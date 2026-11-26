# The `pugc` CLI

`pugc --help` lists commands and `pugc place --help` lists command-specific options. To see Blender operation options, use a command such as `pugc blender compare -- --help`. `pugc --version` reports the Toolkit version. `pugc --json capabilities` lists commands, Blender operations, schema versions, OpenSSL, Blender, and FFmpeg on `PATH`, and NumPy in the Toolkit's Python environment. Blender uses its bundled Python and NumPy. [Installation](INSTALLATION.md)

## Machine-readable mode

Put `--json` first. Standard output contains exactly one JSON object, including on argument errors. Blender logs go to stderr. The process runs without prompts. In this mode, `--help` puts help text in `data.help` and `--version` puts the version in `data.version`.

```sh
pugc --json validate --project "$UGC_WORK/project.json"
pugc --json build "$UGC_WORK/project.json" "$UGC_WORK/map.pugc"
pugc --json blender compare -- "$UGC_WORK/source.npz" "$UGC_WORK/map.pugc" \
  --project "$UGC_WORK/project.json" --meshes "$UGC_WORK/meshes.zip" --out "$UGC_WORK/frames"
```

Response envelope v1

| Field | Value |
| --- | --- |
| `schema` | Integer `1`, the version of the envelope and diagnostic fields. |
| `status` | `ok` or `error`. Warnings can accompany `ok`. |
| `exit_code` | Integer matching the process exit status. |
| `data` | Command-specific object. `search` returns a list in `data.results`, and `asset` returns the entry in `data`. `build` and geometry checks include `data.pugc_sha256` of the map actually written or read. `validate` puts report fields in `data`. |
| `artifacts` | Object with absolute output paths. Comparison frames use arrays of paths. Reports and frames saved when geometry issues are found also appear here. |
| `diagnostics` | Array of records with `code`, `severity` (`error` or `warning`), `message`, `action`, absolute `path`, `field`, `instance_id`, and `object_id`. Location fields may be `null`. Use `code` for agent decisions and `message` and `action` for people. |

| Exit code | Meaning | Reason codes |
| --- | --- | --- |
| 0 | Command completed. | Warnings use `validation_warning`. |
| 1 | Invalid input, project, or map. | `invalid_input`, `invalid_profile`, `invalid_project`, `invalid_map`, `invalid_edit`, `approved_road_changed`, `road_join_unchecked`, `invalid_response_data`. |
| 2 | A geometry check found a discrepancy. | `geometry_mismatch`. The report identifies the field and records details about the camera, landmark, or join. |
| 4 | Required resource missing, unavailable, or unsuitable. | `asset_unknown`, `mesh_missing`, `thumbnail_missing`, `archive_missing`, `archive_invalid`, `lfs_pointer`, `input_missing`, `openssl_missing`, `numpy_missing`, `blender_missing`, `ffmpeg_missing`. `doctor` and `fetch-pack` also report pack contents, SHA-256, and download status. With missing meshes, `compare` and `audit` return 4 even if the report includes geometry findings. [Asset diagnostics](RESOURCES.md) |
| 5 | Write failure, revision conflict, or process failure. | `file_operation_failed`, `revision_conflict`, `blender_failed`, `internal_error`. |
| 64 | Invalid command-line arguments. | `invalid_arguments`. |

Human-readable output retains the earlier formats. `search` prints an array, `asset` prints an entry, `validate` prints a report, `build` prints a SHA-256 line, and edit commands are usually silent. An invalid project gives exit code 1 with `validate --project`, and a confirmed geometry mismatch gives 2. [Checkout wrappers and the installed CLI](INSTALLATION.md)

## Project and catalog

Pass file paths in your working directory. For `build` and `validate`, `--profile` selects a JSON profile. `--allowed-ids ID …` further restricts catalog IDs. CLI placement coordinates and dimensions use authoring XYZ meters, rotation around Z uses degrees, and scale uses per-axis factors. File fields retain their own units. [Project and map formats](UGC_FORMATS.md)

