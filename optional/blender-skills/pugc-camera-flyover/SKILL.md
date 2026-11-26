---
name: pugc-camera-flyover
description: Create an overview video from a completed PUGC map with smooth external camera motion and static game objects.
---

# Flythrough of a static map

1. Reopen the final `.pugc` with its JSON sidecar. Plan an establishing view, a pass over the main landmark, and a closing wide shot. Check the horizon, silhouette, and street visibility at the start, turns, and end.
2. Store the path in the preview scene or a separate camera file. `pugc blender compare -- … --flythrough` requires at least two perspective cameras in the source NPZ with matching optics and resolution. List cameras in travel order with `--cameras`, set the MP4 path with `--flythrough`, and choose the frame rate with `--fps`. The [Inferno project](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/projects/inferno/camera.json) contains an example of a separate path.
3. Move only the camera and, if needed, its target from frame to frame. Keep props, vegetation, water, and architecture in place. Do not add moving objects, animated shaders, simulations, or new textures for the video.
4. Review frames between control points, especially near roofs and arches. If the camera crosses a wall, adjust the path. If the map has a defect, fix the project, rebuild, and record again. Verify MP4 decoding, duration, resolution, and the map version used.

[Map rules](../../../AGENTS.md) · [Original guide](https://github.com/arjun988/blender-skills/blob/904f095d8f36a6e72adaebb08d07f884a074743d/.claude/skills/camera-cinematography/SKILL.md) · [MIT license](../LICENSE)
