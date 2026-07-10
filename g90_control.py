#!/home/ramon/g90env/bin/python3
import sys
import json
import asyncio
from pathlib import Path
from datetime import datetime

from pyg90alarm import G90Alarm

PANEL_IP = "192.168.1.149"
LOG_FILE = Path("/home/ramon/alarma/g90_control_log.jsonl")


def log_event(command, result, detail=""):
    entry = {
        "ts": datetime.now().isoformat(timespec="seconds"),
        "command": command,
        "result": result,
        "detail": detail,
    }
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def send_command(cmd):
    alarm = G90Alarm(host=PANEL_IP)

    if cmd in ("arm_total", "away", "arm_away"):
        await alarm.arm_away()
        return "Armado total enviado"

    if cmd in ("arm_parcial", "home", "arm_home"):
        await alarm.arm_home()
        return "Armado parcial enviado"

    if cmd in ("disarm", "desarmar"):
        await alarm.disarm()
        return "Desarmado enviado"

    raise ValueError(f"Comando no reconocido: {cmd}")


async def main_async():
    if len(sys.argv) != 2:
        print("Uso:")
        print("  g90_control.py arm_total")
        print("  g90_control.py arm_parcial")
        print("  g90_control.py disarm")
        sys.exit(1)

    cmd = sys.argv[1].strip().lower()

    try:
        detail = await send_command(cmd)
        log_event(cmd, "ok", detail)
        print(f"OK: {detail}")

    except Exception as e:
        log_event(cmd, "error", repr(e))
        print(f"ERROR: {e!r}")
        sys.exit(3)


if __name__ == "__main__":
    asyncio.run(main_async())
