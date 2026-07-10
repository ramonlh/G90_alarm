#!/usr/bin/env bash
set -euo pipefail

cd /home/ramon/alarma
source /home/ramon/g90env/bin/activate

# 1) Arrancar listener en segundo plano
python3 /home/ramon/alarma/g90_monitor_hibrido_base_v7.py &
LISTENER_PID=$!

# 2) Esperar un poco para que abra el puerto 5678
sleep 3

# 3) Reaplicar la redirección dentro de la alarma
/home/ramon/alarma/g90_reaplica_redireccion.sh

# 4) Mantener el proceso del listener como principal
wait $LISTENER_PID
