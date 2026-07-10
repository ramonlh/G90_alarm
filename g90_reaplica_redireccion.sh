#!/usr/bin/env bash
set -euo pipefail

ALARMA_IP="192.168.1.149"
ALARMA_USER="admin"
ALARMA_PASS="admin"
NUBE_REAL_IP="47.88.7.61"
PC_IP="192.168.1.78"
PUERTO="5678"

SCRIPT_EXPECT="/home/ramon/alarma/redirige_nube_alarma_final.expect"

if [ ! -x "$SCRIPT_EXPECT" ]; then
  echo "No existe o no es ejecutable: $SCRIPT_EXPECT" >&2
  exit 1
fi

exec "$SCRIPT_EXPECT"   "$ALARMA_IP" "$ALARMA_USER" "$ALARMA_PASS"   "$NUBE_REAL_IP" "$PC_IP" "$PUERTO"
