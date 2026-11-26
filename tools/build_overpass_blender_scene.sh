#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
    echo "Usage: bash $0 OUTPUT.blend [--assets-dir DIR] [--data-dir DIR] [--base-level GLB]"
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
    ""|-*) usage >&2; exit 2 ;;
esac
output="$1"
shift
assets="$ROOT/assets"
data="$ROOT/reference/overpass"
environment=()
while [ "$#" -gt 0 ]; do
    if [ "$#" -lt 2 ]; then usage >&2; exit 2; fi
    case "$1" in
        --assets-dir) assets="$2" ;;
        --data-dir) data="$2" ;;
        --base-level) environment=("$1=$2") ;;
        *) usage >&2; exit 2 ;;
    esac
    shift 2
done

mesh_dir="$(mktemp -d)"
trap 'rm -rf -- "$mesh_dir"' EXIT
python "$ROOT/tools/prepare_assets.py" --overpass --assets-dir "$assets" --data-dir "$data" --out "$mesh_dir"
"${BLENDER:-blender}" --background --python-exit-code 1 --python "$ROOT/tools/create_overpass_blender_lab.py" -- \
    --data-dir "$data" --meshes "$mesh_dir/overpass_ugc_meshes.zip" --output "$output" --no-render "${environment[@]}"
