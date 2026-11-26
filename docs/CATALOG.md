# Asset search and catalog entries

```sh
pugc --json search "стена" --limit 5
pugc --json search "SmallHouse"
pugc --json search "wall" --dimensions 4 0.4 3 --tolerance 0.5
pugc --json asset 10247
pugc --json asset 24 --meshes "$UGC_ASSETS/ugc_meshes_all.zip"
```

A single numeric token looks up an exact ID. Text matches names, categories, and types case-insensitively. Category matches come first. For objects absent from the profile, the first nested mesh name provides a fallback. Ties are sorted by ID. To search by purpose, try part names such as `bench`, `wall`, `pillar`, or `fence`. Russian aliases are also supported, including `стена`, `стены`, `дом`, `здание`, `скамья`, `скамейка`, `лестница`, `пол`, `забор`, `дверь`, and `башня`.

`--dimensions` takes three positive, finite XYZ dimensions in meters. Dimension searches sort by relative closeness and skip entries without dimensions. `--tolerance` can limit the absolute difference for each axis in meters. `--limit` takes a positive integer.

In machine-readable output, `data.query_status` is `matched`, `empty` for catalog browsing, `no_matches`, or `unsupported_term`. Unsupported terms produce a hint with categories. `data.catalog_coverage` compares IDs across the profile, index, material candidates, and selected ZIP.

## Catalog entry fields

- `category`, `weight`, `profile_id`, `profile_revision`, and `profile_repository` describe the selected profile. `placement_status: listed` marks an existing profile entry. Before placing an object, also check its type, limits, and map-specific constraints with `pugc validate`.
- `geometry_indexed` reports presence in the installed index and `mesh_available` checks the selected ZIP. `null` means no ZIP was supplied. ID 24 has indexed geometry and no entry in the default profile. For ID 10247, `SmallHouse` describes the whole building and `first_mesh_name` identifies one of its parts.
- `dimensions_source` distinguishes full-mesh dimensions from the installed index. Pass a local ZIP with `--meshes` for exact dimensions. The installed index works offline.
- `thumbnail_source` distinguishes an editor catalog path from a name-based guess. For `materials`, `binding` records an explicit `--bindings` mapping, a name-based match, or a missing mapping. A candidate match includes `confidence` when available. `--bindings` accepts a JSON mapping from material paths to ZIP entries, as used by Blender comparison. The tool checks whether an image exists when it reads it.

[CLI reference](CLI.md) · [Retrieve assets](RESOURCES.md)
