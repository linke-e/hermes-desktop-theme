---
name: hermes-desktop-theme-studio
description: >
  Create, install, customize, verify, troubleshoot, or restore visual themes
  for the Hermes Desktop Electron app. Use when a user provides a reference
  image or asks for Hermes Desktop colors, background injection, launchers,
  theme plugins, or CDP-based theme validation. This skill is for Desktop;
  Hermes TUI YAML skins are a separate system.
version: "2.1.0"
author: Hot-Carrot
license: MIT
tags: [hermes, desktop, theme, electron, cdp, customization, background]
---

# Hermes Desktop Theme Studio

Generate a complete Hermes Desktop theme from a reference image. A theme has
two cooperating layers:

1. A Desktop Plugin SDK `plugin.js` for the color palette and typography.
2. A loopback CDP injector for the background image and runtime CSS overrides.

The workflow preserves the Hermes application itself: never patch `.app`,
`app.asar`, `dist/`, release files, signatures, API keys, or provider settings.

## Non-negotiable rules

1. Cover all three CSS layers: `--theme-*` seeds, `--ui-*`/`--ui-bg-*` mix
   variables, and `--dt-*` final variables.
2. Never set `--dt-background` to `transparent`; it is used by the real panel
   surfaces and making it transparent removes their readable base.
3. Override `--ui-accent`, `--ui-ring`, `--ring`, and `--dt-composer-ring`, or
   Hermes' default blue accent will leak through.
4. Use exact selectors for visible controls. Never use broad Tailwind matches
   such as `[class*="bg-("]`.
5. Keep user bubbles translucent, normally `rgba(accent, .10)`. Do not use
   `backdrop-filter: blur()` when the user wants the artwork to remain sharp.
6. Launch the exact Hermes binary with `--remote-debugging-port`. Do not use
   macOS `open --args`, and do not kill all Hermes processes with `pkill -9`.
   Refuse an occupied port instead; this avoids terminating unrelated work.
7. CDP must remain on `127.0.0.1`. Reject non-loopback WebSocket targets.
8. Do not report success from CSS presence alone. Verify computed styles and
   inspect a real screenshot with the native controls still usable.

## Generated theme layout

```text
~/.hermes/desktop-plugins/<theme-name>/
├── plugin.js       # Desktop Plugin SDK theme registration
├── inject.css      # three-layer variables, artwork, overlay, controls
├── inject.py       # loopback CDP injection/removal
├── force_vars.py   # inline !important variables after Settings applies
├── launcher.sh     # architecture-aware binary launcher
└── assets/bg.png   # reference image copy
```

The generated CSS keeps a placeholder for the image path. `inject.py` resolves
the image relative to `inject.css` at runtime, so moving the theme directory
does not leave a build-machine path embedded in the theme.

## Workflow

### 1. Generate candidates

Use the bundled generator. The name must be lowercase letters, digits, and
hyphens, because it becomes a directory, JavaScript identifier value, and
shell-visible name.

```bash
python3 scripts/generate_theme.py \
  --image /absolute/path/to/reference.png \
  --name ink-ranger \
  --output-dir "$HOME/.hermes/desktop-plugins"
```

The generator creates `ink-ranger-dark`, `ink-ranger-light`, and
`ink-ranger-vivid`. It extracts dominant colors with Pillow when available and
falls back to a pure-Python PNG decoder. Each candidate must contain all five
runtime files plus `assets/bg.png` before it is used.

To intentionally replace candidates from a previous run, add `--overwrite`.
Do not use that flag with a broad or shared output directory.

### 2. Activate the Plugin SDK theme

Ensure the selected candidate is installed at:

```text
~/.hermes/desktop-plugins/<theme-name>/
```

Reload Hermes Desktop plugins if necessary, then open Settings → Theme and
select the generated theme. `defaultEnabled: true` makes it available; it
does not guarantee that Settings has selected it.

### 3. Launch and inject

Run the selected launcher's `launcher.sh`. It:

- discovers the Apple Silicon or Intel Hermes binary, with `HERMES_BIN` as an
  explicit override;
- uses the Hermes Python environment, with `HERMES_PYTHON` as an override;
- refuses an occupied CDP port instead of killing another process;
- launches the binary directly and waits for `/json/version`;
- injects `inject.css`, then applies `force_vars.py` with inline `!important`.

