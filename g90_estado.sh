#!/usr/bin/env bash
echo "==== SERVICIOS G90 ===="
echo
systemctl --no-pager --full status g90-listener.service | sed -n '1,12p'
echo
systemctl --no-pager --full status g90-panel-web.service | sed -n '1,12p'
echo
systemctl --no-pager --full status g90-redireccion.timer | sed -n '1,12p'
echo
echo "==== URLS ===="
echo "PC      : http://127.0.0.1:8088"
echo "Android : http://192.168.11.78:8088"
echo
echo "==== LOGS EN VIVO ===="
echo "Listener : journalctl -u g90-listener.service -f"
echo "Web      : journalctl -u g90-panel-web.service -f"
echo "Timer    : journalctl -u g90-redireccion.service -f"
