# Working with PUBG UGC maps

**Explicit requests required:** Do not add gameplay devices or configure map settings unless the user explicitly requests that specific action. A general request to create, edit, or improve a map does not authorize either action. Preserve existing devices and map settings unless the user explicitly asks to change them.

The client opens a `.pugc` on a shared map with the starting island and water. The file defines the placed objects and map settings. Compose around the terrain and shoreline, cover the island with scene geometry, face away from it, or build a separate scene above the water.

The terrain spans game X/Y coordinates from 0 to 1,020 m, including the seabed. There is a flat pad near game X 510 m and Y 510 m at an elevation of 10.64 m. With the default authoring origin, this corresponds to X 490 m and Y 510 m in `place --at`. Account for the bottom of the mesh when choosing Z. The editor grid fixes the water level at Z = 0 m. [Island and grid in the editor](https://plzdntkilmeh.github.io/pugc-editor/scene-editor.html)

- Use finishes from existing faces of native game models. Creating, generating, painting, or baking textures, adding new game materials or decals, and reworking UVs are prohibited. If a reference model is missing a material, use its shape and the other frames. For a preview, you may assign an existing native texture to its surface. When the binding is unverified, document your confidence or show a neutral material.
- Map objects are static. Do not add motion keyframes, rigs, drivers, simulations, or material animation, including for presentation videos. In a flythrough, only the external camera and, if needed, its target move. Store the camera path separately from the map.
- Keep full houses and other enterable buildings at native scale wherever possible so doors, rooms, and passages stay familiar. If an exception is justified, check entrances and interior passages at player height. Individual building pieces and decorative objects may be scaled.

1. Work in a separate directory with a Toolkit build from the current checkout. Use `pugc init` for a new map and `pugc import` on the original `.pugc` for an existing map. New projects use `layout_version: 2`. Specify placements relative to each model's native pivot. Preserve imported fields, devices, events, and the owner's manual edits unless the user explicitly requests a change.
2. Find native `objectId` values with `search` and `asset`, then assemble complex shapes from multiple placements. For static maps, add only geometry unless the user explicitly requests devices.
3. Build the map with `pugc build` and check the written file with `pugc validate`. Keep the `.pugc` and its adjacent `.pugc.json` together.
4. When you create or rearrange a scene, inspect a frame from the saved `.pugc` using `pugc blender preview`. Check terrain contact, height above water, joins, and passages. `--frame all` frames the scene with the island. When using a reference, compare matching viewpoints. Correct placements in the project.

[Quick start](README.md#agent-workflow) · [Catalog](docs/CATALOG.md) · [Batch editing](docs/BATCH_EDIT.md) · [Preview](docs/UGC_WORKFLOW.md#source-scenes-frames-and-routes)

For changes to the Toolkit itself, see the [development guide](docs/DEVELOPMENT.md).
