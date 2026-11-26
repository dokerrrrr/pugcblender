# PUGC container and coordinates

The binary `.pugc` wrapper records the container version. The main codec reads and writes version 3. Payload fields `dataVersion` and `buildVersion` are checked at the game-data and profile levels. `schema: 1` applies to the editable project and JSON sidecar. The Toolkit package has a separate release version. [Project and sidecar formats](UGC_FORMATS.md)

| Entry point | Container inputs and outputs | Coordinates |
| --- | --- | --- |
| `pugc_codec.decode_raw`, `read_game`, `encode_raw` | v3 wrapper | Game XYZ in centimeters and XYZW |
| `pugc_codec.read/decode`, `write/encode`, `blender_preview_pugc.py` | v3 wrapper | One transform between the game file and authoring coordinates |
| `pugc import/build` | v3 wrapper, project JSON, and JSON sidecar | Import applies one transform into authoring space. Build transforms new and edited placements, and reuses original game records for untouched placements. `init --template` reads v3 game metadata. |
| `pugc validate` | v3 binary or project JSON | Binary validation uses game coordinates. Project preflight reads authoring fields. |
| `pugc blender compare/audit` through `read_with_receipt` | v3 wrapper | One transform to authoring space with the sidecar or supplied origin. Frame geometry and measurements use meters. |
| `prepare_overpass_blender_lab.py` | Reads v1, v3, and historical headerless blocks through `read_lab_game` | The lab accepts game centimeters. It reorders axes and converts units for visualization. |
| `ugc_reconstructor.py`, `build_from_bsp.sh` | Reads v1, v3, and unwrapped blocks. Writes v3. | The reconstructor works in game coordinates and writes them directly. |
| `vmf_to_pugc_corrected.py` | Reads v1 and v3 wrappers. Writes v3. | Game coordinates |
| `pugc_portable.mjs` with the pinned external codec | Reads and writes v3 wrappers for cross-checks on prepared samples | Game JSON without axis conversion |

In the authoring API, `convert_layout` sets position X to `2 * origin_x_cm - x`, rounded to eight decimal places. It negates Y and Z in the XYZW quaternion. Position Y and Z and the scale stay the same. One formula applies to all models and devices. Preview, audit, and OBJ export reflect the local X axis around the native pivot. [Orientation test](../tests/test_codec_and_mesh.py)

The legacy axis and origin table supports old authoring snapshots and road approvals. Compatibility uses `game_original` to carry over edits from an older imported instance. The conversion from current authoring coordinates to game coordinates always uses the same formula. [Project and sidecar formats](UGC_FORMATS.md)

The Python codec limits containers to 8 MiB and decompressed JSON to 32 MiB. Across 12 tracked maps at the original revision, the largest file was 115,573 bytes and the largest JSON was 737,510 bytes. Before calling OpenSSL, it checks the wrapper, its CRC, encrypted-block alignment, and the length at the end of the file. Before decompression, it checks the decrypted payload CRC, padding, and both declared lengths. Decompression is limited to the declared length plus one byte. It checks for a complete zlib stream and UTF-8 JSON. If OpenSSL fails, the codec reports the required executable. [Implementation](../pugc_toolkit/pugc_codec.py)

The archive keeps the earlier lab implementations, including writing older wrapper versions. Use the lab adapter to read v1. Core commands accept v3. [Archived VMF implementation](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/tools/vmf_to_pugc_corrected.py)
