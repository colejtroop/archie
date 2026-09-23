from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock, Thread
from time import sleep

from .policy import create_objective_selector, select_action, valid_actions
from .policy_data import CELL_COUNT, COMPLETE_ACTION, MAX_HEIGHT, MAX_WIDTH, masks


PAGE = r"""<!doctype html><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>Obsidian · Neural Model</title>
<style>
:root{color-scheme:dark;--bg:#090b10;--panel:#141821;--line:#293142;--text:#e8eaf0;--muted:#9199aa;--purple:#a78bfa;--cyan:#67e8f9;--green:#86efac;--orange:#fdba74}*{box-sizing:border-box}body{margin:0;padding:22px;background:var(--bg);color:var(--text);font:14px system-ui}header{display:flex;justify-content:space-between;gap:16px;align-items:end;margin-bottom:18px}h1{margin:0;color:var(--purple);font-size:28px}h2{font-size:12px;letter-spacing:.12em;text-transform:uppercase;color:var(--muted);margin:0 0 12px}.sub{color:var(--muted)}.status{color:var(--green)}.layout{display:grid;grid-template-columns:300px 1fr;gap:14px}.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:15px}.inputs{display:grid;grid-template-columns:1fr 1fr;gap:12px}.grid5{display:grid;grid-template-columns:repeat(5,1fr);gap:3px}.cell{aspect-ratio:1;border-radius:3px;background:#222938;display:grid;place-items:center;font:11px ui-monospace}.cell.on{background:#6246a8}.cell.built{background:#237a57}.cell.valid{outline:2px solid var(--cyan)}.cell.selected{background:#b56c24;outline:2px solid #fff}.network{display:grid;grid-template-columns:1fr 1fr;gap:12px}.layer{margin-bottom:14px}.heat{display:grid;grid-template-columns:repeat(16,1fr);gap:2px}.neuron{aspect-ratio:1;border-radius:2px;background:color-mix(in srgb,var(--purple) calc(var(--a)*100%),#202532)}.output{display:grid;grid-template-columns:repeat(5,1fr);gap:4px}.logit{min-height:44px;border-radius:4px;background:#202532;padding:4px;font:11px ui-monospace;color:var(--muted)}.logit.valid{outline:1px solid var(--cyan)}.logit.selected{background:#8a541e;color:#fff;outline:2px solid #fff}.metrics{display:grid;grid-template-columns:repeat(3,1fr);gap:8px;margin-bottom:14px}.metric{background:#202532;padding:10px;border-radius:7px}.metric strong{display:block;font-size:19px}.trace{font:12px ui-monospace;white-space:pre-wrap;color:var(--muted)}@media(max-width:800px){.layout,.network{grid-template-columns:1fr}.inputs{grid-template-columns:1fr 1fr}}
</style>
<header><div><h1>OBSIDIAN</h1><div class="sub">Objective Selector V0 · live neural computation</div></div><div id="status" class="status">MODEL ONLINE</div></header>
<div class="layout"><aside class="panel"><h2>Model inputs</h2><div class="inputs"><div><div class="sub">Blueprint</div><div id="blueprint" class="grid5"></div></div><div><div class="sub">Built state</div><div id="built" class="grid5"></div></div></div><hr><h2>Decision</h2><div class="metrics"><div class="metric"><span class="sub">Step</span><strong id="step">—</strong></div><div class="metric"><span class="sub">Target</span><strong id="target">—</strong></div><div class="metric"><span class="sub">Confidence</span><strong id="confidence">—</strong></div></div><div id="trace" class="trace"></div></aside>
<main class="panel"><h2>Hidden activations</h2><div class="network"><div><div class="layer"><div class="sub">Dense 50 → 128</div><div id="layer0" class="heat"></div></div><div class="layer"><div class="sub">Dense 128 → 64</div><div id="layer2" class="heat"></div></div></div><div><div class="sub">Output logits · validity mask · selected action</div><div id="output" class="output"></div></div></div></main></div>
<script>
const el=id=>document.getElementById(id);function cells(root,values,kind){root.innerHTML='';values.forEach((v,i)=>{let d=document.createElement('div');d.className='cell '+(v?kind:'');d.textContent=v?'1':'0';root.appendChild(d)})}function heat(root,values){root.innerHTML='';let max=Math.max(...values.map(Math.abs),1e-6);values.forEach(v=>{let d=document.createElement('div');d.className='neuron';d.style.setProperty('--a',Math.min(1,Math.abs(v)/max));d.title=v.toFixed(4);root.appendChild(d)})}
async function tick(){try{let s=await(await fetch('/api/neural')).json();cells(el('blueprint'),s.blueprint,'on');cells(el('built'),s.built,'built');heat(el('layer0'),s.layers.layer0);heat(el('layer2'),s.layers.layer2);el('output').innerHTML='';s.logits.slice(0,25).forEach((v,i)=>{let d=document.createElement('div');d.className='logit '+(s.valid.includes(i)?'valid ':'')+(s.action===i?'selected':'');d.textContent=i+'\n'+v.toFixed(2);el('output').appendChild(d)});el('step').textContent=s.step+'/9';el('target').textContent=s.action===25?'DONE':s.action;el('confidence').textContent=(s.confidence*100).toFixed(1)+'%';el('trace').textContent='valid actions: ['+s.valid.join(', ')+']\nchosen cell: '+s.action+'\nmasked policy: active\nvision features: not connected';el('status').textContent='MODEL ONLINE'}catch(e){el('status').textContent='MODEL OFFLINE'}}setInterval(tick,300);tick();
</script>"""


