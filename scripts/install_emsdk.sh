#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
mkdir -p "$TOOLS_DIR"

EMSDK_DIR="$TOOLS_DIR/emsdk"

if [[ ! -d "$EMSDK_DIR" ]]; then
  echo "Cloning emsdk..."
  git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
else
  echo "emsdk already exists; updating via git pull (recommended for git-clone installs)"
  (cd "$EMSDK_DIR" && git pull)
fi

cd "$EMSDK_DIR"

# If installed via git clone, prefer update-tags rather than emsdk update
./emsdk update-tags

# Install + activate toolchain
./emsdk install latest
./emsdk activate latest

# Create env shim used by other scripts
cat > "$TOOLS_DIR/emsdk_env.sh" <<EOF
# Helper sourced by project scripts
source "$EMSDK_DIR/emsdk_env.sh"
EOF

echo "Emscripten installed. Env shim written to: $TOOLS_DIR/emsdk_env.sh"

# Optional sanity check in this script:
# shellcheck disable=SC1091
source "$TOOLS_DIR/emsdk_env.sh"
emcc -v