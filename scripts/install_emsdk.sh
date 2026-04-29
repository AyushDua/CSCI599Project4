#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TOOLS_DIR="$ROOT_DIR/.tools"
EMSDK_DIR="$TOOLS_DIR/emsdk"

mkdir -p "$TOOLS_DIR"

if [[ ! -d "$EMSDK_DIR" ]]; then
  echo "Cloning emsdk..."
  git clone https://github.com/emscripten-core/emsdk.git "$EMSDK_DIR"
else
  echo "emsdk already cloned; pulling latest..."
  (cd "$EMSDK_DIR" && git pull)
fi

cd "$EMSDK_DIR"

# Use `python emsdk.py` directly to avoid the `./emsdk` shebang requiring python3.
python emsdk.py update-tags
python emsdk.py install latest
python emsdk.py activate latest

# --- Locate emsdk's bundled python and emcc.py ---
EMSDK_PYTHON="$(find "$EMSDK_DIR/python" -maxdepth 3 -name "python.exe" | head -1)"
EMSCRIPTEN_DIR="$EMSDK_DIR/upstream/emscripten"
EM_CONFIG_PATH="$EMSDK_DIR/.emscripten"

if [[ -z "$EMSDK_PYTHON" ]]; then
  echo "ERROR: could not find bundled python.exe inside emsdk/python/"
  exit 1
fi

if [[ ! -f "$EMSCRIPTEN_DIR/emcc.py" ]]; then
  echo "ERROR: emcc.py not found at $EMSCRIPTEN_DIR"
  exit 1
fi

echo "Found emsdk python: $EMSDK_PYTHON"
echo "Found emscripten:   $EMSCRIPTEN_DIR"

# --- Create bash-callable emcc wrapper (Git Bash on Windows needs this) ---
mkdir -p "$TOOLS_DIR/bin"

cat > "$TOOLS_DIR/bin/emcc" << WRAPPER
#!/usr/bin/env bash
export EMSDK="$EMSDK_DIR"
export EM_CONFIG="$EM_CONFIG_PATH"
exec "$EMSDK_PYTHON" "$EMSCRIPTEN_DIR/emcc.py" "\$@"
WRAPPER
chmod +x "$TOOLS_DIR/bin/emcc"

# --- Create env shim used by build_web.sh ---
cat > "$TOOLS_DIR/emsdk_env.sh" << EOF
export EMSDK="$EMSDK_DIR"
export EM_CONFIG="$EM_CONFIG_PATH"
export PATH="$TOOLS_DIR/bin:\$PATH"
EOF

echo "Emscripten installed."
echo "emcc wrapper: $TOOLS_DIR/bin/emcc"
echo "Env shim:     $TOOLS_DIR/emsdk_env.sh"

# Sanity check
source "$TOOLS_DIR/emsdk_env.sh"
emcc -v
