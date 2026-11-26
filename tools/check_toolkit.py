#!/usr/bin/env python3
"""Verify the two asset ZIPs and, if supplied, the archived Vertigo BSP."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if __name__ == "__main__":
    sys.dont_write_bytecode = True
sys.path.insert(0, str(ROOT))

from pugc_toolkit.asset_packs import FILENAMES, MANIFEST, inspect_pack


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--assets-dir", type=Path, default=ROOT / "assets",
                        help="Directory containing the input ZIPs")
    parser.add_argument("--source-bsp", type=Path, help="Also verify a restored de_vertigo.bsp")
    args = parser.parse_args()
    ok = True
    for kind in ("full-meshes", "full-textures"):
        path = args.assets_dir / FILENAMES[kind]
        pack = inspect_pack(path, kind)
        if pack["state"] != "ok":
            print(f"{path}: {pack['state']}")
            ok = False
            continue
        print(f"{path}: OK SHA-256 {pack['sha256']}")
        if kind == "full-meshes":
            print(f"Meshes: {pack['meshes']}, cards: {pack['cards']}, paired: True")
        else:
            print(f"WEBP: {pack['webp']}, files: {pack['files']}")
    if args.source_bsp is not None:
        manifest = json.loads(MANIFEST.read_text(encoding="utf8"))
        try:
            with args.source_bsp.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
        except FileNotFoundError:
            print(f"MISSING {args.source_bsp}")
            return 1
        good = actual == manifest["source_bsp_sha256"]
        print(f"{args.source_bsp}: {'OK' if good else 'MISMATCH'} SHA-256 {actual}")
        ok &= good
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
