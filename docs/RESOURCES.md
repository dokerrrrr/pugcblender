# PUGC Toolkit assets

`pugc doctor` verifies inputs and lists available capabilities. Put `--json` before the command to get statuses in `data.packs`, feature flags in `data.features`, and recovery commands in `diagnostics[].action`. Use `pugc capabilities` to check whether Blender or NumPy is available for the geometry operation you intend to run. [CLI](CLI.md)

| Mode | Assets | Features |
| --- | --- | --- |
| `base` | Bundled profile, template, and catalog. | Search, catalog entries, editing, building, and validation. |
| `small` | `route-meshes.zip` with nine meshes for the pinned tutorial. | Core commands and tutorial-route geometry. |
| `full` | `ugc_meshes_all.zip`, `PUGC_Textures_Ready.zip`, and `mod_main_level.glb`. | Full-catalog geometry, thumbnails, textures, and the starting island. |

## Download the full pack

```sh
pugc fetch-pack full
pugc --json doctor --mode full
```

The first setup downloads about 700 MB from public, pinned sources. It works from the installed toolkit without a checkout or Git LFS. The command checks SHA-256, the ZIP contents, and the size of the island, then installs each file atomically. Retrying reuses the verified files and retrieves the missing or damaged ones. Add `--offline` to use local copies only or `--refresh` to restage the files and check them again. A failed refresh preserves the existing file.

The default location is `$XDG_CACHE_HOME/pugc-toolkit` or `~/.cache/pugc-toolkit`. Set `PUGC_ASSET_DIR` to share a different directory across commands. `fetch-pack full --cache-dir DIR` and `doctor --mode full --cache-dir DIR` select a directory for a single invocation. For individual files, `--meshes`, `--textures`, and `--base-level` override the default paths where supported.

With `--checkout DIR`, the command can use ZIPs already present in the checkout or retrieve them through Git LFS at that checkout's `HEAD`, then verify them against the same manifest. For an individual file, use `fetch-pack full-meshes`, `fetch-pack full-textures`, or `fetch-pack island` with `--out FILE`. Add `--offline --archive FILE` to use a specific local source. The full ZIPs contain 741 meshes and matching cards, and 3,092 WEBP images. [Manifest](../catalog/pack_contents.json)

## Prepare the tutorial pack

```sh
pugc fetch-pack small --out "$UGC_WORK/route-meshes.zip" --offline
pugc --json doctor --mode small --meshes "$UGC_WORK/route-meshes.zip"
```

The small pack is verified against nine SHA-256 hashes. It can be prepared from the cached full mesh ZIP, an existing `route-meshes.zip`, or a local source passed through `--archive ZIP`.

## Verification statuses

| Status | Action |
| --- | --- |
| `ok` | Use the path in `data.packs[].path`. |
| `archive_missing`, `base_level_missing` | Run `pugc fetch-pack full` or supply a verified local copy. |
| `lfs_pointer` | Run `pugc fetch-pack full` or select a complete ZIP. |
| `archive_invalid`, `hash_mismatch` | Retrieve the archive again from the pinned source. |
| `incomplete_pairs` | Retrieve the full pack. `missing_cards` and `missing_meshes` list IDs for incomplete pairs. |
| `pack_incomplete` | Retrieve all nine entries for the small pack or select a verified local source. |
| `download_failed` | Check access to the reported source or pass a local file through `--archive`. |

`tools/check_toolkit.py` runs the same checks. `examples/ugc_route/fetch_meshes.py` is a compatibility wrapper for the small pack. `tools/prepare_assets.py` and `tools/unpack_assets.py` prepare lab inputs from local ZIPs. Previous download and merge scripts are available in the archive. [Tools and archive](TOOLS.md)
