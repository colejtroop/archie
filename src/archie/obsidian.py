from __future__ import annotations

import json
import base64
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread

from .telemetry import Telemetry
from .vision import VisionRecorder


PAGE = """<!doctype html><meta charset=utf-8><title>Obsidian · Archie</title>
<style>body{font:16px system-ui;background:#0b0d12;color:#e7e9ee;margin:2rem}h1{color:#a98cff}.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:1rem}.card{background:#171a23;padding:1rem;border-radius:10px}.muted{color:#9298a8}pre{white-space:pre-wrap}</style>
<h1>Obsidian</h1><p class=muted>Archie live construction telemetry</p>
<div class=grid><div class=card><h2>Build progress</h2><strong id=progress>0%</strong></div><div class=card><h2>Agent</h2><pre id=agent>Waiting…</pre></div><div class=card><h2>Neural model</h2><strong>NO LEARNED MODEL ACTIVE</strong></div></div>
<div class=card style='margin-top:1rem'><h2>ARCHIE VISION</h2><img id=vision style='max-width:100%;display:none'><strong id=noVision>NO LIVE FRAME SOURCE CONNECTED</strong></div>
<div class=card style='margin-top:1rem'><h2>Event log</h2><pre id=events></pre></div>
<script>async function tick(){let e=await(await fetch('/api/events')).json();let s=[...e].reverse().find(x=>x.event_type==='STATE_UPDATED');if(s){progress.textContent=Math.round(s.payload.completion*100)+'%';agent.textContent=JSON.stringify(s.payload,null,2)}events.textContent=e.slice(-15).map(x=>x.event_type+' '+JSON.stringify(x.payload)).join('\n');let v=await(await fetch('/api/frame')).json();if(v.image){vision.src='data:'+v.media_type+';base64,'+v.image;vision.style.display='block';noVision.style.display='none'}}setInterval(tick,250);tick()</script>"""


def serve(telemetry: Telemetry, vision: VisionRecorder | None = None, host: str = "127.0.0.1", port: int = 8765) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/events":
                body = json.dumps([event.to_dict() for event in telemetry.events]).encode()
                content_type = "application/json"
            elif self.path == "/api/frame":
                frame = vision.latest if vision else None
                value = {"image": None} if frame is None else {
                    "image": base64.b64encode(frame.image).decode("ascii"),
                    "media_type": frame.media_type,
                    "sequence": frame.sequence,
                }
                body = json.dumps(value).encode()
                content_type = "application/json"
            else:
                body = PAGE.encode()
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server