| Command | Input | Writes and `artifacts` keys |
| --- | --- | --- |
| `init PROJECT --name NAME` | Name. `--version-from MAP.pugc` copies the build version. `--template MAP.pugc` copies settings and metadata. | `project` file. |
| `import MAP PROJECT` | PUGC v3. Checks the adjacent `MAP.pugc.json` when present. `--receipt` selects another JSON, and `--ignore-receipt` imports the map alone. `--origin-x-cm` sets X in centimeters for import without a sidecar. | `project` file. `data` includes the source map SHA-256, instance count, and `used_receipt` flag. |
| `search PURPOSE` | ID, name, category, purpose, `--dimensions X Y Z`, `--tolerance M`, `--limit N`, `--profile`, and optional `--meshes` and `--bindings`. | Response on stdout. [Asset search](CATALOG.md) |
| `asset OBJECT_ID` | Catalog ID. `--profile`, `--bindings`, and `--meshes` for dimensions or OBJ. `--textures` selects a thumbnail ZIP. | Entry on stdout and `obj` or `thumbnail` files if requested with `--obj PATH` or `--thumbnail PATH`. |
| `doctor --mode base\|small\|full` | `--cache-dir` or separate `--meshes` and `--textures` paths. | Asset status on stdout. |
| `fetch-pack KIND --out ZIP` | Pinned source, local `--archive ZIP`, or `--checkout DIR` for the full pack. Options include `--offline` and `--refresh`. | Verified `archive` at the given path. |
| `fetch-pack full --cache-dir DIR` | Both full ZIPs from `PUGC_ASSET_DIR` or one Git LFS batch with `--checkout DIR`. Options include `--offline` and `--refresh`. | Verified `meshes` and `textures`. A successful pack is kept on partial failure. |
| `place PROJECT ID OBJECT_ID --at X Y Z --assembly NAME` | Instance and model IDs. `--yaw` in degrees, `--scale X Y Z`, `--zone`, `--source`, and `--role`. | Updated `project`. `data` includes `instance_id` and `object_id`. |
| `group PROJECT ASSEMBLY ID …` | Assembly name and instance IDs. | Updated `project`. |
| `rotate PROJECT ASSEMBLY --center X Y Z --yaw DEG` | Assembly, center in meters, and angle in degrees. | Updated `project`. |
| `approve-road PROJECT` | Project for recording a snapshot of road object positions. | Updated `project`. |
| `edit PROJECT REQUEST` | Operations by stable ID and expected project SHA-256. Takes `--dry-run`, `--profile`, and `--allowed-ids`. | Preview or a single project write. [Batch editing](BATCH_EDIT.md) |
| `build PROJECT MAP` | Project. `--version-from MAP.pugc` selects the output build version. `--raw-json PATH` also writes the game data. | `pugc`, `receipt` (`MAP.pugc.json`), and optional `raw_json`. |
| `validate --project PROJECT` or `validate MAP` | One project or map. For maps, `--receipt` selects the sidecar and `--strict-scale` treats authoring scale deviations as errors. | Report on stdout. |
| `game-json PROJECT OUTPUT` | Project to convert into game coordinates. | `game_json` file. |
| `recover MAP` | Interrupted build paths, including the original `--raw-json PATH` if used. | Recovery state in `data.publication`. Recovery lists existing `pugc`, `receipt`, and `raw_json` files. |

## Blender geometry

In `pugc blender [--blender PATH] [--blend SOURCE.blend] [--threads N] OPERATION -- …`, options before the operation select the binary, source scene, and thread count. The operation handles everything after `--`.

| Operation | Input | Writes and `artifacts` keys |
| --- | --- | --- |
| `extract --out FILE.npz` | Scene opened with `--blend`. `--all-scenes` saves every scene. | `source_npz` with geometry, source units, cameras, and materials. |
| `compare SOURCE.npz MAP --out DIR` | NPZ, saved map, and `--meshes` with geometry. Optional `--project`, `--receipt`, `--origin-x-cm`, `--scene`, `--cameras`, `--samples`, and `--strict`. Color frames support `--mode textured`, `--textures`, and `--bindings`. `--flythrough PATH` requires FFmpeg and `--fps` sets the frame rate. | `report` (`comparison.json`), `source_frames`, `result_frames`, and `flythrough` if written. Comparison uses authoring meters. |
| `audit MAP --project PROJECT --out REPORT.json` | Saved map and project. `--meshes` and optional `--profile`, `--receipt`, `--origin-x-cm`, `--strict`, and `--require`. Gaps, heights, and tolerances use meters. | `report` at the given path. |
| `preview --pugc MAP --out IMAGE.png` | Saved map and `--meshes`. `--view iso\|top\|side` sets the viewpoint. `--frame objects\|island\|all` frames placements, the island, or both. The default frames placements, or the island for an empty map. `--save-blend PATH` saves the scene. | `preview` and optional `blend`. |

`preview` and `compare` take `--base-level PATH` for a local copy of the pinned island GLB. Both previews fix the water level at Z = 0 m on the editor grid. `preview` reads the origin from the sidecar or from the `--receipt` and `--origin-x-cm` options. [Island and preview](UGC_WORKFLOW.md#source-scenes-frames-and-routes)

[Geometry coverage](GEOMETRY_QA.md) · [End-to-end example](UGC_WORKFLOW.md)
