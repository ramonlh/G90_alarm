import asyncio
from pyg90alarm import G90Alarm

async def main():
    equipos = await G90Alarm.discover()
    if not equipos:
        print("No se han encontrado paneles G90 en la red local.")
        return

    print("Paneles encontrados:")
    for eq in equipos:
        print(eq)

asyncio.run(main())
