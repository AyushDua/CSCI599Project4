#!/usr/bin/env bash
set -euo pipefail

# Install into repo-local .tools/ so everyone is consistent.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
mkdir -p "$TOOLS_DIR"

# Detect macOS arch string expected by wasi-sdk releases.
ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  WASI_ARCH="arm64"
elif [[ "$ARCH" == "x86_64" ]]; then
  WASI_ARCH="x86_64"
else
  echo "Unsupported arch: $ARCH"
  exit 1
fi

WASI_OS="macos"

# Get latest WASI SDK major version number from GitHub API (e.g., wasi-sdk-27).
LATEST_TAG="$(curl -s https://api.github.com/repos/WebAssembly/wasi-sdk/releases/latest | \
  python3 -c "import sys, json; print(json.load(sys.stdin)['tag_name'])")"

# Extract the numeric version from tag: "wasi-sdk-27" -> "27"
WASI_VERSION="${LATEST_TAG#wasi-sdk-}"
WASI_VERSION_FULL="${WASI_VERSION}.0"

TARBALL="wasi-sdk-${WASI_VERSION_FULL}-${WASI_ARCH}-${WASI_OS}.tar.gz"
URL="https://github.com/WebAssembly/wasi-sdk/releases/download/${LATEST_TAG}/${TARBALL}"

echo "Latest tag: $LATEST_TAG"
echo "Downloading: $URL"

cd "$TOOLS_DIR"
curl -L -o "$TARBALL" "$URL"
tar -xzf "$TARBALL"

# Find extracted folder
WASI_SDK_PATH="$(find "$TOOLS_DIR" -maxdepth 1 -type d -name "wasi-sdk-*" | head -n 1)"
echo "Installed WASI SDK at: $WASI_SDK_PATH"

# Write env file used by scripts (no shell assumptions)
cat > "$TOOLS_DIR/env.sh" <<EOF
export WASI_SDK_PATH="$WASI_SDK_PATH"
export PATH="\$WASI_SDK_PATH/bin:\$PATH"
EOF

echo "Done. Next: source .tools/env.sh (scripts do this automatically)."