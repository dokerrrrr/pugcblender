# Toolkit release builds

The release contains a wheel, an sdist, SHA-256 checksums, complete file lists, and migration instructions. `manifest.json` records the exact source commit and Toolkit version. The project uses `schema: 1` and the container is PUGC v3. [Formats](UGC_FORMATS.md)

## Reproduce the build

From a clean checkout, install `build==1.6.1` and `setuptools==84.2.1` in the build environment. Choose a new artifact directory outside the checkout.

```sh
python -B tools/build_release.py --ref HEAD --out "$UGC_WORK/release-1.0.1"
(
  cd "$UGC_WORK/release-1.0.1"
  sha256sum -c SHA256SUMS
)
```

The build exports the Git tree, fixes archive timestamps, checks the project version and package metadata, and verifies the contents. It moves the output files into place together after verification. Use the same commit and build environment to reproduce the SHA-256 checksums.

## Acceptance and limitations

| Check | Status |
| --- | --- |
| Quick commands, installation, re-import, and formats | Python 3.11/3.12 matrix and README workflows. Local checks used Python 3.11.18, 3.12.14, and OpenSSL 3.5.7. |
| Offline geometry and binary format | Blender 4.3.2, Node.js 24.22.1, and nine pinned meshes. Local integration reports include geometry differences, skipped checks, and SHA-256 hashes. |
| Flythrough | FFmpeg 7.1.5 wrote H.264 MP4 in the verification run. |
| Full mesh and texture pack | The manifest verifies 741 mesh-and-card pairs and 3,092 WEBP images. Supply the pack separately. |
| PUBG UGC client | Two maps, checksums, the protocol, and an offline preview are ready. Opening, re-saving, and recording observations in the target client build are scheduled for the next release. [Client acceptance](PUBG_CLIENT_ACCEPTANCE.md) |
| GitHub release | The draft records the exact commit, artifacts, manifest, hashes, verified workflows, and CI reports. |

[Local CI](CI.md) · [Migration](MIGRATION.md) · [Provenance](PROVENANCE.md)
