#!/usr/bin/env bash
set -euo pipefail

systemctl restart g90-listener.service
systemctl restart g90-panel-web.service
systemctl restart g90-redireccion.timer
systemctl start g90-redireccion.service
