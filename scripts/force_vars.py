#!/usr/bin/env python3
"""Force theme variables as inline !important styles after Settings applies a theme."""
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

# Replace these values for a hand-authored theme. Generated themes receive their
# own copy with values derived from the reference image.
VARS = {
    "theme-background-seed": "#1a1a1a",
    "theme-foreground": "#e8e0d0",
    "theme-primary": "#c0392b",
    "theme-midground": "#c0392b",
    "theme-warm": "#c0392b",
    "theme-sidebar-seed": "#141312",
    "theme-card-seed": "#262420",
    "theme-bubble-seed": "#c0392b",
    "theme-neutral-chrome": "#0d0d0e",
    "theme-neutral-sidebar": "#0a0a0b",
    "theme-neutral-card": "#161618",
    "ui-accent": "#c0392b",
    "ui-red": "#c0392b",
    "ui-ring": "#c0392b",
    "ring": "#c0392b",
    "ui-bg-chrome": "transparent",
    "ui-bg-editor": "transparent",
    "ui-chat-surface-background": "transparent",
    "ui-sidebar-surface-background": "transparent",
    "dt-background": "#1a1a1a",
    "dt-foreground": "#e8e0d0",
    "dt-card": "#262420",
    "dt-card-foreground": "#e8e0d0",
    "dt-muted": "#595959",
    "dt-muted-foreground": "#b0b0b0",
    "dt-primary": "#c0392b",
    "dt-primary-foreground": "#f2efe6",
    "dt-accent": "#c0392b",
    "dt-accent-foreground": "#f2efe6",
    "dt-border": "#666666",
    "dt-input": "#666666",
    "dt-ring": "#c0392b",
    "dt-sidebar-bg": "#141312",
    "dt-composer-ring": "#c0392b",
}


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


async def force(port: int, target_id: str | None):
    ws_url = get_ws_url(port, target_id)
    if not ws_url:
        raise RuntimeError(f"No Hermes Desktop page found on CDP port {port}")
    expression = "(function(){var d=document.documentElement;" + "".join(
        f'd.style.setProperty("--{name}",{json.dumps(value)},"important");'
        for name, value in VARS.items()
    ) + 'return "forced";})()'
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
            print("✅", result.get("value", "forced"))
            return


parser = argparse.ArgumentParser()
parser.add_argument("--port", type=int, default=9222)
parser.add_argument("--target-id")
args = parser.parse_args()
try:
    asyncio.run(force(args.port, args.target_id))
except Exception as error:
    print(f"Error: {error}", file=sys.stderr)
    raise SystemExit(1)
