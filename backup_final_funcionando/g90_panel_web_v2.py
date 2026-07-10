#!/usr/bin/env python3
import json
import subprocess
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

HOST = "0.0.0.0"
PORT = 8088
LOG_FILE = Path.home() / "alarma" / "g90_eventos_base.jsonl"
CONTROL_SCRIPT = Path.home() / "alarma" / "g90_serial_control.expect"

CONTROL_COMMANDS = {
    "arm_total": "Armado total",
    "arm_parcial": "Armado parcial",
    "disarm": "Desarmado",
}

ARM_STATES = {
    "ARMADO TOTAL",
    "ARMADO PARCIAL",
    "DESARMADO",
    "ARMADO TOTAL DESDE MANDO",
    "ARMADO PARCIAL DESDE MANDO",
    "DESARMADO DESDE MANDO",
}

ZONE_STATES = {
    "ZONA CABLEADA 1 - ACTIVADA": 1,
    "ZONA CABLEADA 2 - ACTIVADA": 2,
    "ZONA CABLEADA 3 - ACTIVADA": 3,
    "ZONA CABLEADA 4 - ACTIVADA": 4,
}

SOS_STATES = {
    "SOS",
    "SOS DESDE MANDO - DETALLE ORIGEN",
    "SOS DESDE PANEL - DETALLE ORIGEN",
}

def parse_iso(text):
    if not text or text == "None":
        return None
    try:
        return datetime.fromisoformat(text)
    except Exception:
        return None

def now_local():
    return datetime.now().astimezone()

def connection_state(last_device_packet_time, last_event_time):
    ref = parse_iso(last_device_packet_time) or parse_iso(last_event_time)
    if not ref:
        return {
            "text": "SIN DATOS",
            "level": "unknown",
            "age_seconds": None,
        }
    age = (now_local() - ref.astimezone()).total_seconds()
    if age < 90:
        return {"text": "RECIBIENDO", "level": "ok", "age_seconds": int(age)}
    if age < 240:
        return {"text": "SIN TRÁFICO RECIENTE", "level": "warn", "age_seconds": int(age)}
    return {"text": "DESCONECTADO / SILENCIOSO", "level": "bad", "age_seconds": int(age)}

def summarize_from_jsonl(path: Path):
    state = {
        "log_path": str(path),
        "exists": path.exists(),
        "arm_state": "DESCONOCIDO",
        "arm_source": "-",
        "last_event": None,
        "last_sos": None,
        "last_device_packet_time": None,
        "last_upstream_packet_time": None,
        "zones": {
            "1": {"state": "REPOSO", "time": None},
            "2": {"state": "REPOSO", "time": None},
            "3": {"state": "REPOSO", "time": None},
            "4": {"state": "REPOSO", "time": None},
        },
        "recent_events": [],
    }

    if not path.exists():
        state["connection"] = connection_state(None, None)
        return state

    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
    except Exception as e:
        state["error"] = f"No se pudo leer el fichero: {e}"
        state["connection"] = connection_state(None, None)
        return state

    recent = []
    for raw in lines[-300:]:
        raw = raw.strip()
        if not raw:
            continue
        try:
            event = json.loads(raw)
        except Exception:
            continue

        ts = event.get("ts")
        kind = event.get("kind")
        ev_state = event.get("state")

        if kind == "status_raw":
            state["last_event"] = {
                "ts": ts,
                "text": ev_state,
                "code_hex": event.get("code_hex"),
                "source": "raw",
            }
            if ev_state in ARM_STATES:
                state["arm_state"] = ev_state
                state["arm_source"] = "raw"
            if ev_state in SOS_STATES:
                state["last_sos"] = {"ts": ts, "text": ev_state}
            if ev_state in ZONE_STATES:
                zone = str(ZONE_STATES[ev_state])
                state["zones"][zone]["state"] = "ACTIVADA"
                state["zones"][zone]["time"] = ts

        elif kind == "armdisarm":
            st = event.get("state")
            state["arm_state"] = st
            state["arm_source"] = "callback"
            state["last_event"] = {
                "ts": ts,
                "text": st,
                "source": "callback",
            }

        elif kind == "watchdog":
            state["last_device_packet_time"] = event.get("last_device_packet_time")
            state["last_upstream_packet_time"] = event.get("last_upstream_packet_time")

        recent.append(event)

    state["recent_events"] = recent[-30:]
    last_event_ts = state["last_event"]["ts"] if state["last_event"] else None
    state["connection"] = connection_state(state["last_device_packet_time"], last_event_ts)
    return state


