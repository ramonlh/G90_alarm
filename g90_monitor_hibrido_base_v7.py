#!/usr/bin/env python3
import asyncio
import json
import logging
import re
from datetime import datetime, timezone

from pyg90alarm import G90Alarm
from pyg90alarm.const import G90ArmDisarmTypes
from pyg90alarm.local.alert_config import G90AlertConfigFlags

PANEL_IP = "192.168.11.133"
PC_IP = "192.168.11.128"
PORT = 5678
EVENTS_FILE = "g90_eventos_base.jsonl"

STATUS_HDR = bytes.fromhex("21 10 00 20 34 00 00 00")
HEARTBEAT = bytes.fromhex("01 10 00 00 08 00 00 00")

STATE_MAP = {
    bytes.fromhex("04 00 00 01"): "ARMADO TOTAL",
    bytes.fromhex("03 00 00 03"): "DESARMADO",
    bytes.fromhex("09 00 00 02"): "ARMADO PARCIAL",
    bytes.fromhex("66 00 0A 06"): "ARMADO TOTAL DESDE MANDO",
    bytes.fromhex("66 00 0A 07"): "ARMADO PARCIAL DESDE MANDO",
    bytes.fromhex("66 00 0A 08"): "DESARMADO DESDE MANDO",
    bytes.fromhex("66 00 0A 09"): "SOS",
    bytes.fromhex("63 00 00 01"): "SOS DESDE MANDO - DETALLE ORIGEN",
    bytes.fromhex("63 00 00 02"): "SOS DESDE PANEL - DETALLE ORIGEN",
    bytes.fromhex("C5 00 08 01"): "ZONA CABLEADA 2 - ACTIVADA",
    bytes.fromhex("C6 00 03 01"): "ZONA CABLEADA 3 - ACTIVADA",
    bytes.fromhex("C4 00 02 01"): "ZONA CABLEADA 1 - ACTIVADA",
    bytes.fromhex("C7 00 03 01"): "ZONA CABLEADA 4 - ACTIVADA",
}

ARM_MAP = {
    G90ArmDisarmTypes.ARM_AWAY: "ARMADO TOTAL",
    G90ArmDisarmTypes.DISARM: "DESARMADO",
    G90ArmDisarmTypes.ARM_HOME: "ARMADO PARCIAL",
}

HEX_RE = re.compile(r"Data:\s*'([0-9A-Fa-f ]+)'")

def ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def iso_now() -> str:
    return datetime.now().astimezone().isoformat()

