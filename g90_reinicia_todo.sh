#!/usr/bin/env bash
set -euo pipefail

echo "Reiniciando listener y web..."
sudo systemctl restart g90-listener.service
sudo systemctl restart g90-panel-web.service

echo "Reiniciando timer..."
sudo systemctl restart g90-redireccion.timer

echo "Lanzando una reaplicación inmediata de redirección..."
sudo systemctl start g90-redireccion.service

echo
echo "Estado actual:"
systemctl status g90-listener.service --no-pager -l || true
echo
systemctl status g90-panel-web.service --no-pager -l || true
echo
systemctl status g90-redireccion.timer --no-pager -l || true
