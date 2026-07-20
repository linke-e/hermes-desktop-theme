# Hermes Desktop Theme

Generate complete Hermes Desktop themes from a reference image: color theme, background image, CDP injector, inline variable overrides, and a safer launcher.

This project targets Hermes Desktop (Electron). It does not modify the app package, `app.asar`, signatures, API keys, or model-provider settings. Hermes TUI YAML skins are a separate system.

## Live previews

These are real Hermes Desktop theme showcase screenshots. They demonstrate the background, palette, readability layer, and native UI working together.

> Important: all four images contain Hermes UI and are **showcase screenshots**, not importable backgrounds. Use a clean wallpaper without windows, buttons, text, or input fields when generating a new theme.

### Dusk double portrait

![Dusk double portrait](docs/images/hermes-desktop-theme-showcase-01.png)

### Starry fantasy

![Starry fantasy](docs/images/hermes-desktop-theme-showcase-02.png)

### Ink knight

![Ink knight](docs/images/hermes-desktop-theme-showcase-03.png)

### Forest elf

![Forest elf](docs/images/hermes-desktop-theme-showcase-04.png)

These showcase screenshots were provided by the repository maintainer. Backgrounds, people, characters, and other visual assets shown in them are not automatically covered by this project's MIT license. Confirm generation, likeness, copyright, and trademark rights before redistributing or using them commercially.

## Usage

### 1. Get the project

```bash
git clone https://github.com/renhongwei-ai/hermes-desktop-theme.git
cd hermes-desktop-theme
```

You need Hermes Desktop, Python 3, and the Hermes Desktop plugin directory. The CDP scripts also need Python `websockets`; the Hermes-provided Python environment is preferred.

### 2. Prepare a clean background

Use an image you are authorized to redistribute. A wide 16:9 image works best; keep the left navigation and center text-safe areas low-information and place the main subject toward the right.

Do not use the four showcase screenshots on this page as generator input: they already contain Hermes windows, controls, text, and composer UI.

### 3. Generate candidates

Requires Hermes Desktop and Python 3. The Hermes Python environment is recommended because the CDP scripts use `websockets`.

```bash
python3 scripts/generate_theme.py \
  --image /absolute/path/to/reference.png \
  --name my-theme \
  --output-dir "$HOME/.hermes/desktop-plugins"
```

The generator creates `my-theme-dark`, `my-theme-light`, and `my-theme-vivid`. Each candidate contains `plugin.js`, `inject.css`, `inject.py`, `force_vars.py`, `launcher.sh`, and a copy of the background image.

To replace candidates from an earlier run, explicitly add `--overwrite`; do not use it on a shared directory.

### 4. Select the theme

If you generated the candidates elsewhere, copy the selected directory as a whole to:

```text
~/.hermes/desktop-plugins/my-theme-dark/
```

Reload Hermes Desktop plugins if needed, then select `my-theme-dark` under `Settings → Theme`. `defaultEnabled: true` makes the theme discoverable; it does not select it for you.

### 5. Launch and inject

```bash
~/.hermes/desktop-plugins/my-theme-dark/launcher.sh
```

The launcher calls the Hermes binary directly, waits for loopback CDP readiness, then injects the CSS and applies the inline variable overrides. It does not use `open --args` or broad `pkill -9` commands.

Override the binary or port when needed:

```bash
HERMES_BIN="/absolute/path/to/Hermes" \
HERMES_DEBUG_PORT=9341 \
~/.hermes/desktop-plugins/my-theme-dark/launcher.sh
```

If `websockets` is missing, install it into the Hermes Python environment:

```bash
"$HOME/.hermes/hermes-agent/venv/bin/python3" -m pip install websockets
```

### 6. Verify and restore

Do not treat a present CSS tag or visible wallpaper as acceptance. Check computed `--ui-accent`, `--dt-background`, and `--dt-composer-ring` values; verify readable text, native controls, focus, menus, attachments, approvals, and both home/task screenshots.

Manual inject/remove:

```bash
python3 ~/.hermes/desktop-plugins/my-theme-dark/inject.py \
  --port "${HERMES_DEBUG_PORT:-9222}" \
  --css ~/.hermes/desktop-plugins/my-theme-dark/inject.css

python3 ~/.hermes/desktop-plugins/my-theme-dark/inject.py \
  --off --port "${HERMES_DEBUG_PORT:-9222}"
```

Reload Hermes Desktop after removal to clear inline variables written by `force_vars.py`.

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
