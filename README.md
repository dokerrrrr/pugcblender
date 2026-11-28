# PUBG UGC Toolkit

Create and edit static PUBG UGC maps with native game assets.

## Installation

The core commands require Python 3.11 or later. Reading and writing `.pugc` v3 files requires OpenSSL on `PATH`. Build the 1.0.0 wheel from the current checkout and install it in your chosen environment. `python -m pugc_toolkit` runs the same CLI. [Build the wheel](docs/INSTALLATION.md#build-the-wheel-and-sdist)

```sh
python -m pip install /path/to/pubg_ugc_toolkit-1.0.0-py3-none-any.whl
pugc --version
```

[Installation and optional dependencies](docs/INSTALLATION.md) · [Migration](docs/MIGRATION.md) · [Changelog](CHANGELOG.md)

## Agent workflow

For Blender previews and comparisons, run `pugc fetch-pack full` once to download and verify the mesh ZIP, texture ZIP, and starting island. Later runs use the same local cache. [Asset setup](docs/RESOURCES.md)

Account for the starting island and the fixed water level at Z = 0 m. `pugc validate` checks the saved file, object settings, and placement limits. When you create or rearrange a scene, use `pugc blender preview` on the saved `.pugc` to check terrain contact, clearance above water, and walkable routes. Keep the map and its `.pugc.json` sidecar together. [Map authoring rules](AGENTS.md) · [Island and preview](docs/UGC_WORKFLOW.md#source-scenes-frames-and-routes)

### Create a new map

This example puts native support 12005 on the island's central pad. To find assets for your own scene, run `pugc search wall --limit 5` and inspect a candidate with `pugc asset ID`. Set `UGC_WORK` to choose a working directory.

```bash
(
  set -eu
  work="${UGC_WORK:-$HOME/PUBG Maps/Toolkit Check}/New Map"
  mkdir -p "$work"
  pugc init "$work/project.json" --name "New Map"
  pugc place "$work/project.json" west-post 12005 --at 490 510 11.74 --assembly Gate
  pugc build "$work/project.json" "$work/map.pugc"
  pugc --json validate "$work/map.pugc" > "$work/validation.json"
)
```

### Client save version

New projects use `buildVersion` `2611.1.2`. If a newer client save uses a different version, pass the path to any compatible v3 map.

```sh
pugc init project.json --name "New Map" --version-from latest.pugc
pugc build project.json map.pugc
```

`--version-from` copies only `buildVersion`. The project stores it in its JSON. For an existing project, `pugc build project.json map.pugc --version-from latest.pugc` sets the version for that export. A normal import and build preserve the source map's version. To copy game settings and owner metadata, initialize the project with `--template` and a save from your client.

Each v3 map derives its key from the length and checksum of its payload. The build version lives inside that payload. A client change to the container format or encryption requires a codec update.

Validation warns when positive scales fall outside the authoring profile. `pugc validate map.pugc --strict-scale` treats those limits as errors.

### Edit an imported map

This example rotates the Gate assembly from the first map and writes a copy. For your own map, substitute its path, assembly name, and rotation center. Use `pugc edit` for individual or batch changes by instance ID. [Batch editing](docs/BATCH_EDIT.md)

```bash
(
  set -eu
  root="${UGC_WORK:-$HOME/PUBG Maps/Toolkit Check}"
  work="$root/Edit"
  mkdir -p "$work"
  pugc import "$root/New Map/map.pugc" "$work/project.json"
  pugc rotate "$work/project.json" Gate --center 490 510 11.74 --yaw 30
  pugc build "$work/project.json" "$work/map.pugc"
  pugc --json validate "$work/map.pugc" > "$work/validation.json"
)
```

For automation, put `--json` before the command. If an operation fails, check `diagnostics[].code` and `diagnostics[].action`. Output paths are in `artifacts`. [CLI and response reference](docs/CLI.md)

## End-to-end example with nine meshes

Build the sample entrance, open the saved map in Blender, and compare it with the source scene. [Commands and inputs](docs/UGC_WORKFLOW.md#end-to-end-example-with-nine-meshes)

## Reference

- [Asset search](docs/CATALOG.md) and [full asset library](docs/RESOURCES.md)
- [Visual review and flythroughs](docs/UGC_WORKFLOW.md#source-scenes-frames-and-routes) and [optional Blender skills](optional/blender-skills/README.md)
- [Advice from archived projects](docs/AUTHOR_RULES.md#advice-from-archived-projects) and [recovering files](docs/ARCHIVE.md)
- [Toolkit development, checks, and releases](docs/DEVELOPMENT.md)
