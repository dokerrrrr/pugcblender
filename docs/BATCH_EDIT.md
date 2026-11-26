# Batch project editing

`pugc edit PROJECT REQUEST` applies a list of operations to an editable schema 1 project. Get the SHA-256 of the current project bytes with `sha256sum project.json` or `python -c 'from hashlib import sha256; from pathlib import Path; print(sha256(Path("project.json").read_bytes()).hexdigest())'`. Put it in the request's `base_sha256`.

Use `pugc import` on an archived map to get a project with `layout_version: 2`. If you edit older JSON directly, take the existing instance parameters from that file. At build time, the Toolkit maps edits to older imported placements into current coordinates relative to `game_original`. [Project format](UGC_FORMATS.md#editable-project)

```json
{
  "schema": 1,
  "base_sha256": "REPLACE_WITH_SHA256",
  "operations": [
    {"op": "update", "id": "west-bench", "fields": {"at_m": [1.5, 7, 0.2], "assembly": "Gate"}},
    {"op": "add", "id": "east-post", "fields": {"objectId": 12005, "at_m": [3, 7, 0], "assembly": "Gate"}},
    {"op": "delete", "id": "extra-panel"}
  ]
}
```

Use IDs from `instances[].id`. `objectId` identifies a model type and may repeat in a project. The tool applies operations in order. `add` requires `objectId`, `at_m`, and `assembly`. Its defaults are zone `near`, the identity quaternion, and a scale of 1 on all axes. `update` changes only the fields supplied. `delete` takes only `id`. After deleting an original instance, you cannot add its ID again in the same batch.

Supported keys in `fields`

| Field | Value |
| --- | --- |
| `objectId` | Integer catalog ID. |
| `at_m` | Three XYZ coordinates in authoring meters. |
| `rotation_xyzw` | Unit XYZW quaternion. |
| `scale` | Three XYZ scale factors. |
| `assembly` | Assembly name. |
| `zone` | `road`, `shoulder`, `near`, or `far`. |
| `source`, `role` | Nonempty string. Use `null` to remove the field. |

```sh
pugc --json edit "$UGC_WORK/project.json" "$UGC_WORK/edits.json"
pugc build "$UGC_WORK/project.json" "$UGC_WORK/map.pugc"
pugc validate "$UGC_WORK/map.pugc"
```

Add `--dry-run` to `edit` to preview the batch. `data.changes` lists the resulting actions and fields, and `data.base_sha256` and `data.result_sha256` report the original and expected hashes. The write operation checks SHA-256 under the project lock, validates the batch using the `validate` rules, and replaces the file with one atomic write. Changing an approved road placement, submitting an invalid operation, or encountering a revision conflict preserves the original project. If the request makes no changes, `data.edit_status` is `unchanged`. On `revision_conflict`, read the project again and prepare a new request. For custom constraints, use `--profile` and `--allowed-ids`. [JSON interface](CLI.md)
