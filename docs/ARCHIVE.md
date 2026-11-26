# Sample project archive

Access to the private repository is required. Revision `c3ab056057d9eb04f401839619bbd35641c863e4` keeps all four projects at their original paths. The earlier revision `2fd0956befae752b0fa71dcf698a31eb2c75038c` contains older examples in `examples/`, the source Vertigo BSP, and the lab's HTML and GLB. Use `c3ab056` for the four projects below. [Project tree](https://github.com/dokerrrrr/pugcblender/tree/c3ab056057d9eb04f401839619bbd35641c863e4/projects) · [Earlier archive](https://github.com/dokerrrrr/pugcblender/tree/2fd0956befae752b0fa71dcf698a31eb2c75038c)

| Archived tree | Files | Bytes | Main inputs and outputs |
| --- | ---: | ---: | --- |
| `projects/aerodrome` | 16 | 5,912,962 | Owner's map, pre-edit map and annotations, generator, rays and clearance reports, overview, and video. |
| `projects/inferno` | 11 | 4,901,943 | PUGC, compressed project, annotations, geometry report, waypoints, cameras, overview, and video. |
| `projects/shanghai` | 9 | 3,575,028 | PUGC, compressed project, annotations, bridge checks, overview, and video. |
| `projects/vertigo` | 27 | 9,198,607 | PUGC, BSP classification, template, face data, texture samples, two Blender scenes, and a report. |
| Total in `projects/` | 63 | 23,588,540 | All four projects. |
| Root `Vertigo_Optimized_Face_Aware_V2.pugc` | 1 | 32,581 | Byte-for-byte copy of the file under `projects/vertigo/`. |
| `examples/ugc_route/evidence` | 15 | 774,018 | Earlier frames, scenes, maps, videos, and reports from one tutorial. |

Compressed Inferno and Shanghai projects use the older authoring coordinates without `layout_version`. To make a fresh edit to an archived map, import the original `.pugc` and its sidecar with the current Toolkit. To build an older JSON project with existing edits, use compatibility with `game_original`. [Migration](MIGRATION.md)

```sh
UGC_ARCHIVE="$UGC_WORK/Map Archive"
mkdir -p "$UGC_ARCHIVE"
git -C "$UGC_TOOLKIT" archive c3ab056057d9eb04f401839619bbd35641c863e4 \
  projects examples/ugc_route/evidence Vertigo_Optimized_Face_Aware_V2.pugc |
  tar -x -C "$UGC_ARCHIVE"
sha256sum "$UGC_ARCHIVE/projects/aerodrome/Aerodrome.pugc"
```

The recovered owner's Aerodrome file has SHA-256 `0caf69e0af4fa6c5a114505a60242d0fa0383f7edcf6b656603ffe11f3cd9a1c`. The compressed Shanghai and Inferno projects, Vertigo classification and template, and all other files in `projects/` were also checked. To recover one file, redirect `git -C "$UGC_TOOLKIT" show REVISION:PATH` into your working directory.

Generators in `examples/ugc_route` create fresh tutorial inputs and outputs in the working directory. Shared native-mesh measurements live in `pugc_toolkit/ugc_raycast.py`. `reference/overpass` contains inputs for a separate lab. The earlier generated PUGC and material reports are available at `c3ab056`. [End-to-end tutorial](UGC_WORKFLOW.md#end-to-end-example-with-nine-meshes) · [Lab tools](TOOLS.md)
