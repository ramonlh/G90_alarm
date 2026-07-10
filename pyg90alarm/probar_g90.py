import asyncio
from pyg90alarm import G90Alarm

PANEL_IP = "192.168.11.142"

async def main():
    alarm = G90Alarm(host=PANEL_IP)

    info = await alarm.get_host_info()
    status = await alarm.get_host_status()
    sensors = await alarm.get_sensors()

    print("=== INFO ===")
    print(info)
    print("\n=== STATUS ===")
    print(status)
    print(f"\n=== SENSORES ({len(sensors)}) ===")
    for s in sensors:
        print(s)

asyncio.run(main())
