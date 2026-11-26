#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"

usage() {
    echo "Usage: bash $0 INPUT.bsp OUTPUT.pugc [limit=3000] [--assets-dir DIR]"
}

case "${1:-}" in
    -h|--help) usage; exit 0 ;;
esac
if [ "$#" -lt 2 ]; then usage >&2; exit 2; fi
input="$1"
output="$2"
shift 2
limit=3000
assets="$ROOT/assets"
if [ "$#" -gt 0 ] && [ "$1" != "--assets-dir" ]; then
    limit="${1:-3000}"
    shift
fi
if [ "$#" -gt 0 ]; then
    if [ "$#" -ne 2 ] || [ "$1" != "--assets-dir" ]; then usage >&2; exit 2; fi
    assets="$2"
fi

python -B "$ROOT/tools/ugc_reconstructor.py" build --bsp "$input" --meshes "$assets/ugc_meshes_all.zip" \
    --model "$ROOT/reference/overpass/overpass_style_model.json" --output "$output" \
    --limit "$limit" --report "${output%.pugc}.report.json"