class NeuralState:
    def __init__(self, checkpoint: Path) -> None:
        import torch

        self.model = create_objective_selector()
        saved = torch.load(checkpoint, map_location="cpu", weights_only=True)
        self.model.load_state_dict(saved["state_dict"])
        self.model.eval()
        self.activations: dict[str, list[float]] = {}
        self.value: dict = {}
        self.lock = Lock()
        for name in ("0", "2", "4"):
            self.model[int(name)].register_forward_hook(self._capture(f"layer{name}"))

    def _capture(self, name: str):
        def hook(_module, _inputs, output) -> None:
            self.activations[name] = [round(float(value), 5) for value in output[0].detach().tolist()]
        return hook

    def evaluate(self, column_heights: list[int]) -> int:
        import torch

        blueprint, built = masks(3, 3, tuple(column_heights))
        features = tuple(blueprint + built)
        action = select_action(self.model, features)
        with torch.no_grad():
            logits_tensor = self.model(torch.tensor([features], dtype=torch.float32))[0]
            valid = valid_actions(features)
            probabilities = torch.softmax(logits_tensor[valid], dim=0)
            confidence = float(probabilities[valid.index(action)].item())
        with self.lock:
            self.value = {
                "blueprint": blueprint,
                "built": built,
                "layers": {"layer0": self.activations["layer0"], "layer2": self.activations["layer2"]},
                "logits": [round(float(value), 5) for value in logits_tensor.tolist()],
                "valid": valid,
                "action": action,
                "confidence": confidence,
                "step": sum(column_heights),
            }
        return action


def run_demo(state: NeuralState) -> None:
    column_heights = [0, 0, 0]
    while True:
        action = state.evaluate(column_heights)
        sleep(1.0)
        if action == COMPLETE_ACTION:
            sleep(2.0)
            column_heights = [0, 0, 0]
            continue
        x, y = action % MAX_WIDTH, action // MAX_WIDTH
        if x < 3 and y == column_heights[x]:
            column_heights[x] += 1


def serve(state: NeuralState, host: str = "127.0.0.1", port: int = 8766) -> ThreadingHTTPServer:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            if self.path == "/api/neural":
                with state.lock:
                    body = json.dumps(state.value).encode()
                content_type = "application/json"
            else:
                body = PAGE.encode()
                content_type = "text/html; charset=utf-8"
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, _format: str, *_args: object) -> None:
            return

    server = ThreadingHTTPServer((host, port), Handler)
    Thread(target=server.serve_forever, daemon=True).start()
    return server


def main() -> None:
    parser = argparse.ArgumentParser(description="Serve Obsidian neural visualization")
    parser.add_argument("--checkpoint", type=Path, default=Path("checkpoints/objective-selector-v0.pt"))
    parser.add_argument("--port", type=int, default=8766)
    args = parser.parse_args()
    state = NeuralState(args.checkpoint)
    state.evaluate([0, 0, 0])
    server = serve(state, port=args.port)
    Thread(target=run_demo, args=(state,), daemon=True).start()
    print(f"Obsidian neural visualization: http://127.0.0.1:{args.port}")
    try:
        while True:
            sleep(1)
    except KeyboardInterrupt:
        server.shutdown()


if __name__ == "__main__":
    main()
