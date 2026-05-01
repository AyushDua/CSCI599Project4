#!/usr/bin/env bash
set -euo pipefail

# Install into repo-local .tools/ so everyone is consistent.
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
mkdir -p "$TOOLS_DIR"

# Detect python — try python first, verify it actually runs (Windows Store
# stub reports as found but exits 49 without executing anything).
PYTHON="${PYTHON:-}"
if [[ -z "$PYTHON" ]]; then
  if command -v python >/dev/null 2>&1 && python -c "" >/dev/null 2>&1; then
    PYTHON="python"
  elif command -v python3 >/dev/null 2>&1 && python3 -c "" >/dev/null 2>&1; then
    PYTHON="python3"
  else
    echo "python not found on PATH"
    exit 2
  fi
fi

# Detect arch string expected by wasi-sdk releases.
ARCH="$(uname -m)"
if [[ "$ARCH" == "arm64" ]]; then
  WASI_ARCH="arm64"
elif [[ "$ARCH" == "x86_64" ]]; then
  WASI_ARCH="x86_64"
else
  echo "Unsupported arch: $ARCH"
  exit 1
fi

# Detect OS for release artifact naming.
# Git Bash on Windows reports uname -s as MINGW64_NT-... or MSYS_NT-...
KERNEL="$(uname -s)"
if [[ "$KERNEL" == "Darwin" ]]; then
  WASI_OS="macos"
elif [[ "$KERNEL" == "Linux" ]]; then
  WASI_OS="linux"
elif [[ "$KERNEL" == MINGW* ]] || [[ "$KERNEL" == MSYS* ]] || [[ "$KERNEL" == CYGWIN* ]]; then
  WASI_OS="windows"
else
  echo "Unsupported OS kernel: $KERNEL"
  echo "Run from macOS, Linux, WSL, or Git Bash on Windows."
  exit 1
fi

# Get latest WASI SDK major version number from GitHub API (e.g., wasi-sdk-27).
LATEST_TAG="$(curl -s https://api.github.com/repos/WebAssembly/wasi-sdk/releases/latest | \
  "$PYTHON" -c "import sys, json; print(json.load(sys.stdin)['tag_name'])")"

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