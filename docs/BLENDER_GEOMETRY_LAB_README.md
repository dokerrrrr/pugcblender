# Overpass Geometry Lab for Blender 5.3

This kit studies visible Overpass geometry and compares Counter-Strike Source BSP/VMF geometry with native PUBG UGC meshes from the reference map. Device import is omitted.

## Main file

`Overpass_Geometry_Lab.blend` is a prebuilt native Blender scene. Its meshes are embedded in the `.blend`, so it opens without a browser, network connection, or additional assets.

| Layer | Contents | Count |
| --- | --- | ---: |
| `01 · SOURCE BSP` | Visible surfaces from the compiled BSP, including displacements | 61,697 triangles |
| `02 · SOURCE VMF` | Visible VMF brush surfaces | 30,275 triangles |
| `03 · REFERENCE PUGC` | Native PUBG model geometry from the reference map | 2,801 placements, 187 object IDs |
| `04 · GENERATED PUGC` | Earlier experimental version for comparison | 3,000 placements |
| `PUGC base level` | Starting island from pugc-editor and a water surface for previews when rebuilding the scene | 17 island meshes and a water plane |

Placed objects use collection instances. The geometry for each UGC model loads once and is reused. The 238 library meshes contain a total of 457,594 triangles from native parts, with model-component transforms accounted for.

## View and measure

1. Open the `.blend` in Blender 5.3.
2. Toggle layers `01`, `02`, `03`, and `04` in the **Outliner** using the monitor or eye icon. By default, BSP and the reference map are visible, while VMF and the experimental version are hidden.
3. Switch an area to the **Text Editor**, select the embedded **`LAB_TOOLS.py`** text, and choose **Run Script** (`Alt+P)). Return to the 3D View, press `N`, and open the **Geometry Lab** tab.
4. Select a `REFERENCE_...` object in the Outliner. It represents a UGC placement with its original ID, scale, quaternion, and PUGC position.
5. Choose **Measure selected model → BSP**. Blender builds a BSP BVH and measures from a sample of actual model vertices to the nearest BSP triangles. The panel shows the median, 90th percentile, and fraction of vertices within 1 m.
6. Select `SOURCE_ALIGNMENT` in the Outliner or use the panel to adjust the Source translation, rotation, and axis reflections. This updates the comparison without rebuilding the scene.
7. Use `CAM_Top`, `CAM_Side`, or `CAM_Overview` to inspect different views. In a rebuilt scene, `CAM_Island` frames the island.

`Measure selected model` is an approximate, local measurement. It samples one UGC object's vertices, excludes Source prop meshes absent from the BSP, and does not establish topological equivalence.

## Scripts and inputs

- `create_overpass_blender_lab.py` builds the `.blend` from prepared data and native UGC meshes.
- `LAB_TOOLS.py` provides the 3D View panel for layer toggles and BVH measurements.
- `analyze_overpass_geometry.py` analyzes PUGC-to-BSP distances on the CPU with NumPy and SciPy and reports by UGC type.
- `overpass_lab_inputs.json` holds transforms for all placements extracted from the original `.pugc` files.
- `overpass_source_surfaces.npz` holds compiled visible BSP and VMF triangles.
- `overpass_ugc_meshes.zip` contains the 187 required UGC meshes from the 741-model source archive.
- `prepare_overpass_blender_lab.py` prepares inputs from `.pugc`, BSP, VMF, and the model archive. `--html` can also read layers from the archived HTML.
- `verify_overpass_lab.py` and `test_addon.py` verify scene structure and measurements.

### Rebuild the Blender scene

Set the Toolkit, asset, and working-directory paths. The script creates an intermediate mesh archive in a temporary directory. [Working directories](UGC_WORKFLOW.md#assets-and-labs)

```bash
bash "$UGC_TOOLKIT/tools/build_overpass_blender_scene.sh" "$UGC_WORK/Overpass_Geometry_Lab.blend" \
    --assets-dir "$UGC_ASSETS"
```

`build_validation.json` appears beside the scene. Use the `BLENDER` environment variable to select a Blender binary. For an offline build, pass a local copy of the pinned GLB through `--base-level PATH`. [Island and water level](UGC_WORKFLOW.md#source-scenes-frames-and-routes)

For your own sources, prepare data from BSP, VMF, or both and pass the output directory to Blender.

```bash
python "$UGC_TOOLKIT/tools/prepare_overpass_blender_lab.py" \
    --bsp "$UGC_WORK/de_overpass.bsp" --vmf "$UGC_WORK/de_overpass.vmf" \
    --reference "$UGC_WORK/reference.pugc" --mesh-zip "$UGC_ASSETS/ugc_meshes_all.zip" \
    --out "$UGC_WORK/lab-inputs"
blender --background --python-exit-code 1 --python "$UGC_TOOLKIT/tools/create_overpass_blender_lab.py" -- \
    --data-dir "$UGC_WORK/lab-inputs" --output "$UGC_WORK/Overpass_Geometry_Lab.blend" --no-render
```

To verify the saved scene, open it and pass script and report paths.

```sh
blender -b "$UGC_WORK/Overpass_Geometry_Lab.blend" --python-exit-code 1 \
  --python "$UGC_TOOLKIT/tools/verify_overpass_lab.py" -- --out "$UGC_WORK/reopen_validation.json"
blender -b "$UGC_WORK/Overpass_Geometry_Lab.blend" --python-exit-code 1 \
  --python "$UGC_TOOLKIT/tools/test_addon.py" -- --lab-script "$UGC_TOOLKIT/tools/LAB_TOOLS.py"
```

### Run a bulk comparison without Blender

```bash
python -m pip install numpy scipy
python "$UGC_TOOLKIT/tools/analyze_overpass_geometry.py" --data-dir "$UGC_WORK/lab-inputs"
```

`geometry_distance_report.json` reports distances on actual local UGC meshes. It uses sampled vertices, so mesh density, large-object scale, and props missing from the BSP affect the result. A smaller distance measures proximity only.

## Coordinates and visual accuracy

- PUGC stores positions in Unreal Engine centimeters. Blender receives XYZ divided by 100 and uses the UE rotation quaternions in the same Z-up basis.
- PUGC Editor mesh data uses meters and Y-up, converted to Blender Z-up with internal model matrices accounted for.
- Source BSP/VMF units convert from inches to meters. The initial empirical alignment reflects Source X and translates by **(325.28, 475.59, 56.92) m** in Blender XYZ. Tune this initial estimate through `SOURCE_ALIGNMENT`.
- A compiled BSP describes brush and displacement geometry. Full vertices for external Source `prop_static` models require the original MDL/VVD/VTX files.
- The BSP includes some VMT/VTF data. The lab uses diagnostic materials and colors because it lacks a full set of diffuse textures. UGC `.bin.gz` files contain meshes and material paths.
- The generated layer is an earlier experiment using box approximations.
- The scene opened and passed headless verification in Blender 5.3.0, including the native library meshes and BVH operation. EGL/GPU availability limited Blender screenshots in the Linux test environment. `overpass_geometry_top_comparison.png` and `overpass_geometry_elevation.png` are CPU diagrams plotted from actual vertices.

## Verification

- Reopened the `.blend` successfully in Blender 5.3.
- `REFERENCE` has 2,801 placements and `GENERATED` has 3,000. All 187 native model types were found.
- The active dependency graph contains 3,128 evaluated geometry instances.
- A Blender BVH measurement for reference model `UGC 16042` sampled 132 vertices. The median distance to the nearest BSP triangles at the initial alignment was 0.60 m. This measures that model only.
