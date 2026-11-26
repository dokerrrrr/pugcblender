# Migrate to the current Toolkit

Tag `v1.0.0` contains the older export transform with per-model-ID corrections. To use the unified transform, use Toolkit 1.0.1 from the current checkout. New projects and fresh imports write `layout_version: 2`. You can build an older JSON project with its existing annotations and edits. When `game_original` is present, the exporter maps edits relative to the original game record. To recover authoring coordinates from a built map, import its `.pugc` with the sidecar. [Formats](UGC_FORMATS.md) · [Installation](INSTALLATION.md)

| Previous invocation | Installed command |
| --- | --- |
| `python tools/ugc_project.py init`, `import`, `place`, `group`, `rotate`, `approve-road`, `build` | Use `pugc` with the same subcommand and arguments. `pugc edit` applies a list of operations by ID. |
| `python tools/validate_pugc.py MAP` or `--project PROJECT` | `pugc validate MAP` or `pugc validate --project PROJECT`. |
| `python tools/check_toolkit.py --assets-dir DIR` | `pugc doctor --mode full --cache-dir DIR`. |
| `python examples/ugc_route/fetch_meshes.py ZIP` | `pugc fetch-pack small --out ZIP`. |
| `blender -b … --python tools/compare_pugc.py -- …` | `pugc blender compare -- …`. Other operations include `extract`, `audit`, and `preview`. |

`python -m pugc_toolkit` runs the same CLI. The project format remains `schema: 1` and the binary format remains PUGC v3. A verified sidecar restores IDs on import. Without it, import assigns `import-0000`, `import-0001`, and so on. Store maps, projects, and reports in your external working directory. Enable machine-readable output with `--json` as the first argument. [Formats](UGC_FORMATS.md) · [CLI paths and exit codes](CLI.md)

To roll back, use a separate Python environment and the earlier Toolkit build. If the earlier tool is available only as a checkout, extract the pinned revision into a separate directory. Pass paths to working copies of the maps and a new output file. [Command and tool history](TOOLS.md) · [Recover archived projects](ARCHIVE.md)
