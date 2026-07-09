#!/usr/bin/env bash
set -euo pipefail

echo "Recargando systemd..."
sudo systemctl daemon-reload

echo "Desactivando servicio antiguo si existe..."
sudo systemctl disable --now g90-monitor.service 2>/dev/null || true

echo "Activando listener, web y timer al arranque..."
sudo systemctl enable --now g90-listener.service
sudo systemctl enable --now g90-panel-web.service
sudo systemctl enable --now g90-redireccion.timer

echo
echo "Estado actual:"
systemctl status g90-listener.service --no-pager -l || true
echo
systemctl status g90-panel-web.service --no-pager -l || true
echo
systemctl status g90-redireccion.timer --no-pager -l || true

echo
echo "Hecho."
echo "Tras reiniciar el PC deberían arrancar solos:"
echo "  - g90-listener.service"
echo "  - g90-panel-web.service"
echo "  - g90-redireccion.timer"
