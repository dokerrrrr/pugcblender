---
name: pugc-visual-review
description: Repeat a visual check of a static PUGC map against a reference from player height and above, before and after a correction.
---

# Visually review the saved map

1. Open the saved `.pugc` with its matching `.pugc.json` and native meshes. Choose a wide view, an approach to the landmark, and a view from player height. Save camera position, field of view, and lighting for repeat captures.
2. First review the silhouette, terrain contact, gaps, and platform edges with a neutral material. Repeat with existing game textures. Paired comparison through `pugc blender compare -- …` supports `--mode geometry` and `--mode textured --textures "$UGC_ASSETS/PUGC_Textures_Ready.zip"`. Use the NPZ, map, camera, and output arguments from the [end-to-end example](../../../README.md#end-to-end-example-with-nine-meshes).
3. If a surface is blank, check the face and binding entry. Report `confirmed`, `name_similarity`, `missing_binding`, and image-load errors distinctly. Do not generate or bake a replacement or use object animation to correct the view.
4. For each significant defect, record the viewpoint, object or assembly, observed defect, and result of the recheck. Fix placements in the project and reopen the saved binary. Repeat the geometry test for a blocked passage and the same camera frame for a hidden landmark.
5. Record what was reviewed visually, what was measured with native meshes, and whether you ran a PUBG client test. Verify walkability in the client.

[Map rules](../../../AGENTS.md) · [Original guide](https://github.com/arjun988/blender-skills/blob/904f095d8f36a6e72adaebb08d07f884a074743d/.claude/skills/qa-review/SKILL.md) · [MIT license](../LICENSE)
