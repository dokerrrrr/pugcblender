# Provenance and package contents

| Material | Source and terms | Location |
| --- | --- | --- |
| Toolkit code and project guides | The original private repository. The Toolkit code has no separate license file. Access to verification artifacts follows repository access. | Source tree, wheel, and sdist. |
| Four adapted Blender skills | Guides from `arjun988/blender-skills` pinned to `904f095d…`. Source links and the original MIT license are included. | `optional/blender-skills` in the checkout. [License](../optional/blender-skills/LICENSE) · [Attribution](../optional/blender-skills/README.md) |
| Placement profile, model index, and texture mappings | Editor metadata comes from the pinned revision `3bd69a10c3ad9ebe8f9aa44964a36784b7bce29b`. Measurements and candidate mappings were compiled in this project. The reviewed editor revision had no separate root license. Confirm permissions for the applicable material before external distribution. | Catalog JSON in the private verification package. [Editor revision](https://github.com/PlzDntKilMeh/pugc-editor/tree/3bd69a10c3ad9ebe8f9aa44964a36784b7bce29b) |
| PUBG meshes and textures | Full ZIPs with Git LFS checksums and a small pack checked against hashes for nine editor entries. Asset packs are stored separately. Supply a local copy you can access. | [Manifest](../catalog/pack_contents.json) · [Retrieval and verification](RESOURCES.md) |
| Browser codec, user maps, frames, and scenes | The JS codec uses the same pinned editor revision for verification. Archived user projects and visual materials retain their original paths in Git. | CI inputs and private repository archives. [CI](CI.md) · [Archive](ARCHIVE.md) |

The sdist includes this inventory. The release build checks the manifest and the contents of both artifacts. Confirm the distribution terms for the included materials and the repository access level for each release. [Release builds](RELEASE_PREFLIGHT.md)
