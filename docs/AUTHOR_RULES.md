# PUGC map authoring rules

Build scenes from native objects using the shapes and finishes of existing faces. If a Blender reference is missing a material, use the silhouette and supplied frames. In previews, you may assign an existing native texture with a confirmed binding or show a neutral material. [Set dressing](../optional/blender-skills/pugc-set-dressing/SKILL.md)

Preserve imported fields and stable IDs. Update the project for visual edits and render the same viewpoint again from the saved map. In a flythrough, the external camera and, if needed, its target move. Store the camera path separately from the map. [Map rules](../AGENTS.md) · [Project format](UGC_FORMATS.md#editable-project) · [Flythroughs](../optional/blender-skills/pugc-camera-flyover/SKILL.md)

## Advice from archived projects

- **Aerodrome.** Keep the device and event counts at zero, including for smoke, lighting, and spawn points. When editing the roof, road, or terrain, reopen the rebuilt binary. Compare the west apron, courtyard, and end of H2 from the same cameras with and without textures. Then lower the camera to inspect thresholds and side entrances. [Aerodrome guide](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/projects/aerodrome/README.md)
- **Siege of Shanghai.** Check the separate house-category limit when replacing facades. Before adding a building, free enough placements for its entire assembly. Check which side of a sign faces the street camera. Review plazas, passages, and signs at pedestrian height, then review the roof and waterfront outline from the water and from above. [Shanghai guide](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/projects/shanghai/README.md)
- **Inferno.** When replacing an object, preserve the visible plane, its elevation, and its outward normal. A pivot difference can shift the slab edge or raise water above the rim. Check adjacent edges when moving slabs. [Inferno guide](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/projects/inferno/README.md)
- **Vertigo.** Check back-face visibility on floors, ceilings, and internal partitions. When snapping a placement to a plane, align the mesh's actual visible face with the target surface. [Face checks and snapping](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/projects/vertigo/build_surface_aware.py#L133-L206)

[Original AGENTS.md revision](https://github.com/dokerrrrr/pugcblender/blob/c3ab056057d9eb04f401839619bbd35641c863e4/AGENTS.md) · [Project archive](ARCHIVE.md)
