# Project and sidecar JSON formats

`schema: 1` applies to Toolkit JSON. Game maps use PUGC v3. The machine-readable JSON Schema 2020-12 defines `#project` and `#receipt`. Use the Toolkit loader for checks that relate multiple records or files. [Schema](schemas/ugc-formats-v1.schema.json)

The codec reference describes coordinate conversion boundaries and the versions supported by each command. [PUGC container and coordinates](PUGC_CODEC.md)

## Editable project

A project requires `schema`, a finite `origin_x_cm`, a `game` object, and an ordered `instances` array. `game` holds decoded map data except for the `objects` list, which is built from `instances` in the same order.

Each instance requires a unique nonempty string `id`, an integer catalog `objectId`, a nonempty `assembly` string, a `zone` of `road`, `shoulder`, `near`, or `far`, and a `transform`. Multiple instances of one catalog object have different IDs. Extra fields are allowed. For example, `source` describes provenance, and `role` and `gameplay` are used by the audit.

`transform.translation` stores authoring XYZ coordinates in centimeters, `rotation` is an XYZW quaternion, and `scale3D` contains dimensionless XYZ factors. `place --at` and `rotate --center` take meters, and `--yaw` takes degrees around Z. `origin_x_cm` is the X reflection origin between authoring and game space. For a map without a sidecar, it defaults to 50,000 cm. `layout_version: 2` denotes a unified transform around the native pivot.

After import, `game_original` stores the original game record for the instance. A rebuild reuses an untouched record in full, including its original precision and fields the Toolkit does not recognize.

In a project without `layout_version`, the builder reconstructs each imported instance's legacy snapshot from `game_original`. It adds the position delta to the current native pivot and converts the rotation from the old basis to the current basis. It takes scale from `transform`. For an instance without `game_original`, the builder uses the specified transform in current coordinates. To convert a source map to a `layout_version: 2` project, import its binary `.pugc`. [Migration](MIGRATION.md)

```json
{
  "schema": 1,
  "layout_version": 2,
  "origin_x_cm": 42000,
  "game": {
    "name": "Example",
    "dataVersion": 3,
    "buildVersion": "2608.1.1",
    "deviceEventList": []
  },
  "instances": [
    {
      "id": "west-post",
      "objectId": 12005,
      "assembly": "Gate",
      "zone": "near",
      "source": "West post",
      "transform": {
        "translation": { "x": 100, "y": 200, "z": 0 },
        "rotation": { "x": 0, "y": 0, "z": 0, "w": 1 },
        "scale3D": { "x": 1, "y": 1, "z": 1 }
      }
    }
  ]
}
```

## JSON sidecar

`build` writes `map.pugc.json` beside `map.pugc`. The sidecar requires `schema`, `pugc_sha256` with the lowercase SHA-256 of the entire binary, a finite `origin_x_cm`, and an `instances` array. Each item corresponds to the game object at the same index. The tool checks the record count, `objectId` at each index, and `id` uniqueness. When `objectId` repeats, the array index determines the match.

The sidecar contains instance annotations from the project, including extra fields. Tools read geometry from the binary map. Sidecar `instances` include annotations and omit `transform` and `game_original`. The optional `approved_road` maps instance IDs to snapshots from `approve-road`. Each snapshot contains `objectId` and `transform` in authoring coordinates and must match an instance in zone `road` within conversion rounding. An absent `approved_road` is equivalent to an empty collection. Import converts snapshots from old pairs to `layout_version: 2`.

```json
{
  "schema": 1,
  "layout_version": 2,
  "pugc_sha256": "0000000000000000000000000000000000000000000000000000000000000000",
  "origin_x_cm": 42000,
  "instances": [
    {
      "id": "west-post",
      "objectId": 12005,
      "assembly": "Gate",
      "zone": "near",
      "source": "West post"
    }
  ],
  "approved_road": {}
}
```

The example hash shows the field format. At build time, the Toolkit computes the hash of the saved map.

To reproduce visual checks, keep the full project and separate source files with cameras and camera paths. `landmarks`, `road_joins`, `viewpoints`, `opaque_instances`, `annotations`, and `source_to_authoring_m` are stored only in the full project. Explicit annotations within `instances` are copied when importing the pair.

## Re-import

Pass the `.pugc` and the path to a new project. Import uses the adjacent `.pugc.json` if present, or the sidecar selected with `--receipt`. It restores IDs, annotations, the approved road, and the origin from a verified pair. An invalid pair is rejected before project output. Once the temporary file is fully written, it replaces the destination JSON.

```sh
pugc import /path/to/map.pugc /path/to/project.json
```

For a third-party map without a sidecar, IDs are assigned in order as `import-0000`, `import-0001`, and so on. Use `--ignore-receipt` to import the same way when an incompatible sidecar exists. `--origin-x-cm` sets the origin when importing a binary. For a verified pair, a supplied origin must match the saved value.

```sh
pugc import /path/to/map.pugc /path/to/project.json \
  --ignore-receipt --origin-x-cm 42000
```

## Preflight and build

`pugc validate --project` and `pugc build` check project structure before coordinate conversion, then evaluate the generated game records using the same rules. Both take `--profile` and `--allowed-ids`. Instance diagnostics include the field path and stable ID.

When validating an imported map, inherited scale for the same model remains a warning while its original value is preserved. An unknown object produces a warning and an incomplete budget if its original game record is preserved in full. If the original saved records already exceed a limit, the overage remains a warning while the category weight stays at or below that level. New deviations and violations of an explicit allowlist stop the build before it writes files.

Preflight prints JSON. Build prints the successful output SHA-256 to stdout and sends JSON errors and warnings to stderr. Validating a standalone binary applies the selected profile without project history.

## Write and recover

Use distinct paths for the project, map, sidecar, and `--raw-json`. On import, the project records the source map and sidecar paths in `import_source`. Choose a new output when building that project. For older projects without `import_source`, set a new path manually.

A project write replaces the file after preparing the complete JSON. During a build, the Toolkit keeps the previous outputs, rereads the prepared map, and matches its hash and records against the prepared sidecar. A concurrent command with overlapping outputs reports a busy file and can retry after the first process completes. `.ugc-lock-*` files serve as lock points and remain in the working directory.

If the process is interrupted, reading the pair reports an unfinished write. Run `recover` with the same paths as the build. If the build wrote `--raw-json`, pass that path too.

```sh
pugc recover /path/to/map.pugc --raw-json /path/to/game.json
```

`restored` means the previous set was recovered, `committed` means cleanup finished after the new set was successfully committed, and `none` means there was no unfinished write. If an external process replaced an output after failure, recovery reports its path and preserves both versions for inspection. An interrupted standalone project write may leave a `.ugc-write-*` directory with a temporary copy. Remove it after the processes using the directory have finished.
