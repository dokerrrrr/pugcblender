# Build and verify PUGC maps

Keep your project, saved map, and JSON sidecar in your working directory. Start an existing map with `pugc import`. For a new map use `pugc init`, adding `--template PATH` if you have a template from your client. The Toolkit copies the template settings and metadata and starts with an empty placement list. [Quick start](../README.md#agent-workflow) · [Project format](UGC_FORMATS.md)

When transferring a scene, use the reference geometry and cameras to build a representative section. Select models by the shape and dimensions of the whole object. Group complex structures into assemblies and give each instance a stable ID. [Find models](CATALOG.md) · [Edit by ID](BATCH_EDIT.md)

## Source scenes, frames, and routes

All `.pugc` files open in the same game location with an island and water. Editor terrain spans game X/Y 0–1,020 m, including the seabed. A flat pad near game X 510 m and Y 510 m lies at 10.64 m elevation. At the default `origin_x_cm`, its authoring X is about 490 m. `place --at` sets the pivot in authoring meters. For another reflection origin, the pad's authoring X is `2 * origin_x_cm / 100 - 510`. Account for the terrain shape and the bottom of the model. [PUGC Scene Editor](https://plzdntkilmeh.github.io/pugc-editor/scene-editor.html)

Blender and the Overpass labs place the island at the same game coordinates. Water stays at Z = 0 m. Run `pugc fetch-pack full` to install the island, meshes, and textures in the shared cache. Pass `--base-level PATH` to use a verified local GLB. [Local assets](RESOURCES.md)

`validate` rereads the saved map and checks structure, object IDs, numeric values, and limits. After editing placements, preview the saved map itself. Check placement relative to the shore, terrain contact, height above water, joins, and passages.

```sh
pugc blender preview -- --pugc "$UGC_WORK/map.pugc" --out "$UGC_WORK/preview.png"
```

The preview frames placed objects by default. `--frame island` shows the island, and `--frame all` includes both the island and the placements. A map without objects shows the island. `--view top` shows the view from above. Add `--mode textured` to apply available native textures. `--save-blend PATH` saves the scene in authoring meters and packs the textures used in a textured preview.

Compare a Blender reference with the saved map in one command. The comparison uses the same camera for each pair and records material coverage in `comparison.json`.

```sh
pugc blender compare -- "$UGC_WORK/source.blend" "$UGC_WORK/map.pugc" \
  --mode textured --out "$UGC_WORK/frames"
```

Check joins and visibility along a route with `audit` and project annotations. If you find a discrepancy, fix the project, rebuild the map, and render the same view. For a flythrough, run `compare --flythrough PATH` with FFmpeg and at least two perspective cameras. Confirm collisions and walkability in the PUBG client. [Blender commands](CLI.md#blender-geometry) · [Cameras and route checks](GEOMETRY_QA.md) · [Blender skills](../optional/blender-skills/README.md)

## End-to-end example with nine meshes

Install `pugc` and set absolute paths for the checkout and working directory. This example needs a local island, nine meshes, and Blender with NumPy. It builds an original entrance with a gate from native game pieces, rotates one bench, and writes an intentionally incorrect variant with the tower on the right. It also creates an overpass to check visibility.

```sh
UGC_TOOLKIT="/path/to/PUBG UGC Toolkit"
UGC_WORK="$HOME/PUBG Maps/Sample Route"
mkdir -p "$UGC_WORK"
pugc fetch-pack full
pugc fetch-pack small --out "$UGC_WORK/meshes.zip"
blender -b -t 4 --python-exit-code 1 --python "$UGC_TOOLKIT/examples/ugc_route/create_source.py" -- "$UGC_WORK/source.blend"
python "$UGC_TOOLKIT/examples/ugc_route/prepare.py" "$UGC_WORK"
pugc validate "$UGC_WORK/route.pugc"
pugc blender --threads 4 compare -- "$UGC_WORK/source.blend" "$UGC_WORK/route.pugc" --project "$UGC_WORK/route.json" --meshes "$UGC_WORK/meshes.zip" --out "$UGC_WORK/frames"
pugc blender --threads 4 audit -- "$UGC_WORK/overpass.pugc" --project "$UGC_WORK/overpass.json" --meshes "$UGC_WORK/meshes.zip" --out "$UGC_WORK/overpass-audit.json"
```

Pass `wrong-tower.pugc` to the comparison command and choose a different `--out`. The report should identify `Tower` in `Approach` and `Alongside`. Exit code 2 indicates a geometry check failure. After removing the hidden tire, run the audit again with `overpass-clean.pugc` and `overpass-clean.json`. [Acceptance frames and files](https://github.com/dokerrrrr/pugcblender/tree/c3ab056057d9eb04f401839619bbd35641c863e4/examples/ugc_route/evidence)

## Assets and labs

The base installation supports asset search and map building. For frames, supply a ZIP with the required meshes. Use `pugc fetch-pack small` for the sample route or `pugc fetch-pack full-meshes` for the full mesh pack. Color frames can use native textures from a separate ZIP. [Retrieve assets](RESOURCES.md)

Specialized workflows use the external working directory `UGC_WORK`, repository path `UGC_TOOLKIT`, and asset ZIP directory `UGC_ASSETS`. [BSP reconstruction](BSP_RECONSTRUCTOR_README.md) · [Blender lab](BLENDER_GEOMETRY_LAB_README.md)

## Recover archived files

Sample maps and tutorial frames are available at their original paths. The earlier ZIP also contains the original Vertigo BSP, `reference/overpass/overpass_geometry_lab.html`, `overpass_bsp_aligned.glb`, and `overpass_vmf_aligned.glb`. [Map archive and Git commands](ARCHIVE.md) · [Earlier ZIP](https://github.com/dokerrrrr/pugcblender/archive/2fd0956befae752b0fa71dcf698a31eb2c75038c.zip)