def save_event(kind: str, **data) -> None:
    row = {"ts": iso_now(), "kind": kind, **data}
    line = json.dumps(row, ensure_ascii=False)
    print(line)
    with open(EVENTS_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def decode_status_frame(frame: bytes):
    if len(frame) < 52:
        return None
    code = frame[12:16]
    state = STATE_MAP.get(code, f"DESCONOCIDO({code.hex()})")
    unix_ts = int.from_bytes(frame[-4:], "little")
    try:
        human = datetime.fromtimestamp(
            unix_ts, timezone.utc
        ).astimezone().strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        human = "timestamp inválido"
    return state, code.hex(), unix_ts, human

def scan_raw_blob(raw: bytes):
    out = []

    start = 0
    while True:
        i = raw.find(HEARTBEAT, start)
        if i < 0:
            break
        out.append(("HEARTBEAT", i))
        start = i + 1

    start = 0
    while True:
        i = raw.find(STATUS_HDR, start)
        if i < 0:
            break
        frame = raw[i:i + 52]
        decoded = decode_status_frame(frame)
        if decoded is not None:
            out.append(("STATUS", i, decoded))
        start = i + 1

    return out

class G90LogSniffer(logging.Handler):
    def emit(self, record):
        try:
            msg = record.getMessage()
        except Exception:
            return

        m = HEX_RE.search(msg)
        if not m:
            return

        hex_blob = m.group(1)
        try:
            raw = bytes.fromhex(hex_blob)
        except Exception:
            return

        items = scan_raw_blob(raw)
        for item in items:
            if item[0] == "HEARTBEAT":
                print(f"[{ts()}] HEARTBEAT detectado")
            elif item[0] == "STATUS":
                _, pos, decoded = item
                state, code_hex, unix_ts, human = decoded
                print(
                    f"[{ts()}] EVENTO_RAW -> {state} | code={code_hex} | "
                    f"ts={unix_ts} | {human} | pos={pos}"
                )
                save_event(
                    "status_raw",
                    state=state,
                    code_hex=code_hex,
                    unix_ts=unix_ts,
                    human=human,
                    pos=pos,
                    source="raw"
                )

async def cb_armdisarm(state):
    state_txt = ARM_MAP.get(state, str(state))
    print(f"[{ts()}] EVENTO_CB -> {state_txt}")
    save_event(
        "armdisarm",
        state=state_txt,
        state_enum=str(state),
        source="callback"
    )

async def ensure_notice_flags(alarm: G90Alarm) -> None:
    try:
        await asyncio.wait_for(
            alarm.alert_config.set_flag(G90AlertConfigFlags.ARM_DISARM, True),
            timeout=5.0
        )
        print(f"[{ts()}] Flag ARM_DISARM asegurada")
        save_event("notice_flag", flag="ARM_DISARM", value=True, result="ok")
    except Exception as e:
        print(
            f"[{ts()}] Aviso: no se pudo asegurar ARM_DISARM ({e}); "
            "continúo sin bloquear"
        )
        save_event(
            "notice_flag_warning",
            flag="ARM_DISARM",
            value=True,
            warning=str(e)
        )

async def watchdog(alarm: G90Alarm):
    while True:
        await asyncio.sleep(30)
        save_event(
            "watchdog",
            last_device_packet_time=str(alarm.last_device_packet_time),
            last_upstream_packet_time=str(alarm.last_upstream_packet_time),
        )

async def startup_probe(alarm: G90Alarm):
    await asyncio.sleep(1)
    try:
        info = await asyncio.wait_for(alarm.get_host_info(), timeout=3.0)
        save_event("startup_info", host_info=str(info))
    except Exception as e:
        save_event(
            "startup_probe_warning",
            step="get_host_info",
            warning=str(e)
        )
    try:
        status = await asyncio.wait_for(alarm.get_host_status(), timeout=3.0)
        save_event("startup_status", host_status=str(status))
    except Exception as e:
        save_event(
            "startup_probe_warning",
            step="get_host_status",
            warning=str(e)
        )

async def main():
    sniffer = G90LogSniffer()
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(sniffer)
    logging.getLogger("pyg90alarm").setLevel(logging.INFO)

    alarm = G90Alarm(host=PANEL_IP)

    print(f"[{ts()}] Configurando cloud server en la alarma...")
    await alarm.set_cloud_server_address(
        cloud_ip=PC_IP,
        cloud_port=PORT
    )

    print(f"[{ts()}] Preparando cloud notifications...")
    await alarm.use_cloud_notifications(
        cloud_ip=PC_IP,
        cloud_port=PORT,
        cloud_local_ip=PC_IP,
        cloud_local_port=PORT,
        upstream_host=None
    )

    print(f"[{ts()}] Intentando activar flag ARM_DISARM en la alarma...")
    await ensure_notice_flags(alarm)
    print(f"[{ts()}] Continuando con el arranque del listener...")

    alarm.armdisarm_callback.add(cb_armdisarm)

    print(f"[{ts()}] Arrancando listen_notifications() en {PC_IP}:{PORT} ...")
    await alarm.listen_notifications()

    save_event(
        "listener_start",
        panel_ip=PANEL_IP,
        listen_ip=PC_IP,
        port=PORT,
        mode="cloud_notifications"
    )

    asyncio.create_task(watchdog(alarm))
    asyncio.create_task(startup_probe(alarm))

    print(f"[{ts()}] Listener arrancado; esperando eventos...")
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
