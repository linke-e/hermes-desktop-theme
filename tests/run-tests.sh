#!/bin/bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd -P)"
cd "$ROOT"

python3 -m py_compile \
  scripts/generate_theme.py \
  scripts/inject.py \
  scripts/force_vars.py
bash -n scripts/launcher.sh

TEST_IMAGE="${HERMES_THEME_TEST_IMAGE:-}"
if [ -z "$TEST_IMAGE" ]; then
  echo "Syntax checks passed. Set HERMES_THEME_TEST_IMAGE to run generator smoke tests." 
  exit 0
fi

if [ ! -f "$TEST_IMAGE" ]; then
  echo "Test image does not exist: $TEST_IMAGE" >&2
  exit 1
fi

OUTPUT_DIR="$(mktemp -d "${TMPDIR:-/tmp}/hermes-theme-test.XXXXXX")"
trap 'rm -rf "$OUTPUT_DIR"' EXIT

# Native Windows Python cannot use git-bash /tmp paths; convert once (no-op elsewhere).
OUTPUT_DIR_WIN="$OUTPUT_DIR"
command -v cygpath >/dev/null 2>&1 && OUTPUT_DIR_WIN="$(cygpath -m "$OUTPUT_DIR")"

python3 scripts/generate_theme.py \
  --image "$TEST_IMAGE" \
  --name test-theme \
  --output-dir "$OUTPUT_DIR_WIN" >/dev/null

for candidate in "$OUTPUT_DIR"/test-theme-*; do
  CANDIDATE_WIN="$candidate"
  command -v cygpath >/dev/null 2>&1 && CANDIDATE_WIN="$(cygpath -m "$candidate")"
  python3 -m py_compile "$CANDIDATE_WIN/inject.py" "$CANDIDATE_WIN/force_vars.py" "$CANDIDATE_WIN/launcher.py"
  bash -n "$candidate/launcher.sh"
  test -f "$candidate/plugin.js"
  test -f "$candidate/inject.css"
  test -f "$candidate/launcher.py"
  test -f "$candidate/assets/bg.png"
  grep -q -- "--theme-background-seed" "$candidate/inject.css"
  grep -q -- "--ui-accent" "$candidate/inject.css"
  grep -q -- "--dt-background" "$candidate/inject.css"
  grep -q -- "__HERMES_BACKGROUND_FILE__" "$candidate/inject.css"
  if grep -q -- "--dt-background: transparent" "$candidate/inject.css"; then
    echo "Generated theme makes the background transparent" >&2
    exit 1
  fi
  if grep -q -- "pkill -9" "$candidate/launcher.sh"; then
    echo "Generated launcher contains a broad force-kill" >&2
    exit 1
  fi
done

if python3 scripts/generate_theme.py \
  --image "$TEST_IMAGE" \
  --name Invalid_Name \
  --output-dir "$OUTPUT_DIR_WIN" >/dev/null 2>&1; then
  echo "Invalid theme name was accepted" >&2
  exit 1
fi

echo "Hermes Desktop Theme smoke tests passed."
