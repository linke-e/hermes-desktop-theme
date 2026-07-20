#!/usr/bin/env python3
"""
Hermes Desktop Theme Studio — core generator.
Analyzes an image, generates 3 theme candidates (dark/light/vivid).
"""
import argparse
import json
import re
import shutil
import sys
from pathlib import Path

# Try to import PIL for color analysis; fall back to pure-Python PNG decoder
try:
    from PIL import Image
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False


MAX_INPUT_IMAGE_BYTES = 50 * 1024 * 1024
THEME_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")


def validate_theme_name(value: str) -> str:
    """Validate the name before using it in paths, JavaScript, or shell code."""
    if not THEME_NAME_PATTERN.fullmatch(value):
        raise ValueError("name must contain only lowercase letters, digits, and hyphens (1-64 chars)")
    return value


def validate_overlay(value: float, name: str) -> float:
    if not 0 <= value <= 1:
        raise ValueError(f"{name} must be between 0 and 1")
    return value


def validate_image(path: Path) -> Path:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"image must be a regular file: {path}")
    if path.stat().st_size == 0 or path.stat().st_size > MAX_INPUT_IMAGE_BYTES:
        raise ValueError(f"image must be between 1 byte and {MAX_INPUT_IMAGE_BYTES} bytes")
    return path


def hex_to_rgb(hex_color: str) -> tuple:
    """Convert hex color to RGB tuple."""
    hex_color = hex_color.lstrip('#')
    return tuple(int(hex_color[i:i+2], 16) for i in (0, 2, 4))


def rgb_to_hex(r: int, g: int, b: int) -> str:
    """Convert RGB to hex color."""
    return f"#{r:02x}{g:02x}{b:02x}"


def adjust_brightness(hex_color: str, factor: float) -> str:
    """Adjust brightness of a hex color. factor > 1 = brighter, < 1 = darker."""
    r, g, b = hex_to_rgb(hex_color)
    r = min(255, int(r * factor))
    g = min(255, int(g * factor))
    b = min(255, int(b * factor))
    return rgb_to_hex(r, g, b)


def adjust_saturation(hex_color: str, factor: float) -> str:
    """Adjust saturation of a hex color."""
    r, g, b = hex_to_rgb(hex_color)
    # Convert to HSL-like approximation
    max_c = max(r, g, b)
    min_c = min(r, g, b)
    l = (max_c + min_c) / 2
    if max_c == min_c:
        s = 0
    else:
        s = (max_c - min_c) / (255 - abs(2 * l - 255)) if l > 127 else (max_c - min_c) / (2 * l + 1)
    
    # Apply saturation adjustment
    if s > 0:
        s_new = min(1.0, s * factor)
        # Simplified saturation adjustment
        gray = int(0.299 * r + 0.587 * g + 0.114 * b)
        r = min(255, max(0, int(gray + (r - gray) * factor)))
        g = min(255, max(0, int(gray + (g - gray) * factor)))
        b = min(255, max(0, int(gray + (b - gray) * factor)))
    
    return rgb_to_hex(r, g, b)


