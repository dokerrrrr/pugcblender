#!/usr/bin/env python3
"""Unpack complete mesh and texture packs into a selected directory."""
import argparse
from pathlib import Path
from shutil import copyfileobj
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--meshes", action="store_true")
    parser.add_argument("--textures", action="store_true")
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--out", type=Path, required=True, help="Destination for meshes/ and textures/")
    parser.add_argument("--assets-dir", type=Path, default=ROOT / "assets",
                        help="Directory containing the input ZIPs")
    args = parser.parse_args()
    if not (args.meshes or args.textures or args.all):
        parser.error("pass --all or --meshes or --textures")

    packs = (
        (args.meshes or args.all, "ugc_meshes_all.zip", "meshes"),
        (args.textures or args.all, "PUGC_Textures_Ready.zip", "textures"),
    )
    for selected, filename, subdirectory in packs:
        if not selected:
            continue
        destination = args.out.resolve() / subdirectory
        with ZipFile(args.assets_dir / filename) as archive:
            for member in archive.infolist():
                if member.is_dir():
                    continue
                target = (destination / member.filename).resolve()
                if not target.is_relative_to(destination) or target == destination:
                    raise ValueError(f"Unsafe ZIP path: {member.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.open(member) as data, target.open("wb") as output:
                    copyfileobj(data, output)
        print(filename, "->", destination)


if __name__ == "__main__":
    main()
