#!/bin/bash
set -euo pipefail

# Template launcher. Replace THEME_NAME or set HERMES_BIN/HERMES_HOME when using it.
THEME_NAME="my-theme"
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
THEME_DIR="$HERMES_HOME/desktop-plugins/$THEME_NAME"
PYTHON="${HERMES_PYTHON:-$HERMES_HOME/hermes-agent/venv/bin/python3}"
if [ ! -x "$PYTHON" ]; then PYTHON="${HERMES_PYTHON:-python3}"; fi
INJECTOR="$THEME_DIR/inject.py"
FORCE_VARS="$THEME_DIR/force_vars.py"
DEBUG_PORT="${HERMES_DEBUG_PORT:-9222}"

if [ -n "${HERMES_BIN:-}" ]; then
  HERMES_BIN="$HERMES_BIN"
else
  HERMES_BIN=""
  for candidate in \
    "$HERMES_HOME/hermes-agent/apps/desktop/release/mac-arm64/Hermes.app/Contents/MacOS/Hermes" \
    "$HERMES_HOME/hermes-agent/apps/desktop/release/mac-x64/Hermes.app/Contents/MacOS/Hermes"; do
    if [ -x "$candidate" ]; then HERMES_BIN="$candidate"; break; fi
  done
fi

if [ ! -x "$HERMES_BIN" ]; then
  echo "Hermes Desktop binary not found. Set HERMES_BIN to its Contents/MacOS/Hermes path." >&2
  exit 1
fi

if curl -fsS "http://127.0.0.1:$DEBUG_PORT/json/version" >/dev/null 2>&1; then
  echo "Refusing to use occupied CDP port $DEBUG_PORT; set HERMES_DEBUG_PORT to a free port." >&2
  exit 1
fi

# Launch the exact binary. Do not kill unrelated processes and do not use open --args.
"$HERMES_BIN" --remote-debugging-port="$DEBUG_PORT" >"$THEME_DIR/launcher.log" 2>&1 &

echo "Waiting for Hermes Desktop to start..."
for i in $(seq 1 20); do
  sleep 1
  if curl -fsS "http://127.0.0.1:$DEBUG_PORT/json/version" >/dev/null 2>&1; then
    echo "CDP ready"
    break
  fi
  if [ "$i" -eq 20 ]; then
    echo "Warning: CDP not detected" >&2
  fi
done

if ! curl -fsS "http://127.0.0.1:$DEBUG_PORT/json/version" >/dev/null 2>&1; then
  echo "CDP did not become ready; see $THEME_DIR/launcher.log" >&2
  exit 1
fi

"$PYTHON" "$INJECTOR" --port "$DEBUG_PORT" --css "$THEME_DIR/inject.css"
if [ -f "$FORCE_VARS" ]; then "$PYTHON" "$FORCE_VARS" --port "$DEBUG_PORT"; fi
echo "✅ Hermes Desktop launched with theme: $THEME_NAME"
