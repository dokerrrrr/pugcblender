# Toolkit checks

The `PUGC checks` workflow runs quick checks on Python 3.11 and 3.12 and verifies installation from both the wheel and sdist. It runs on pull requests, `v*` tags, and manual dispatch.

The quick job installs a wheel from the exported tree, checks local links and anchors, and runs both README Bash blocks in an external directory. The two large archives in the checkout use 134-byte LFS pointers. Only the skips enumerated in code for optional tools or inputs are allowed.

## Run locally

Set up a clean environment with Python 3.11 or 3.12, OpenSSL, and NumPy for tests. Build and install the wheel from the exported tree, then run these commands from a checkout. [Installation](INSTALLATION.md)

The local integration check also needs Blender, Node.js 24, and a directory containing `mod_main_level.glb`, `route-meshes.zip`, `codec/pugc-codec-client.js`, and `codec/aes256-ecb.js`. It checks hashes and builds the source scene and NPZ in Blender. It checks the valid map, the wrong side of Tower from two cameras, an incomplete audit, a corrupted sidecar, and a publication failure. An undetected defect, a skipped required test, or a checkout modification fails the run. [Geometry checks](GEOMETRY_QA.md)

```sh
python -B tests/ci_acceptance.py quick --work "$UGC_WORK/ci-quick"
export PUGC_ASSET_DIR=/path/to/local-fixtures
python -B tests/ci_acceptance.py integration --work "$UGC_WORK/ci-integration"
```

The integration run revalidates the local cache. The working directory records versions, input SHA-256 hashes, test results, checkout cleanliness, maps, frames, reports, and logs.

Package verification builds the wheel and sdist from the exact PR branch or release tag SHA. After installing both packages and running the two README workflows, CI uploads the archives and manifest as a run artifact.

To verify the full pack locally, restore both pinned archives to your asset directory and run `pugc doctor --mode full`. [Retrieve and verify assets](RESOURCES.md)
