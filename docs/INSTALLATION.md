# Install PUGC Toolkit

The package supports Python 3.11 and later. The installed `pugc` command and `python -m pugc_toolkit` expose the same CLI. The package includes a neutral template, the placement profile, and indexes. The historical coordinate table supports older projects. Search and catalog entries work with the base installation. `init --template`, `init --version-from`, `import`, `build`, and binary validation use `openssl` from `PATH` to read and write the container. [Coordinate transforms](PUGC_CODEC.md)

## Build the wheel and sdist

Build the artifacts from a separate copy of the source. Substitute absolute paths to the checkout and build directory. These commands use the files at `HEAD`.

```sh
UGC_TOOLKIT="/path/to/checkout"
UGC_BUILD="/path/to/package-build"
mkdir -p "$UGC_BUILD/source" "$UGC_BUILD/dist"
git -C "$UGC_TOOLKIT" archive HEAD MANIFEST.in README.md pyproject.toml catalog pugc_toolkit |
  tar -x -C "$UGC_BUILD/source"
python -m venv "$UGC_BUILD/builder"
"$UGC_BUILD/builder/bin/python" -m pip install build
"$UGC_BUILD/builder/bin/python" -m build --outdir "$UGC_BUILD/dist" "$UGC_BUILD/source"
```

Install the wheel or sdist into your chosen environment. The sdist requires the build dependencies in `pyproject.toml`. Use a separate directory for your map project.

```sh
python -m pip install "$UGC_BUILD/dist/pubg_ugc_toolkit-1.0.0-py3-none-any.whl"
pugc --version
pugc --help
pugc search wall --limit 3
```

## Optional dependencies

- OBJ export and exact measurements from ZIP archives use NumPy. Install the package with the `[geometry]` extra and pass the mesh archive through `--meshes`.
- To extract thumbnails or render textured Blender previews, install the native assets with `pugc fetch-pack full`. Use `--textures` to select a different ZIP. [Assets](RESOURCES.md)
- The `[research]` extra installs NumPy, SciPy, and Shapely for research workflows from the checkout. The repository holds the specialized scripts and inputs.

```sh
python -m pip install "$UGC_BUILD/dist/pubg_ugc_toolkit-1.0.0-py3-none-any.whl[geometry]"
pugc asset 12005 --meshes /path/to/meshes.zip --obj /path/to/12005.obj
```

## Blender

`pugc blender` starts an installed Blender with its own Python and NumPy, then passes it the installed Toolkit path. For PUGC checks, Blender inherits `PATH` with OpenSSL. Flythrough output also uses FFmpeg. If Blender is outside `PATH`, select it with `--blender`.

Put Blender launch options before the operation. Pass the operation's arguments after `--`. For `extract`, supply the source scene with `--blend`. Pass the source `.blend` or extracted NPZ directly to `compare`. Comparison, audit, and preview use the mesh ZIP in the shared asset cache by default.

```sh
pugc blender --blend /path/to/source.blend extract -- --out /path/to/source.npz
pugc blender compare -- /path/to/source.npz /path/to/map.pugc \
  --project /path/to/project.json --meshes /path/to/meshes.zip --out /path/to/frames
pugc blender audit -- /path/to/map.pugc \
  --project /path/to/project.json --meshes /path/to/meshes.zip --out /path/to/audit.json
```

During the transition to 1.0, `python tools/ugc_project.py`, `python tools/validate_pugc.py`, and `blender --python tools/…` remain available from the checkout. They call the same implementation. [Verification commands](UGC_WORKFLOW.md)
