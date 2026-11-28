# Geometry verification coverage

```sh
pugc --json blender compare -- "$UGC_WORK/source.npz" "$UGC_WORK/route.pugc" \
  --project "$UGC_WORK/route.json" --meshes "$UGC_WORK/meshes.zip" \
  --cameras Approach Alongside --strict --out "$UGC_WORK/frames"
pugc --json blender audit -- "$UGC_WORK/overpass.pugc" --project "$UGC_WORK/overpass.json" \
  --meshes "$UGC_WORK/meshes.zip" --strict --require viewpoints --out "$UGC_WORK/audit.json"
```

Both commands read the saved `.pugc` and report its actual SHA-256. The reports and machine-readable `data.geometry_check` list expected and checked items, omissions, and mismatch counts. `compare` counts instances, cameras, and camera–landmark pairs. `audit` counts instances, joins, viewpoints, and approved road positions.

| Check status | Meaning |
| --- | --- |
| `checked` | The specified items were checked. |
| `mismatch` | The check found a discrepancy. |
| `skipped` | The check was not requested or had no candidates. |
| `incomplete` | Meshes, a camera, an annotation, or other required inputs were missing. |

An overall result of `complete` means all requested checks were covered. `findings` means a discrepancy was found, `partial` means coverage was incomplete, and `skipped` means no checks ran. `partial` takes precedence over `findings`. Individual findings remain in the report even with partial coverage. Machine-readable mode returns 4 for `partial` and 2 for `findings`.

`compare --strict` requires the selected cameras and annotated landmarks for them. `audit --strict` requires route annotations and full coverage of the requested inputs. To require specific groups for acceptance, add `--require road_joins`, `--require viewpoints`, or `--require approved_road`. Strict mode also uses these exit codes in human-readable output. For a partial preview, omit `--strict` and read `geometry_check` alongside the frames and report.

For an external map, provide its verified sidecar through `--receipt` or set the reflection origin with `--origin-x-cm`. In the latter case, a map without a sidecar uses IDs such as `objects[0]` and `objects[1]` in record order. Pass annotations with these IDs through `--project`. Comparison also reads `source_to_authoring_m`, `landmarks`, and scene cameras. Paired frames use matching cameras. In `textured` mode, the report records binding provenance. The audit reports observations and suggestions that can be applied in a separate project edit.

## Configure comparison and route checks

- `compare` accepts a `.blend` or an NPZ from `extract`. Both routes use evaluated geometry from the Blender layer with viewport visibility and modifiers. For `.blend`, comparison uses all perspective and orthographic cameras in the active scene by default. When none are available, it frames the source from isometric, top, and side views. Use `--scene` to select another scene and `--cameras` to select specific cameras. For NPZ input the default is one camera. Use `--all-cameras` to request every supported camera or the same overview views.
- To align the source, set `source_to_authoring_m` in the project to a 4×4 matrix with rotation, translation, and positive uniform scale. Cameras transform along with the geometry.
- `--mode geometry` shows silhouettes. `--mode textured` uses available images from the asset cache or from a ZIP passed with `--textures PATH`. In the source scene, images connected directly to Principled BSDF Base Color are supported. `--bindings PATH` provides verified mappings from game material paths to ZIP entries. For game materials the report counts loaded textures, confirmed and inferred mappings, missing mappings, and image issues.
- `landmarks` maps source names to result IDs and lists cameras. The report checks the screen side and visibility of the specified landmarks. Frames include the island and water, and comparison rays test source and result geometry. A flythrough needs perspective cameras with matching projections and FFmpeg.
- `road_joins` defines two road surfaces, a join point, direction, half-width, and tolerances. The audit checks heights, gaps, and overlap. `drive_material` explicitly selects the surface. When an `approve-road` snapshot exists, the audit checks the approved placements.
- `viewpoints` defines viewpoints and `opaque_instances` identifies verified opaque instances. A hidden decoration can be recommended for removal only with explicit `role: "decor"` and `gameplay: false` and confirmation that it lies entirely inside a closed opaque mesh.

[Source scenes, materials, and routes](UGC_WORKFLOW.md#source-scenes-frames-and-routes)
