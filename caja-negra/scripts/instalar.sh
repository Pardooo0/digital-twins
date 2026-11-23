#!/usr/bin/env bash
# Se ejecuta EN LA PI, una vez (y de nuevo si cambian requirements.txt o el .service):
#   bash ~/cajanegra/scripts/instalar.sh
set -euo pipefail
cd "$(dirname "$0")/.."

# --system-site-packages: gpiozero viene de apt (python3-gpiozero)
python3 -m venv --system-site-packages .venv
.venv/bin/pip install -r requirements.txt

# Acceso al puerto serie y a los GPIO sin sudo
sudo usermod -aG dialout,gpio "$USER"

sed "s|__USUARIO__|$USER|g; s|__DIR__|$PWD|g" systemd/cajanegra.service \
  | sudo tee /etc/systemd/system/cajanegra.service > /dev/null
sudo systemctl daemon-reload
sudo systemctl enable cajanegra
sudo systemctl restart cajanegra

echo "Listo. Ver el registro en vivo con: journalctl -u cajanegra -f"
