# PUGC Toolkit assets

`pugc doctor` verifies inputs and lists available capabilities. Put `--json` before the command to get statuses in `data.packs`, feature flags in `data.features`, and recovery commands in `diagnostics[].action`. Use `pugc capabilities` to check whether Blender or NumPy is available for the geometry operation you intend to run. [CLI](CLI.md)

| Mode | Assets | Features |
| --- | --- | --- |
| `base` | Bundled profile, template, and catalog. | Search, catalog entries, editing, building, and validation. |
| `small` | `route-meshes.zip` with nine meshes for the pinned tutorial. | Core commands and tutorial-route geometry. |
| `full` | `ugc_meshes_all.zip` and `PUGC_Textures_Ready.zip`. | Full-catalog geometry, thumbnails, and textures. |

## Work from a separate directory

```sh
pugc --json doctor --mode base
export PUGC_ASSET_DIR="$UGC_ASSETS"
pugc fetch-pack small --archive "$UGC_ASSETS/ugc_meshes_all.zip" --out "$UGC_ASSETS/route-meshes.zip"
pugc fetch-pack small --out "$UGC_ASSETS/route-meshes.zip" --offline
pugc --json doctor --mode small --cache-dir "$UGC_ASSETS"
pugc asset 12005 --meshes "$UGC_ASSETS/route-meshes.zip" --obj "$UGC_WORK/12005.obj"
```

Put `mod_main_level.glb` and the asset ZIPs in `PUGC_ASSET_DIR` or pass paths explicitly through `--base-level`, `--meshes`, and `--textures`. For `doctor`, explicit paths override names in `--cache-dir`. The small pack is verified against nine SHA-256 hashes. `fetch-pack small` reads entries from `route-meshes.zip` or `ugc_meshes_all.zip` in `PUGC_ASSET_DIR`. Use `--archive ZIP` to select a particular local archive.

For the full pack, specify a checkout with Git LFS access. Retrieval uses pinned revision `c3ab056057d9eb04f401839619bbd35641c863e4`. The download cache and prepared ZIP live in a temporary directory beside the selected output. The command verifies each ZIP and installs it atomically under a lock. `--refresh` forces source verification and preparation again. A failure preserves the previous output ZIP.

```sh
pugc fetch-pack full --checkout "$UGC_TOOLKIT" --cache-dir "$UGC_ASSETS"
pugc --json doctor --mode full --cache-dir "$UGC_ASSETS"
```

To restore from a local ZIP, use `--offline --archive /path/to/archive.zip` in place of `--checkout`. Full-pack verification checks SHA-256 hashes, 741 meshes with 741 corresponding cards, and 3,092 WEBP images. [Manifest](../catalog/pack_contents.json)

## Verification statuses

| Status | Action |
| --- | --- |
| `ok` | Use the path in `data.packs[].path`. |
| `archive_missing` | Pass a local ZIP through `--archive` or check `PUGC_ASSET_DIR`. |
| `lfs_pointer` | Restore the object with `fetch-pack … --checkout` or select a complete ZIP. |
| `archive_invalid`, `hash_mismatch` | Retrieve the archive again from the pinned source. |
| `incomplete_pairs` | Retrieve the full pack. `missing_cards` and `missing_meshes` list IDs for incomplete pairs. |
| `pack_incomplete` | Retrieve all nine entries for the small pack or select a verified local source. |
| `download_failed` | Check Git LFS access or pass a local ZIP through `--archive`. |

`tools/check_toolkit.py` runs the same checks. `examples/ugc_route/fetch_meshes.py` is a compatibility wrapper for the small pack. `tools/prepare_assets.py` and `tools/unpack_assets.py` prepare lab inputs from local ZIPs. Previous download and merge scripts are available in the archive. [Tools and archive](TOOLS.md)
