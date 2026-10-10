#!/usr/bin/env bash
# Regenerates the PNG icons of the barista panel from app/web/public/favicon.svg:
#   favicon-32.png, apple-touch-icon.png (180), icon-192.png, icon-512.png.
# The PNGs are committed; run this only after favicon.svg changes:
#   ci/make-web-icons.sh
# Needs Node (npx downloads sharp-cli, pinned below) and network access once.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PUBLIC_DIR="${REPO_ROOT}/app/web/public"
SOURCE="${PUBLIC_DIR}/favicon.svg"
SHARP_CLI="sharp-cli@6.1.0"

[ -f "$SOURCE" ] || { echo "make-web-icons: no ${SOURCE}" >&2; exit 1; }

# iOS rounds the corners itself and paints transparent pixels black, so the
# touch icon is rendered from a square (rx=0) copy of the logo.
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"' EXIT
sed 's/rx="14"/rx="0"/' "$SOURCE" >"${WORK}/square.svg"

render() { # <input.svg> <size> <output.png>
  npx --yes "$SHARP_CLI" -i "$1" -o "$3" resize "$2" "$2"
}

render "$SOURCE" 32 "${PUBLIC_DIR}/favicon-32.png"
render "${WORK}/square.svg" 180 "${PUBLIC_DIR}/apple-touch-icon.png"
render "$SOURCE" 192 "${PUBLIC_DIR}/icon-192.png"
render "$SOURCE" 512 "${PUBLIC_DIR}/icon-512.png"

ls -l "${PUBLIC_DIR}"/*.png
echo "OK: icons regenerated"