Useful overrides:

```bash
HERMES_BIN="/absolute/path/to/Hermes" \
HERMES_DEBUG_PORT=9341 \
~/.hermes/desktop-plugins/<theme-name>/launcher.sh
```

If the image is not visible, inspect whether the Electron build blocks `file:`
image URLs through CSP. Do not weaken the application CSP or patch the app;
use a loopback asset server and a loopback `http:` image URL instead.

### 4. Verify the live result

At minimum, use the provided CDP scripts to confirm the target and computed
variables. A successful injection is not visual acceptance.

```bash
python3 ~/.hermes/desktop-plugins/<theme-name>/inject.py \
  --port "${HERMES_DEBUG_PORT:-9222}" \
  --css ~/.hermes/desktop-plugins/<theme-name>/inject.css
```

Check these values in DevTools/CDP:

```javascript
(() => {
  const root = getComputedStyle(document.documentElement)
  return {
    accent: root.getPropertyValue('--ui-accent').trim(),
    background: root.getPropertyValue('--dt-background').trim(),
    ring: root.getPropertyValue('--dt-composer-ring').trim(),
    bubble: getComputedStyle(document.querySelector('.composer-human-message'))
      .backgroundColor,
  }
})()
```

Capture a real home screen and a task screen. Confirm:

- sidebar, project selector, navigation, composer, menus, attachments,
  approvals, keyboard focus, and buttons remain native and clickable;
- user bubbles and action surfaces retain artwork visibility;
- text, status labels, output, links, and code remain readable;
- no decorative layer receives pointer events;
- reload or route change does not leave duplicate `hermes-dream-skin` styles;
- the screenshot contains no private conversations, tokens, or account data.

### 5. Restore

Remove the injected style:

```bash
python3 ~/.hermes/desktop-plugins/<theme-name>/inject.py \
  --off --port "${HERMES_DEBUG_PORT:-9222}"
```

Reload Hermes Desktop to clear inline variable overrides from
`force_vars.py`. Restore the built-in Settings theme manually if it was
changed. This skill does not edit Hermes' persistent configuration or alter
the application package.

## Security and failure boundaries

- CDP is a powerful same-user debugging interface. Keep it loopback-only and
  run only trusted local software while it is open.
- The injector selects a `page` target and rejects non-loopback WebSockets;
  pass `--target-id` when multiple pages are present and selection matters.
- A local theme image is copied into the generated theme. Reject empty,
  symlinked, or unexpectedly large input files before generation.
- The generator validates theme names before using them in paths, JavaScript,
  or shell templates.
- Never put API keys, auth files, private screenshots, or user conversations
  into a public theme repository.
- A launcher failure, a CDP connection, a visible background, and a complete
  visual acceptance check are four different states. Report exactly which one
  was verified.

## Common pitfalls

| Symptom | Cause | Fix |
|---|---|---|
| CDP never opens | `open --args` did not pass the flag | Launch `Contents/MacOS/Hermes` directly |
| Another process was terminated | Broad `pkill -9` | Refuse occupied ports; close only the intended app manually |
| Default blue remains | Only one variable layer was overridden | Cover `theme-*`, `ui-*`, and `dt-*` |
| Panels disappear | `--dt-background: transparent` | Keep a solid `--dt-background` |
| Repeated injection looks wrong | Old style tags were retained | The injector removes `#hermes-dream-skin` before adding one |
| Artwork is hidden | Opaque native surface or CSP blocks `file:` | Inspect computed styles; use scoped transparent surfaces or loopback HTTP |
| Current theme looks right but reload breaks | No early reinjection mechanism | Re-run the launcher/injector after reload and document the limitation |

## Completion checklist

- [ ] Input image is authorized for redistribution and contains no fake UI.
- [ ] Theme name passes the lowercase-hyphen validation.
- [ ] `plugin.js`, `inject.css`, `inject.py`, `force_vars.py`, and `launcher.sh`
      were generated and syntax-checked.
- [ ] Plugin is selected in Hermes Settings.
- [ ] CDP is loopback-only and the intended page target was verified.
- [ ] Computed accent, background, ring, and bubble styles were checked.
- [ ] Home and task screenshots were visually inspected.
- [ ] Native interactions and reload behavior were tested.
- [ ] No app package, credentials, private data, or unrelated files entered the release.
