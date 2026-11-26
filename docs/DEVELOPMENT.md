# Develop PUBG UGC Toolkit

Use this guide when changing Toolkit code, formats, assets, or the release process. Use the quick start for building and editing maps. [Authoring workflow](../README.md#agent-workflow)

## Checks and releases

Run checks from the checkout with the Toolkit installed. `quick` checks documentation, runs the README examples, and verifies hashes of the resulting map-and-sidecar pairs. Run `integration` locally with Blender, Node.js, and pinned fixtures. Set `PUGC_ASSET_DIR` to the local fixture directory. Keep verification outputs outside the checkout. [Install from source](INSTALLATION.md#build-the-wheel-and-sdist) · [CI checks](CI.md)

```sh
python -B tests/ci_acceptance.py quick --work "$UGC_WORK/ci-quick"
python -B tests/ci_acceptance.py integration --work "$UGC_WORK/ci-integration"
```

To run only unit tests, use `python -B -m unittest discover -s tests -v`. To run with prepared inputs, set `UGC_TEST_MESHES`, `UGC_TEST_SOURCE_NPZ`, and `UGC_TEST_JS_CODEC`. `integration` prepares the inputs and sets these variables itself. CI verifies installation from both wheel and sdist. Use `pugc doctor --mode full` to verify a locally supplied asset pack. [Asset manifest](../catalog/pack_contents.json) · [Release builds](RELEASE_PREFLIGHT.md) · [Client acceptance procedure](PUBG_CLIENT_ACCEPTANCE.md)

## Profile and template

The bundled budget profile is pinned to editor revision `3bd69a10c3ad9ebe8f9aa44964a36784b7bce29b`. Categories and weights are mapped to the object and device catalog. Editor limits are marked `manual-ingame-observed`. This profile checks the minimum scale of 0.10 and hundredth-place precision. `available_after_road_and_shoulder` reports the remaining budget after roads and shoulders, while `remaining` accounts for all placements. An unknown ID marks the budget as incomplete. [Profile](../catalog/placement_profile.json) · [Data provenance](PROVENANCE.md)

The neutral v3 template contains `name`, `dataVersion`, `buildVersion`, `objects`, `deviceEventList`, and `editFileData`. The fallback `buildVersion` is `2611.1.2`. `init --version-from` copies only `buildVersion` and checks container and `dataVersion` compatibility. The initial tag is `MainTag_None`, the object, event, and rule lists are empty, and `modUserSelectPlayType` is `NONE`. `init` fills the name and time for a new project. With `--template`, it takes build and profile fields from a saved map and clears placements, devices, and known links. [Template](../catalog/pugc_v3_empty.json) · [Editor save code](https://github.com/PlzDntKilMeh/pugc-editor/blob/3bd69a10c3ad9ebe8f9aa44964a36784b7bce29b/scene-editor/project-files.js) · [Coordinate transforms](PUGC_CODEC.md)

## Verify the starting location

The published editor loads `cache/mod_main_level.glb` and adds it with its original transforms. `prepareBakedLevelScene` enables double-sided materials. The published GLB has 17 nodes, including eight terrain pieces and nine rock instances. The geometry includes the seabed. GLB coordinates in meters map to (game X, game Z, game Y). The full model spans 0–1,020 m on X/Y and approximately −204.19 to 17.31 m on Z. [Scene loader](https://plzdntkilmeh.github.io/pugc-editor/scene-editor.js) · [GLB processing](https://plzdntkilmeh.github.io/pugc-editor/scene-editor/terrain-utils.js)

The published GLB and pinned copy share SHA-256 `e72dbad55c8c1499ad899b9e50707a0c657952c60024b94a21043fd15d7540dd`. [Published GLB](https://plzdntkilmeh.github.io/pugc-editor/cache/mod_main_level.glb) · [Pinned copy](https://github.com/PlzDntKilMeh/pugc-editor/blob/3bd69a10c3ad9ebe8f9aa44964a36784b7bce29b/cache/mod_main_level.glb)

The web editor adds a world grid, `THREE.GridHelper(4000, 400, …)`, directly to the scene. In Three.js r168, grid vertices lie on Y = 0, and `ue4PosToThree` maps game Z to Y height. The grid sits at game Z = 0 m. The Toolkit uses it as the fixed water level. Reports record `water_z_m = 0` and `water_z_source = scene_editor_grid`. [Scene grid code](https://plzdntkilmeh.github.io/pugc-editor/scene-editor.js) · [GridHelper vertices](https://github.com/mrdoob/three.js/blob/r168/src/helpers/GridHelper.js#L22-L23) · [Axis transform](https://github.com/PlzDntKilMeh/pugc-editor/blob/3bd69a10c3ad9ebe8f9aa44964a36784b7bce29b/scene-editor/coords.js#L30-L32)

The Toolkit checks the size and hash of the local GLB from `--base-level`, `PUGC_ASSET_DIR`, or an existing cache at `$XDG_CACHE_HOME/pugc-toolkit` or `~/.cache/pugc-toolkit`. Blender imports the GLB into XYZ. The Toolkit converts it into game or authoring coordinates and uses the same space for water. [Source and settings](../pugc_toolkit/base_level.py) · [Blender transform](../pugc_toolkit/blender_base_level.py)

## Cross-check with Node.js

Use Node.js 22 or later with `CompressionStream("deflate-raw")` and both codec modules from the local fixtures. The codec accepts JSON in game coordinates, such as the example's `route-game.json` or JSON decoded from an existing file. [Local fixtures](CI.md#run-locally)

```sh
node "$UGC_TOOLKIT/tools/pugc_portable.mjs" decode "$PUGC_ASSET_DIR/codec/pugc-codec-client.js" "$UGC_WORK/route.pugc" "$UGC_WORK/route-game.json"
node "$UGC_TOOLKIT/tools/pugc_portable.mjs" encode "$PUGC_ASSET_DIR/codec/pugc-codec-client.js" "$UGC_WORK/route-game.json" "$UGC_WORK/route-copy.pugc"
```

## Benchmark batch editing

`PYTHONPATH=. python -B tests/benchmark_batch_edit.py` creates two 3,000-instance projects in a temporary directory. It changes the assemblies of 100 instances. The first run applies 100 single-operation requests and the second applies one request with all operations. The script measures elapsed time and the number of atomic writes, then checks that the projects match byte for byte.
