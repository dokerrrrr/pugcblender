#!/usr/bin/env python3
"""Prepare a filtered Overpass mesh ZIP or a browser-ready mesh directory."""
import argparse
import json
from pathlib import Path
from shutil import copyfileobj
from zipfile import ZIP_STORED, ZipFile

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--overpass", action="store_true", help="Create overpass_ugc_meshes.zip")
    parser.add_argument("--browser", action="store_true", help="Extract bp-mesh/ for offline viewing")
    parser.add_argument("--out", type=Path, required=True, help="Destination directory")
    parser.add_argument("--assets-dir", type=Path, default=ROOT / "assets",
                        help="Directory containing ugc_meshes_all.zip")
    parser.add_argument("--data-dir", type=Path, default=ROOT / "reference/overpass",
                        help="Directory containing overpass_lab_inputs.json")
    args = parser.parse_args()
    if not (args.overpass or args.browser):
        parser.error("choose --overpass and/or --browser")

    with ZipFile(args.assets_dir / "ugc_meshes_all.zip") as source:
        args.out.mkdir(parents=True, exist_ok=True)
        if args.overpass:
            manifest = args.data_dir / "overpass_lab_inputs.json"
            ids = json.loads(manifest.read_text(encoding="utf-8"))["asset_ids"]
            output = args.out / "overpass_ugc_meshes.zip"
            names = [f"bp-mesh/{object_id}{ext}" for object_id in ids for ext in (".bin.gz", ".json")]
            for name in names:
                source.getinfo(name)
            with ZipFile(output, "w", compression=ZIP_STORED) as destination:
                for name in names:
                    destination.writestr(name, source.read(name))
            print("Created:", output, "ids:", len(ids))
        if args.browser:
            destination = args.out.resolve() / "bp-mesh"
            for member in source.infolist():
                if member.is_dir() or not member.filename.startswith("bp-mesh/"):
                    continue
                target = (args.out / member.filename).resolve()
                if not target.is_relative_to(destination) or target == destination:
                    raise ValueError(f"Unsafe mesh ZIP path: {member.filename}")
                target.parent.mkdir(parents=True, exist_ok=True)
                with source.open(member) as data, target.open("wb") as output:
                    copyfileobj(data, output)
            print("Created offline mesh folder:", destination)


if __name__ == "__main__":
    main()