def run_control_command(cmd: str):
    if cmd not in CONTROL_COMMANDS:
        return {
            "ok": False,
            "cmd": cmd,
            "message": "Comando no válido",
        }

    if not CONTROL_SCRIPT.exists():
        return {
            "ok": False,
            "cmd": cmd,
            "message": f"No existe el script de control: {CONTROL_SCRIPT}",
        }

    try:
        result = subprocess.run(
            [str(CONTROL_SCRIPT), cmd],
            cwd=str(Path.home() / "alarma"),
            capture_output=True,
            text=True,
            timeout=15,
        )

        ok = result.returncode == 0
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()

        return {
            "ok": ok,
            "cmd": cmd,
            "label": CONTROL_COMMANDS[cmd],
            "returncode": result.returncode,
            "stdout": out,
            "stderr": err,
            "message": out if ok else (err or out or "Error ejecutando comando"),
        }

    except subprocess.TimeoutExpired:
        return {
            "ok": False,
            "cmd": cmd,
            "message": "Timeout ejecutando comando de control",
        }

    except Exception as e:
        return {
            "ok": False,
            "cmd": cmd,
            "message": repr(e),
        }

INDEX_HTML = """<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>Alarma G90</title>
  <style>
    body { font-family: system-ui, sans-serif; margin: 0; background: #f5f5f5; color: #222; }
    .wrap { max-width: 980px; margin: 0 auto; padding: 12px; }
    .grid { display: grid; gap: 12px; }
    .top { grid-template-columns: 1fr; }
    @media (min-width: 800px) { .top { grid-template-columns: 1.2fr 1fr; } }
    .zones { grid-template-columns: repeat(2,1fr); }
    @media (min-width: 700px) { .zones { grid-template-columns: repeat(4,1fr); } }
    .card { background: white; border-radius: 14px; padding: 14px; box-shadow: 0 1px 6px rgba(0,0,0,.08); }
    .title { font-size: 14px; color: #666; margin-bottom: 8px; }
    .big { font-size: 28px; font-weight: 700; padding: 10px 12px; border-radius: 12px; display: inline-block; }
    .ok { background: #5cb85c; color: white; }
    .warn { background: #f0ad4e; color: #111; }
    .bad { background: #d9534f; color: white; }
    .unknown { background: #cccccc; color: #111; }
    .row { margin: 6px 0; }
    .muted { color: #666; }
    .zonebox { text-align: center; padding: 12px; border-radius: 12px; }
    .zonebox.active { background: #d9534f; color: white; }
    .zonebox.idle { background: #5cb85c; color: white; }
    .list { max-height: 360px; overflow: auto; }
    .item { padding: 8px 0; border-bottom: 1px solid #eee; }
    .small { font-size: 13px; }
    .header { display: flex; justify-content: space-between; align-items: center; gap: 12px; margin-bottom: 12px; }
    button { border: 0; background: #222; color: white; padding: 10px 12px; border-radius: 10px; cursor: pointer; }
    .controls { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 12px; }
    .btn-arm-total { background: #b02a37; }
    .btn-arm-home { background: #d99000; color: #111; }
    .btn-disarm { background: #27864b; }
    .control-status { margin-top: 10px; padding: 8px 10px; border-radius: 10px; background: #f3f3f3; }
    .control-status.okmsg { background: #dff0d8; color: #245b2e; }
    .control-status.errmsg { background: #f8d7da; color: #842029; }
    code { background: #f3f3f3; padding: 2px 5px; border-radius: 6px; }
  </style>
</head>
<body>
  <div class="wrap">
    <div class="header">
      <div>
        <h2 style="margin:0;">Estado alarma G90</h2>
        <div class="muted small">Panel web local para Android y PC</div>
      </div>
      <button onclick="loadState()">Actualizar</button>
    </div>

    <div class="grid top">
      <div class="card">
        <div class="title">Estado general</div>
        <div id="armState" class="big unknown">DESCONOCIDO</div>
        <div class="row small muted">Origen: <span id="armSource">-</span></div>
        <div class="row small muted">Último evento: <span id="lastEvent">-</span></div>
        <div class="row small muted">Último SOS: <span id="lastSos">-</span></div>

        <div class="controls">
          <button class="btn-arm-total" onclick="sendControl('arm_total')">Armado total</button>
          <button class="btn-arm-home" onclick="sendControl('arm_parcial')">Armado parcial</button>
          <button class="btn-disarm" onclick="sendControl('disarm')">Desarmar</button>
        </div>
        <div id="controlStatus" class="control-status small muted">Control preparado</div>
      </div>

      <div class="card">
        <div class="title">Conexión</div>
        <div id="connState" class="big unknown">SIN DATOS</div>
        <div class="row small muted">Último paquete del dispositivo: <span id="lastDevicePacket">-</span></div>
        <div class="row small muted">Último paquete upstream: <span id="lastUpstreamPacket">-</span></div>
        <div class="row small muted">Fichero: <code id="logPath"></code></div>
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="title">Zonas cableadas</div>
      <div class="grid zones">
        <div>
          <div class="zonebox idle" id="zone1">Zona 1<br><strong>REPOSO</strong></div>
          <div class="small muted" id="zone1time">Sin eventos</div>
        </div>
        <div>
          <div class="zonebox idle" id="zone2">Zona 2<br><strong>REPOSO</strong></div>
          <div class="small muted" id="zone2time">Sin eventos</div>
        </div>
        <div>
          <div class="zonebox idle" id="zone3">Zona 3<br><strong>REPOSO</strong></div>
          <div class="small muted" id="zone3time">Sin eventos</div>
        </div>
        <div>
          <div class="zonebox idle" id="zone4">Zona 4<br><strong>REPOSO</strong></div>
          <div class="small muted" id="zone4time">Sin eventos</div>
        </div>
      </div>
    </div>

    <div class="card" style="margin-top:12px;">
      <div class="title">Eventos recientes</div>
      <div class="list" id="events"></div>
    </div>
  </div>

<script>
function levelClass(text) {
  if ((text || "").startsWith("ARMADO TOTAL")) return "bad";
  if ((text || "").startsWith("ARMADO PARCIAL")) return "warn";
  if ((text || "").startsWith("DESARMADO")) return "ok";
  if ((text || "").includes("RECIBIENDO")) return "ok";
  if ((text || "").includes("SIN TRÁFICO")) return "warn";
  if ((text || "").includes("DESCONECTADO")) return "bad";
  return "unknown";
}

function setBig(el, text) {
  el.textContent = text || "-";
  el.className = "big " + levelClass(text || "");
}

function setZone(zoneNum, info) {
  const box = document.getElementById("zone" + zoneNum);
  const time = document.getElementById("zone" + zoneNum + "time");
  const active = info && info.state === "ACTIVADA";
  box.className = "zonebox " + (active ? "active" : "idle");
  box.innerHTML = "Zona " + zoneNum + "<br><strong>" + (active ? "ACTIVADA" : "REPOSO") + "</strong>";
  time.textContent = info && info.time ? info.time : "Sin eventos";
}

function fmtEvent(ev) {
  const ts = ev.ts || "";
  if (ev.kind === "status_raw") {
    return `${ts} | RAW | ${ev.state || ""} | code=${ev.code_hex || ""}`;
  }
  if (ev.kind === "armdisarm") {
    return `${ts} | CALLBACK | ${ev.state || ""}`;
  }
  if (ev.kind === "watchdog") {
    return `${ts} | WATCHDOG | last_device=${ev.last_device_packet_time || ""}`;
  }
  return `${ts} | ${ev.kind || ""}`;
}

async function sendControl(cmd) {
  const box = document.getElementById("controlStatus");
  box.className = "control-status small muted";
  box.textContent = "Enviando orden...";

  try {
    const res = await fetch("/control/" + cmd, {cache: "no-store"});
    const data = await res.json();

    if (data.ok) {
      box.className = "control-status small okmsg";
      box.textContent = data.message || "Orden enviada";
    } else {
      box.className = "control-status small errmsg";
      box.textContent = data.message || "Error enviando orden";
    }

    setTimeout(loadState, 1000);
  } catch (e) {
    box.className = "control-status small errmsg";
    box.textContent = "Error: " + e;
  }
}

async function loadState() {
  try {
    const res = await fetch("/api/state", {cache: "no-store"});
    const data = await res.json();

    setBig(document.getElementById("armState"), data.arm_state || "DESCONOCIDO");
    document.getElementById("armSource").textContent = data.arm_source || "-";
    document.getElementById("lastEvent").textContent = data.last_event ? `${data.last_event.ts} | ${data.last_event.text}` : "-";
    document.getElementById("lastSos").textContent = data.last_sos ? `${data.last_sos.ts} | ${data.last_sos.text}` : "-";

    setBig(document.getElementById("connState"), data.connection ? data.connection.text : "SIN DATOS");
    document.getElementById("lastDevicePacket").textContent = data.last_device_packet_time || "-";
    document.getElementById("lastUpstreamPacket").textContent = data.last_upstream_packet_time || "-";
    document.getElementById("logPath").textContent = data.log_path || "-";

    setZone(1, data.zones["1"]);
    setZone(2, data.zones["2"]);
    setZone(3, data.zones["3"]);
    setZone(4, data.zones["4"]);

    const events = document.getElementById("events");
    events.innerHTML = "";
    for (const ev of (data.recent_events || []).slice().reverse()) {
      const div = document.createElement("div");
      div.className = "item small";
      div.textContent = fmtEvent(ev);
      events.appendChild(div);
    }
  } catch (e) {
    document.getElementById("lastEvent").textContent = "Error cargando estado: " + e;
  }
}

loadState();
setInterval(loadState, 2000);
</script>
</body>
</html>
"""

class Handler(BaseHTTPRequestHandler):
    def _send_bytes(self, payload: bytes, content_type: str, status: int = 200):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/":
            self._send_bytes(INDEX_HTML.encode("utf-8"), "text/html; charset=utf-8")
            return
        if path == "/api/state":
            data = summarize_from_jsonl(LOG_FILE)
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send_bytes(payload, "application/json; charset=utf-8")
            return
        if path.startswith("/control/"):
            cmd = path.split("/", 2)[2]
            data = run_control_command(cmd)
            status = 200 if data.get("ok") else 500
            payload = json.dumps(data, ensure_ascii=False).encode("utf-8")
            self._send_bytes(payload, "application/json; charset=utf-8", status=status)
            return
        self._send_bytes(b"No encontrado", "text/plain; charset=utf-8", status=404)

    def log_message(self, format, *args):
        return

def main():
    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Panel web G90 escuchando en http://127.0.0.1:{PORT}")
    print(f"En la red local: http://192.168.1.78:{PORT}")
    print(f"Leyendo eventos de: {LOG_FILE}")
    server.serve_forever()

if __name__ == "__main__":
    main()
