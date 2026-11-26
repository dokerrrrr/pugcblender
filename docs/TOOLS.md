# Supported, lab, and historical tools

## Installed Toolkit

| Task | Entry point | Verification |
| --- | --- | --- |
| Create, import, edit, batch edit, build, recover, and validate | `pugc init`, `import`, `place`, `group`, `rotate`, `approve-road`, `edit`, `game-json`, `build`, `recover`, `validate` | End-to-end route using original inputs, re-import, and format and recovery tests. |
| Search, look up assets, install and verify packs | `pugc search`, `asset`, `doctor`, `fetch-pack`, `capabilities` | Bundled index, archive states, nine meshes, and full-pack verification. |
| Extract, preview, compare, and audit geometry | `pugc blender extract`, `preview`, `compare`, `audit` | Small source scene, valid map, incorrect tower, and repeat route audit. |
| Browser codec compatibility | `tools/pugc_portable.mjs` with pinned inputs and Node.js | Read, write, and compare decoded records. |

The checkout still provides `tools/ugc_project.py`, `validate_pugc.py`, `audit_route.py`, `compare_pugc.py`, `blender_extract_geometry.py`, `blender_preview_pugc.py`, and `check_toolkit.py` wrappers. `mesh_library.py`, `pugc_codec.py`, `ugc_geometry.py`, `ugc_raycast.py`, `ugc_storage.py`, and `ugc_validation.py` import the package implementation from the old paths. The base installation uses the bundled catalog and runs without lab data. [CLI reference](CLI.md) · [Installation](INSTALLATION.md)

[Local checks and GitHub Actions](CI.md)

## Lab tools from the checkout

| Input or workflow | Tools, dependencies, and outputs |
| --- | --- |
| Extract and export Source geometry | `extract_source_bsp.py INPUT OUTPUT_DIRECTORY` for BSP data, `bsp_material_manifest.py BSP OUT` for material references, `rasterize_geometry.py --mesh NPZ --out FILE` for rasterization, and `export_geometry_glb.py HTML --out-dir DIRECTORY` to read archived HTML layers and write GLB. Uses Python and NumPy, plus Numba for rasterization and trimesh for GLB export. |
| Experimental build from Source | `ugc_reconstructor.py` and `build_from_bsp.sh` use a BSP, meshes, and a style model. `vmf_to_pugc_corrected.py` builds approximate box elements from VMF. BSP needs NumPy, SciPy, and OpenSSL. VMF needs NumPy and OpenSSL. Set external map and report paths. [Reconstructor](BSP_RECONSTRUCTOR_README.md) |
| Prepare and open the lab scene | `prepare_assets.py`, `unpack_assets.py`, `prepare_overpass_blender_lab.py`, `build_overpass_blender_scene.sh`, `create_overpass_blender_lab.py`, `LAB_TOOLS.py`, `analyze_overpass_geometry.py`, `verify_overpass_lab.py`, `test_addon.py`. Use a prepared data directory and an external output. The scene needs Blender with NumPy. CPU analysis needs NumPy and SciPy. [Blender lab](BLENDER_GEOMETRY_LAB_README.md) |

The reconstructor and Blender lab preparation use the BSP parser in `tools/source_bsp.py`. `extract_source_bsp.py` saves parsed data for separate numerical workflows. `vmf_to_pugc_corrected.py` generates an approximate PUGC from VMF brush surfaces. [PUGC containers](PUGC_CODEC.md)

The lab minimum of 0.09 came from rounding the scale 0.091890335 of object 16051 in a research sample. The built-in Toolkit profile checks a minimum of 0.10 for new maps. Use the lab reconstructor's `--min-scale` to select 0.10 when comparing against the profile. [Origin of the limit](BSP_RECONSTRUCTOR_README.md#009-update)

## Recover historical files

Revision `c3ab056057d9eb04f401839619bbd35641c863e4` keeps `tools/legacy/generate_new_bsp.sh`, `tools/legacy/pugc_codec_base.py`, `tools/legacy/source_bsp.py`, `tools/fetch_missing_models.py`, `tools/merge_model_packs.py`, `tools/preview_overpass_lab.py`, `tools/render_vertigo_portable.py`, and `tools/ugc_material_lookup.py`. Use `pugc asset` to work with the full catalog and `pugc fetch-pack` to install assets.

```sh
mkdir -p "$UGC_WORK/archive/tools/legacy"
git -C "$UGC_TOOLKIT" show c3ab056057d9eb04f401839619bbd35641c863e4:tools/legacy/source_bsp.py \
  > "$UGC_WORK/archive/tools/legacy/source_bsp.py"
```

The historical Vertigo render used scene `examples/vertigo/Vertigo_UGC_Texture_Review_Portable.blend` from revision `2fd0956`. [Scene](https://github.com/dokerrrrr/pugcblender/blob/2fd0956befae752b0fa71dcf698a31eb2c75038c/examples/vertigo/Vertigo_UGC_Texture_Review_Portable.blend) · [Historical tools](https://github.com/dokerrrrr/pugcblender/tree/c3ab056057d9eb04f401839619bbd35641c863e4/tools) · [Archived lab inputs](UGC_WORKFLOW.md#recover-archived-files)