def _decode_png_pure_python(image_path: str, max_pixels: int = 10000) -> list:
    """
    Pure-Python PNG decoder for extracting pixel colors.
    Handles non-interlaced 8-bit RGB/RGBA PNGs.
    Returns list of (r, g, b) tuples.
    """
    import struct
    import zlib
    
    with open(image_path, 'rb') as f:
        data = f.read()
    
    # Verify PNG signature
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        raise ValueError("Not a PNG file")
    
    pos = 8
    width = height = None
    bit_depth = color_type = None
    idat_data = b''
    
    while pos < len(data):
        length = struct.unpack('>I', data[pos:pos+4])[0]
        chunk_type = data[pos+4:pos+8]
        chunk_data = data[pos+8:pos+8+length]
        
        if chunk_type == b'IHDR':
            width = struct.unpack('>I', chunk_data[0:4])[0]
            height = struct.unpack('>I', chunk_data[4:8])[0]
            bit_depth = chunk_data[8]
            color_type = chunk_data[9]
        elif chunk_type == b'IDAT':
            idat_data += chunk_data
        
        pos += 8 + length + 4  # skip CRC
    
    if width is None or height is None:
        raise ValueError("Invalid PNG: missing IHDR")
    
    if bit_depth != 8:
        raise ValueError(f"Unsupported bit depth: {bit_depth}")
    if color_type not in (2, 6):  # 2=RGB, 6=RGBA
        raise ValueError(f"Unsupported color type: {color_type}")
    
    # Decompress IDAT
    raw = zlib.decompress(idat_data)
    
    # Calculate bytes per pixel and stride
    bpp = 3 if color_type == 2 else 4
    stride = width * bpp
    
    # Apply PNG filters and extract pixels
    pixels = []
    prev_row = bytearray(stride)
    
    step = max(1, (width * height) // max_pixels)  # Sample if too large
    pixel_count = 0
    
    for y in range(height):
        row_start = y * (stride + 1)
        filter_type = raw[row_start]
        row = bytearray(raw[row_start + 1:row_start + 1 + stride])
        
        # Apply filter
        if filter_type == 0:  # None
            pass
        elif filter_type == 1:  # Sub
            for i in range(bpp, stride):
                row[i] = (row[i] + row[i - bpp]) & 0xFF
        elif filter_type == 2:  # Up
            for i in range(stride):
                row[i] = (row[i] + prev_row[i]) & 0xFF
        elif filter_type == 3:  # Average
            for i in range(stride):
                left = row[i - bpp] if i >= bpp else 0
                up = prev_row[i]
                row[i] = (row[i] + (left + up) // 2) & 0xFF
        elif filter_type == 4:  # Paeth
            for i in range(stride):
                a = row[i - bpp] if i >= bpp else 0
                b = prev_row[i]
                c = prev_row[i - bpp] if i >= bpp else 0
                p = a + b - c
                pa = abs(p - a)
                pb = abs(p - b)
                pc = abs(p - c)
                pred = a if pa <= pb and pa <= pc else (b if pb <= pc else c)
                row[i] = (row[i] + pred) & 0xFF
        
        prev_row = row
        
        # Sample pixels from this row
        if y % max(1, step // width + 1) == 0:
            for x in range(0, width, max(1, step % width + 1)):
                idx = x * bpp
                r, g, b = row[idx], row[idx + 1], row[idx + 2]
                pixels.append((r, g, b))
                pixel_count += 1
                if pixel_count >= max_pixels:
                    break
        if pixel_count >= max_pixels:
            break
    
    return pixels


def _quantize_colors(pixels: list, n: int) -> list:
    """Simple median-cut color quantization."""
    if not pixels:
        return []
    
    # Convert to list of [r, g, b] for easier manipulation
    pixels = [list(p) for p in pixels]
    
    def median_cut(pixels, depth):
        if depth == 0 or len(pixels) <= 1:
            # Return average color
            if not pixels:
                return [0, 0, 0]
            avg = [sum(c[i] for c in pixels) // len(pixels) for i in range(3)]
            return avg
        
        # Find channel with greatest range
        ranges = [max(c[i] for c in pixels) - min(c[i] for c in pixels) for i in range(3)]
        channel = ranges.index(max(ranges))
        
        # Sort by that channel and split at median
        pixels.sort(key=lambda c: c[channel])
        mid = len(pixels) // 2
        
        left = median_cut(pixels[:mid], depth - 1)
        right = median_cut(pixels[mid:], depth - 1)
        
        # Return the "better" half (we'll collect all at the end)
        return left if len(pixels[:mid]) > len(pixels[mid:]) else right
    
    # Use a different approach: iterative splitting
    def split_box(pixels, n_boxes):
        boxes = [pixels]
        while len(boxes) < n_boxes:
            # Find box with most pixels and greatest range
            best_idx = -1
            best_score = -1
            for i, box in enumerate(boxes):
                if len(box) < 2:
                    continue
                ranges = [max(c[ch] for c in box) - min(c[ch] for c in box) for ch in range(3)]
                score = len(box) * max(ranges)
                if score > best_score:
                    best_score = score
                    best_idx = i
            
            if best_idx < 0:
                break
            
            box = boxes.pop(best_idx)
            ranges = [max(c[ch] for c in box) - min(c[ch] for c in box) for ch in range(3)]
            channel = ranges.index(max(ranges))
            box.sort(key=lambda c: c[channel])
            mid = len(box) // 2
            boxes.append(box[:mid])
            boxes.append(box[mid:])
        
        # Average each box
        result = []
        for box in boxes:
            if box:
                avg = tuple(sum(c[i] for c in box) // len(box) for i in range(3))
                result.append(avg)
        return result
    
    quantized = split_box(pixels, n)
    return [rgb_to_hex(*q) for q in quantized]


def get_dominant_colors(image_path: str, n: int = 8) -> list:
    """Extract dominant colors from image using PIL or pure-Python fallback."""
    if PIL_AVAILABLE:
        img = Image.open(image_path)
        img = img.convert('RGB')
        img = img.resize((150, 150))  # Downsample for speed
        
        # Quantize to reduce color space
        img_quant = img.quantize(colors=n, method=2)
        palette = img_quant.getpalette()
        
        colors = []
        for i in range(n):
            r = palette[i * 3]
            g = palette[i * 3 + 1]
            b = palette[i * 3 + 2]
            colors.append(rgb_to_hex(r, g, b))
        
        # Sort by luminance (perceived brightness)
        def luminance(hex_c):
            r, g, b = hex_to_rgb(hex_c)
            return 0.299 * r + 0.587 * g + 0.114 * b
        
        colors.sort(key=luminance)
        return colors
    
    # Pure-Python fallback for PNG
    try:
        pixels = _decode_png_pure_python(image_path, max_pixels=8000)
        if not pixels:
            raise ValueError("No pixels extracted")
        
        colors = _quantize_colors(pixels, n)
        
        # Sort by luminance
        def luminance(hex_c):
            r, g, b = hex_to_rgb(hex_c)
            return 0.299 * r + 0.587 * g + 0.114 * b
        
        colors.sort(key=luminance)
        
        # Ensure we have exactly n colors
        while len(colors) < n:
            colors.append(colors[-1] if colors else '#808080')
        
        return colors[:n]
        
    except Exception as e:
        print(f"Warning: PNG decode failed ({e}), using fallback colors")
        # Return sensible defaults based on common dark theme
        return [
            '#1a1a2e', '#16213e', '#0f3460', '#e94560',
            '#f5f5f0', '#eaeaea', '#2d2d4a', '#7c3aed'
        ]


def generate_theme_colors(colors: list, mode: str) -> dict:
    """Generate DesktopTheme colors from extracted palette."""
    if len(colors) < 4:
        # Fallback defaults
        colors = ['#1a1a2e', '#16213e', '#0f3460', '#e94560', '#f5f5f0', '#eaeaea']
    
    # Ensure we have enough colors
    while len(colors) < 6:
        colors.append(colors[-1])
    
    darkest = colors[0]
    dark = colors[1] if len(colors) > 1 else adjust_brightness(darkest, 1.3)
    mid_dark = colors[2] if len(colors) > 2 else adjust_brightness(darkest, 1.6)
    mid = colors[3] if len(colors) > 3 else adjust_brightness(darkest, 2.0)
    light = colors[-2] if len(colors) > 4 else adjust_brightness(darkest, 3.0)
    lightest = colors[-1]
    
    # Find most saturated color for accent
    def saturation(hex_c):
        r, g, b = hex_to_rgb(hex_c)
        max_c = max(r, g, b)
        min_c = min(r, g, b)
        return (max_c - min_c) / 255 if max_c > 0 else 0
    
    accent = max(colors, key=saturation)
    max_sat = saturation(accent)
    
    # For low-saturation images (ink wash, B&W, minimal), use contextual accent
    if max_sat < 0.15:
        # Check if image is warm or cool toned
        avg_r = sum(hex_to_rgb(c)[0] for c in colors) / len(colors)
        avg_b = sum(hex_to_rgb(c)[2] for c in colors) / len(colors)
        
        if avg_r > avg_b + 10:
            # Warm toned → use warm accent
            accent = '#c94f4f'  # muted red, like ink seal
        elif avg_b > avg_r + 10:
            # Cool toned → use cool accent
            accent = '#4a6fa5'  # muted blue
        else:
            # Neutral → use classic ink red (traditional Chinese seal)
            accent = '#a04040'
    elif max_sat < 0.25:
        # Slightly low saturation → boost it
        accent = adjust_saturation(accent, 1.5)
    
    if mode == 'dark':
        return {
            'background': darkest if hex_to_rgb(darkest)[0] < 40 else '#0d0d1a',
            'foreground': lightest if hex_to_rgb(lightest)[0] > 200 else '#e8e8f0',
            'card': dark,
            'cardForeground': lightest if hex_to_rgb(lightest)[0] > 200 else '#e8e8f0',
            'muted': mid_dark,
            'mutedForeground': adjust_brightness(mid_dark, 2.5),
            'popover': dark,
            'popoverForeground': lightest if hex_to_rgb(lightest)[0] > 200 else '#e8e8f0',
            'primary': accent,
            'primaryForeground': '#ffffff',
            'secondary': mid_dark,
            'secondaryForeground': adjust_brightness(mid_dark, 2.0),
            'accent': accent,
            'accentForeground': '#ffffff',
            'border': mid_dark,
            'input': mid_dark,
            'ring': accent,
            'destructive': '#ef4444',
            'destructiveForeground': '#ffffff',
            'sidebarBackground': adjust_brightness(darkest, 0.7) if hex_to_rgb(darkest)[0] < 40 else '#0a0a14',
            'sidebarBorder': mid_dark,
            'userBubble': accent,
            'userBubbleBorder': adjust_brightness(accent, 0.8),
        }
    
    elif mode == 'light':
        # For light mode, invert the palette
        light_bg = lightest if hex_to_rgb(lightest)[0] > 200 else '#f5f5f0'
        dark_text = darkest if hex_to_rgb(darkest)[0] < 60 else '#1a1a2e'
        light_accent = adjust_brightness(accent, 0.7)  # Darker accent for light bg
        
        return {
            'background': light_bg,
            'foreground': dark_text,
            'card': adjust_brightness(light_bg, 0.95),
            'cardForeground': dark_text,
            'muted': adjust_brightness(light_bg, 0.9),
            'mutedForeground': adjust_brightness(dark_text, 1.5),
            'popover': adjust_brightness(light_bg, 0.98),
            'popoverForeground': dark_text,
            'primary': light_accent,
            'primaryForeground': '#ffffff',
            'secondary': adjust_brightness(light_bg, 0.85),
            'secondaryForeground': adjust_brightness(dark_text, 1.3),
            'accent': light_accent,
            'accentForeground': '#ffffff',
            'border': adjust_brightness(light_bg, 0.8),
            'input': adjust_brightness(light_bg, 0.92),
            'ring': light_accent,
            'destructive': '#dc2626',
            'destructiveForeground': '#ffffff',
            'sidebarBackground': adjust_brightness(light_bg, 0.97),
            'sidebarBorder': adjust_brightness(light_bg, 0.85),
            'userBubble': light_accent,
            'userBubbleBorder': adjust_brightness(light_accent, 0.9),
        }
    
    else:  # vivid
        base = generate_theme_colors(colors, 'dark')
        # Boost saturation and brightness of accent
        vivid_accent = adjust_saturation(accent, 1.4)
        vivid_accent = adjust_brightness(vivid_accent, 1.2)
        base['primary'] = vivid_accent
        base['accent'] = vivid_accent
        base['ring'] = vivid_accent
        base['userBubble'] = vivid_accent
        base['userBubbleBorder'] = adjust_brightness(vivid_accent, 0.8)
        return base


def generate_plugin_js(theme_name: str, label: str, colors: dict, description: str = '') -> str:
    """Generate plugin.js content."""
    # Generate dark variant (slightly darker)
    dark_colors = colors.copy()
    for key in ['background', 'card', 'muted', 'popover', 'sidebarBackground']:
        if key in dark_colors:
            dark_colors[key] = adjust_brightness(dark_colors[key], 0.85)
    
    def format_colors(c: dict, indent: int = 4) -> str:
        lines = []
        spaces = ' ' * indent
        for k, v in c.items():
            lines.append(f"{spaces}{k}: '{v}',")
        return '\n'.join(lines)
    
    return f"""import {{ THEMES_AREA }} from '@hermes/plugin-sdk'

const theme = {{
  name: '{theme_name}',
  label: '{label}',
  description: '{description or f'Generated theme: {label}'}',
  colors: {{
{format_colors(colors)}
  }},
  darkColors: {{
{format_colors(dark_colors)}
  }},
  typography: {{
    fontSans: 'system-ui, -apple-system, BlinkMacSystemFont, sans-serif',
    fontMono: 'SF Mono, Monaco, Menlo, monospace',
  }},
}}

export default {{
  id: '{theme_name}',
  name: '{label}',
  defaultEnabled: true,
  register(ctx) {{
    ctx.register({{ id: '{theme_name}', area: THEMES_AREA, data: theme }})
  }},
}}
"""


def rgba_from_hex(hex_color: str, alpha: float) -> str:
    r, g, b = hex_to_rgb(hex_color)
    return f"rgba({r}, {g}, {b}, {alpha:.2f})"


def generate_inject_css(theme_dir: Path, colors: dict, overlay_opacity: float) -> str:
    """Generate inject.css content."""
    # Resolve this at injection time so a generated theme can be moved or copied
    # to ~/.hermes without leaving an absolute build-machine path in CSS.
    bg_url = '__HERMES_BACKGROUND_FILE__'
    accent = colors['primary']
    background = colors['background']
    foreground = colors['foreground']
    sidebar = colors.get('sidebarBackground', colors['background'])
    card = colors.get('card', colors['background'])
    muted = colors.get('muted', colors['background'])
    muted_foreground = colors.get('mutedForeground', colors['foreground'])
    border = colors.get('border', muted)

    return f"""/* Background image layer */
html::before {{
  content: '';
  position: fixed;
  inset: 0;
  z-index: -1;
  background: url('{bg_url}') center / cover no-repeat fixed;
  pointer-events: none;
}}

/* Keep the canvas transparent without flattening every descendant surface. */
body, #root {{
  background: transparent !important;
}}
:root {{
  --theme-foreground: {foreground} !important;
  --theme-primary: {accent} !important;
  --theme-midground: {accent} !important;
  --theme-warm: {accent} !important;
  --theme-background-seed: {background} !important;
  --theme-sidebar-seed: {sidebar} !important;
  --theme-card-seed: {card} !important;
  --theme-bubble-seed: {accent} !important;
  --theme-neutral-chrome: {background} !important;
  --theme-neutral-sidebar: {sidebar} !important;
  --theme-neutral-card: {card} !important;
  --theme-mix-chrome: 74% !important;
  --theme-mix-sidebar: 100% !important;
  --theme-mix-card: 38% !important;
  --ui-accent: {accent} !important;
  --ui-red: {accent} !important;
  --ui-ring: {accent} !important;
  --ring: {accent} !important;
  --ui-bg-chrome: transparent !important;
  --ui-bg-editor: transparent !important;
  --ui-chat-surface-background: transparent !important;
  --ui-sidebar-surface-background: transparent !important;
  --dt-background: {background} !important;
  --dt-foreground: {foreground} !important;
  --dt-card: {card} !important;
  --dt-card-foreground: {foreground} !important;
  --dt-muted: {muted} !important;
  --dt-muted-foreground: {muted_foreground} !important;
  --dt-primary: {accent} !important;
  --dt-primary-foreground: {colors.get('primaryForeground', '#ffffff')} !important;
  --dt-accent: {accent} !important;
  --dt-accent-foreground: {colors.get('accentForeground', '#ffffff')} !important;
  --dt-border: {border} !important;
  --dt-input: {colors.get('input', border)} !important;
  --dt-ring: {accent} !important;
  --dt-sidebar-bg: {sidebar} !important;
  --dt-composer-ring: {accent} !important;
}}

/* Keep the real sidebar and message controls usable over the artwork. */
[class~="sidebar-wrapper"] {{
  background: transparent !important;
}}

.composer-human-message {{
  background-color: {rgba_from_hex(accent, 0.10)} !important;
  border-color: {rgba_from_hex(accent, 0.30)} !important;
}}

button[type="submit"] {{
  background: {accent} !important;
  color: {colors.get('primaryForeground', '#ffffff')} !important;
  border-color: transparent !important;
}}

*:focus-visible {{
  outline-color: {accent} !important;
}}

footer .text-primary,
[class~="status"] .text-primary {{
  color: {muted_foreground} !important;
}}

/* Semi-transparent overlay for readability */
body::after {{
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  background: {rgba_from_hex(background, overlay_opacity)};
  pointer-events: none;
}}

/* Content above overlay */
#root {{
  position: relative;
  z-index: 1;
}}
"""


def generate_launcher_sh(theme_name: str, theme_dir: Path) -> str:
    """Generate launcher.sh content."""
    return f"""#!/bin/bash
set -euo pipefail

THEME_NAME="{theme_name}"
HERMES_HOME="${{HERMES_HOME:-$HOME/.hermes}}"
THEME_DIR="$HERMES_HOME/desktop-plugins/$THEME_NAME"
PYTHON="${{HERMES_PYTHON:-$HERMES_HOME/hermes-agent/venv/bin/python3}}"
if [ ! -x "$PYTHON" ]; then PYTHON="${{HERMES_PYTHON:-python3}}"; fi
INJECTOR="$THEME_DIR/inject.py"
FORCE_VARS="$THEME_DIR/force_vars.py"
DEBUG_PORT="${{HERMES_DEBUG_PORT:-9222}}"

if [ -n "${{HERMES_BIN:-}}" ]; then
  HERMES_BIN="$HERMES_BIN"
else
  HERMES_BIN=""
  for candidate in \\
    "$HERMES_HOME/hermes-agent/apps/desktop/release/mac-arm64/Hermes.app/Contents/MacOS/Hermes" \\
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

# Launch the exact Hermes binary. Do not kill unrelated processes and do not use open --args.
"$HERMES_BIN" --remote-debugging-port="$DEBUG_PORT" >"$THEME_DIR/launcher.log" 2>&1 &

echo "Waiting for Hermes Desktop to start..."
for i in $(seq 1 20); do
  sleep 1
  if curl -fsS "http://127.0.0.1:$DEBUG_PORT/json/version" >/dev/null 2>&1; then
    echo "CDP ready"
    break
  fi
  if [ $i -eq 20 ]; then
    echo "Warning: CDP not detected, injection may fail"
  fi
done

if ! curl -fsS "http://127.0.0.1:$DEBUG_PORT/json/version" >/dev/null 2>&1; then
  echo "CDP did not become ready; see $THEME_DIR/launcher.log" >&2
  exit 1
fi

"$PYTHON" "$INJECTOR" --port "$DEBUG_PORT" --css "$THEME_DIR/inject.css"
if [ -f "$FORCE_VARS" ]; then "$PYTHON" "$FORCE_VARS" --port "$DEBUG_PORT"; fi

echo "✅ Hermes Desktop launched with theme: $THEME_NAME"
echo "   Theme picker: Settings → Theme → $THEME_NAME"
"""


def generate_force_vars_py(colors: dict) -> str:
    """Generate the inline-important override used after the theme CSS."""
    vars_map = {
        'theme-background-seed': colors['background'],
        'theme-foreground': colors['foreground'],
        'theme-primary': colors['primary'],
        'theme-midground': colors['primary'],
        'theme-warm': colors['primary'],
        'theme-sidebar-seed': colors.get('sidebarBackground', colors['background']),
        'theme-card-seed': colors.get('card', colors['background']),
        'theme-bubble-seed': colors['primary'],
        'theme-neutral-chrome': colors['background'],
        'theme-neutral-sidebar': colors.get('sidebarBackground', colors['background']),
        'theme-neutral-card': colors.get('card', colors['background']),
        'ui-accent': colors['primary'],
        'ui-red': colors['primary'],
        'ui-ring': colors['primary'],
        'ring': colors['primary'],
        'ui-bg-chrome': 'transparent',
        'ui-bg-editor': 'transparent',
        'ui-chat-surface-background': 'transparent',
        'ui-sidebar-surface-background': 'transparent',
        'dt-background': colors['background'],
        'dt-foreground': colors['foreground'],
        'dt-card': colors.get('card', colors['background']),
        'dt-card-foreground': colors.get('cardForeground', colors['foreground']),
        'dt-muted': colors.get('muted', colors['background']),
        'dt-muted-foreground': colors.get('mutedForeground', colors['foreground']),
        'dt-primary': colors['primary'],
        'dt-primary-foreground': colors.get('primaryForeground', '#ffffff'),
        'dt-accent': colors['primary'],
        'dt-accent-foreground': colors.get('accentForeground', '#ffffff'),
        'dt-border': colors.get('border', colors['background']),
        'dt-input': colors.get('input', colors.get('border', colors['background'])),
        'dt-ring': colors['primary'],
        'dt-sidebar-bg': colors.get('sidebarBackground', colors['background']),
        'dt-composer-ring': colors['primary'],
    }
    vars_json = json.dumps(vars_map, indent=4, ensure_ascii=False)
    return f'''#!/usr/bin/env python3
"""Force this generated theme's CSS variables after Settings applies a theme."""
import argparse
import asyncio
import json
import sys
import urllib.request
from urllib.parse import urlparse

try:
    import websockets
except ImportError:
    print("Missing dependency: install the Hermes Python environment or run pip install websockets", file=sys.stderr)
    raise SystemExit(1)

VARS = {vars_json}


def get_ws_url(port: int):
    with urllib.request.urlopen(f"http://127.0.0.1:{{port}}/json", timeout=3) as response:
        pages = json.loads(response.read())
    candidates = [
        page for page in pages
        if page.get("type") == "page" and page.get("webSocketDebuggerUrl")
    ]
    if not candidates:
        return None
    page = next(
        (item for item in candidates
         if "hermes" in f"{{item.get('title', '')}} {{item.get('url', '')}}".lower()),
        candidates[0],
    )
    parsed = urlparse(page["webSocketDebuggerUrl"])
    if parsed.scheme not in {{"ws", "wss"}} or parsed.hostname not in {{"127.0.0.1", "localhost"}}:
        raise RuntimeError("Refusing a non-loopback CDP websocket")
    return f"{{parsed.scheme}}://{{parsed.hostname}}:{{parsed.port}}{{parsed.path}}"


async def force(port: int):
    ws_url = get_ws_url(port)
    if not ws_url:
        raise RuntimeError("No Hermes Desktop CDP page found")
    expression = "(function(){{var d=document.documentElement;" + "".join(
        f'd.style.setProperty("--{{name}}",{{json.dumps(value)}},"important");'
        for name, value in VARS.items()
    ) + 'return "forced";}})()'
    async with websockets.connect(ws_url, max_size=2**20) as websocket:
        await websocket.send(json.dumps({{"id": 1, "method": "Runtime.evaluate", "params": {{"expression": expression, "returnByValue": True}}}}))
        while True:
            message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=3))
            if message.get("id") == 1:
                result = message.get("result", {{}}).get("result", {{}})
                if "exceptionDetails" in result:
                    raise RuntimeError("CDP evaluation failed")
                print("✅", result.get("value", "forced"))
                return


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=9222)
args = parser.parse_args()
try:
    asyncio.run(force(args.port))
except Exception as error:
    print(f"Error: {{error}}", file=sys.stderr)
    raise SystemExit(1)
'''


def generate_inject_py() -> str:
    """Generate the CDP injector script."""
    return '''#!/usr/bin/env python3
"""Inject or remove a Hermes Desktop theme through a loopback CDP port."""
import argparse
import asyncio
import json
import sys
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

try:
    import websockets
except ImportError:
    print("Missing dependency: install the Hermes Python environment or run pip install websockets", file=sys.stderr)
    raise SystemExit(1)


def get_ws_url(port: int, target_id: str | None = None):
    with urllib.request.urlopen(f"http://127.0.0.1:{port}/json", timeout=3) as response:
        pages = json.loads(response.read())
    candidates = [
        page for page in pages
        if page.get("type") == "page" and page.get("webSocketDebuggerUrl")
    ]
    if target_id:
        candidates = [page for page in candidates if page.get("id") == target_id]
    if not candidates:
        return None
    page = next(
        (item for item in candidates
         if "hermes" in f"{item.get('title', '')} {item.get('url', '')}".lower()),
        candidates[0],
    )
    parsed = urlparse(page["webSocketDebuggerUrl"])
    if parsed.scheme not in {"ws", "wss"} or parsed.hostname not in {"127.0.0.1", "localhost"}:
        raise RuntimeError("Refusing a non-loopback CDP websocket")
    return f"{parsed.scheme}://{parsed.hostname}:{parsed.port}{parsed.path}"


async def evaluate(port: int, expression: str, target_id: str | None):
    ws_url = get_ws_url(port, target_id)
    if not ws_url:
        raise RuntimeError(f"No Hermes Desktop page found on CDP port {port}")
    async with websockets.connect(ws_url, max_size=2**20) as websocket:
        await websocket.send(json.dumps({
            "id": 1,
            "method": "Runtime.evaluate",
            "params": {"expression": expression, "returnByValue": True},
        }))
        while True:
            message = json.loads(await asyncio.wait_for(websocket.recv(), timeout=3))
            if message.get("id") != 1:
                continue
            result = message.get("result", {}).get("result", {})
            if "exceptionDetails" in result:
                raise RuntimeError("CDP evaluation failed")
            return result.get("value", "")


async def inject(port: int, css_path: str, target_id: str | None):
    css_file = Path(css_path).resolve()
    css = css_file.read_text(encoding="utf-8")
    background = (css_file.parent / "assets" / "bg.png").resolve()
    css = css.replace("__HERMES_BACKGROUND_FILE__", background.as_uri())
    expression = f"""(function() {{
        var previous = document.getElementById('hermes-dream-skin');
        if (previous) previous.remove();
        var style = document.createElement('style');
        style.id = 'hermes-dream-skin';
        style.textContent = {json.dumps(css)};
        document.head.appendChild(style);
        return 'injected';
    }})()"""
    print("✅", await evaluate(port, expression, target_id))


async def remove(port: int, target_id: str | None):
    expression = """(function() {
        var style = document.getElementById('hermes-dream-skin');
        if (!style) return 'not found';
        style.remove();
        return 'removed';
    })()"""
    print("✅", await evaluate(port, expression, target_id))


parser = argparse.ArgumentParser()
parser.add_argument("--off", action="store_true", help="remove the injected theme")
parser.add_argument("--css", default="inject.css")
parser.add_argument("--port", type=int, default=9222)
parser.add_argument("--target-id")
args = parser.parse_args()

try:
    if args.off:
        asyncio.run(remove(args.port, args.target_id))
    else:
        asyncio.run(inject(args.port, args.css, args.target_id))
except Exception as error:
    print(f"Error: {error}", file=sys.stderr)
    raise SystemExit(1)
'''


def create_theme_candidate(
    base_name: str,
    mode: str,
    colors: dict,
    image_path: str,
    output_dir: Path,
    overlay_opacity: float,
    overwrite: bool = False,
) -> Path:
    """Create a complete theme candidate directory."""
    theme_name = f"{base_name}-{mode}"
    theme_dir = output_dir / theme_name
    if theme_dir.exists():
        if not overwrite:
            raise FileExistsError(f"theme already exists: {theme_dir} (use --overwrite to replace it)")
        shutil.rmtree(theme_dir)
    theme_dir.mkdir(parents=True, exist_ok=True)
    
    # Create assets directory and copy background image
    assets_dir = theme_dir / 'assets'
    assets_dir.mkdir(exist_ok=True)
    bg_dest = assets_dir / 'bg.png'
    shutil.copy2(image_path, bg_dest)
    
    # Generate files
    label = f"{base_name.replace('-', ' ').title()} ({mode.title()})"
    description = f"Generated from reference image — {mode} variant"
    
    plugin_js = generate_plugin_js(theme_name, label, colors, description)
    (theme_dir / 'plugin.js').write_text(plugin_js)
    
    inject_css = generate_inject_css(theme_dir, colors, overlay_opacity)
    (theme_dir / 'inject.css').write_text(inject_css)
    
    launcher_sh = generate_launcher_sh(theme_name, theme_dir)
    launcher_path = theme_dir / 'launcher.sh'
    launcher_path.write_text(launcher_sh)
    launcher_path.chmod(0o755)

    force_vars = generate_force_vars_py(colors)
    force_vars_path = theme_dir / 'force_vars.py'
    force_vars_path.write_text(force_vars)
    force_vars_path.chmod(0o755)
    
    inject_py = generate_inject_py()
    (theme_dir / 'inject.py').write_text(inject_py)
    
    return theme_dir


def main():
    parser = argparse.ArgumentParser(description='Generate Hermes Desktop themes from an image')
    parser.add_argument('--image', required=True, help='Path to reference image')
    parser.add_argument('--name', required=True, help='Base theme name (lowercase, hyphens)')
    parser.add_argument('--output-dir', default='~/.hermes/desktop-plugins/', help='Output directory')
    parser.add_argument('--overlay-dark', type=float, default=0.65, help='Overlay opacity for dark mode')
    parser.add_argument('--overlay-light', type=float, default=0.35, help='Overlay opacity for light mode')
    parser.add_argument('--overlay-vivid', type=float, default=0.55, help='Overlay opacity for vivid mode')
    parser.add_argument('--overwrite', action='store_true', help='Replace existing generated candidate directories')
    
    args = parser.parse_args()
    
    try:
        validate_theme_name(args.name)
        image_path = validate_image(Path(args.image).expanduser())
        validate_overlay(args.overlay_dark, 'overlay-dark')
        validate_overlay(args.overlay_light, 'overlay-light')
        validate_overlay(args.overlay_vivid, 'overlay-vivid')
    except (ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(2)
    
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Extract colors
    print(f"Analyzing image: {image_path}")
    colors = get_dominant_colors(str(image_path), n=8)
    print(f"Extracted colors: {', '.join(colors)}")
    
    # Generate 3 candidates
    candidates = []
    
    # Dark
    dark_colors = generate_theme_colors(colors, 'dark')
    dark_dir = create_theme_candidate(args.name, 'dark', dark_colors, str(image_path), output_dir, args.overlay_dark, args.overwrite)
    candidates.append(('dark', dark_dir, dark_colors))
    print(f"✅ Generated: {dark_dir.name}")
    
    # Light
    light_colors = generate_theme_colors(colors, 'light')
    light_dir = create_theme_candidate(args.name, 'light', light_colors, str(image_path), output_dir, args.overlay_light, args.overwrite)
    candidates.append(('light', light_dir, light_colors))
    print(f"✅ Generated: {light_dir.name}")
    
    # Vivid
    vivid_colors = generate_theme_colors(colors, 'vivid')
    vivid_dir = create_theme_candidate(args.name, 'vivid', vivid_colors, str(image_path), output_dir, args.overlay_vivid, args.overwrite)
    candidates.append(('vivid', vivid_dir, vivid_colors))
    print(f"✅ Generated: {vivid_dir.name}")
    
    # Summary
    print()
    print("=" * 60)
    print("3 theme candidates generated. Pick one:")
    print()
    for mode, theme_dir, theme_colors in candidates:
        bg = theme_colors['background']
        primary = theme_colors['primary']
        overlay = args.overlay_dark if mode == 'dark' else (args.overlay_light if mode == 'light' else args.overlay_vivid)
        print(f"  {mode.upper():6s}  bg={bg}  primary={primary}  overlay={overlay}")
        print(f"         dir: {theme_dir}")
    print()
    print("To activate, run:")
    print(f"  cd {output_dir}")
    print(f"  # Pick your favorite, e.g. dark:")
    print(f"  mv {args.name}-dark {args.name}")
    print(f"  rm -rf {args.name}-light {args.name}-vivid")
    print(f"  ./{args.name}/launcher.sh")


if __name__ == '__main__':
    main()
