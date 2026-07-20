# Hermes Desktop Theme

Generate complete Hermes Desktop themes from a reference image: color theme, background image, CDP injector, inline variable overrides, and a safer launcher.

This project targets Hermes Desktop (Electron). It does not modify the app package, `app.asar`, signatures, API keys, or model-provider settings. Hermes TUI YAML skins are a separate system.

## Quick start

Requires Hermes Desktop and Python 3. The Hermes Python environment is recommended because the CDP scripts use `websockets`.

```bash
python3 scripts/generate_theme.py \
  --image /absolute/path/to/reference.png \
  --name my-theme \
  --output-dir "$HOME/.hermes/desktop-plugins"
```

The generator creates `my-theme-dark`, `my-theme-light`, and `my-theme-vivid`. Choose one and run its launcher:

```bash
~/.hermes/desktop-plugins/my-theme-dark/launcher.sh
```

Override the binary or port when needed:

```bash
HERMES_BIN="/absolute/path/to/Hermes" \
HERMES_DEBUG_PORT=9341 \
~/.hermes/desktop-plugins/my-theme-dark/launcher.sh
```

The launcher calls the Hermes binary directly, refuses an occupied CDP port, avoids `open --args`, and does not terminate unrelated processes with broad `pkill -9` commands.

## Generated files

- `plugin.js`: Hermes Desktop Plugin SDK colors and typography
- `inject.css`: three-layer `--theme-*`, `--ui-*`, and `--dt-*` variables plus artwork
- `inject.py`: loopback CDP injection and removal
- `force_vars.py`: inline `!important` variables after Settings applies a theme
- `launcher.sh`: architecture-aware launch and readiness check
- `assets/bg.png`: copied background image

## Hard rules

- Never set `--dt-background` to `transparent`.
- Override `--ui-accent`, `--ui-ring`, `--ring`, and `--dt-composer-ring`.
- Keep user bubbles around 10% opacity and avoid blur when artwork should stay sharp.
- Do not use broad Tailwind selectors such as `[class*="bg-("]`.
- Keep CDP on `127.0.0.1`; never commit tokens, private screenshots, or app binaries.
- CSS injection is not visual acceptance: inspect computed styles and real home/task screenshots.

See [SKILL.md](./SKILL.md) for the full workflow and verification checklist.

## Checks

```bash
./tests/run-tests.sh
HERMES_THEME_TEST_IMAGE=/absolute/path/to/reference.png ./tests/run-tests.sh
```

## License

MIT
