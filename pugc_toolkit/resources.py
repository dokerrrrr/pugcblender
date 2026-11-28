"""Filesystem locations shared by the wheel and the source checkout."""
import os
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parent
ROOT = PACKAGE_ROOT if (PACKAGE_ROOT / "catalog").is_dir() else PACKAGE_ROOT.parent
CATALOG = ROOT / "catalog"
ASSET_DIR = Path(os.getenv("PUGC_ASSET_DIR") or ROOT / "assets").expanduser().resolve()
USER_CACHE = (Path(os.getenv("XDG_CACHE_HOME") or Path.home() / ".cache") / "pugc-toolkit").expanduser().resolve()
ASSET_CACHE = ASSET_DIR if os.getenv("PUGC_ASSET_DIR") else USER_CACHE


def asset_candidates(name):
    return tuple(dict.fromkeys((ASSET_CACHE / name, ASSET_DIR / name)))


def default_asset(name):
    candidates = asset_candidates(name)
    return next((path for path in candidates if path.is_file()), candidates[0])


MESHES = default_asset("ugc_meshes_all.zip")
TEXTURES = default_asset("PUGC_Textures_Ready.zip")
PROFILE = CATALOG / "placement_profile.json"
TEMPLATE = CATALOG / "pugc_v3_empty.json"
