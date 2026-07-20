#!/usr/bin/env python3
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
