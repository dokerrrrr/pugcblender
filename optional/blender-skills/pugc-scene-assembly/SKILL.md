---
name: pugc-scene-assembly
description: Place static architecture from the PUBG catalog using a Blender model, floor plan, or reference frames.
---

# Assemble a site from a reference

1. Select an area with a recognizable landmark and a passage. Measure street width, entrance height, floor level changes, and the landmark's position relative to the route in the source scene. Record the coordinate alignment and one reproducible viewpoint.
2. Find candidates with `pugc search` and `pugc asset`. Check actual model geometry, dimensions, and the visible face. Place the main structural volumes first and walk the route at player height, then add frames and small details.
3. Group one building's parts in a named `assembly`. Keep a separate stable `id` for each instance. When editing an existing map, change only the intended assembly and preserve approved road sections.
4. Build the area with `pugc build`, check the budget with `pugc validate`, and reread the binary. Compare the silhouette and clearances from the original viewpoint before reusing the assembly.

If no complete asset fits, build the shape from static catalog pieces. Keep reference Blender materials and animations out of the map. Do not create textures or animate props.

[Map rules](../../../AGENTS.md) · [Original guide](https://github.com/arjun988/blender-skills/blob/904f095d8f36a6e72adaebb08d07f884a074743d/.claude/skills/scene-assembly/SKILL.md) · [MIT license](../LICENSE)
