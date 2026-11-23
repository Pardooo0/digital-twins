# Se ejecuta EN WINDOWS: copia el código a ~/cajanegra en la Pi y reinicia el servicio.
#   .\caja-negra\scripts\deploy.ps1 [-Usuario host] [-Equipo cajanegra]
# No toca ~/cajanegra/datos ni el .venv de la Pi.
param(
    [string]$Usuario = "host",
    [string]$Equipo = "cajanegra"
)
$ErrorActionPreference = "Stop"
$origen = Split-Path -Parent $PSScriptRoot   # carpeta caja-negra
$destino = "$Usuario@$Equipo"
$paquete = Join-Path $env:TEMP "cajanegra.tgz"

# tar a archivo (no por tubería: PowerShell 5.1 corrompe datos binarios en tuberías)
tar -czf $paquete -C $origen --exclude=__pycache__ cajanegra config.yaml requirements.txt systemd scripts tests/verificar_sesion.py
if ($LASTEXITCODE -ne 0) { throw "Falló tar" }

scp $paquete "${destino}:/tmp/cajanegra.tgz"
if ($LASTEXITCODE -ne 0) { throw "Falló scp" }

# Si el servicio aún no existe (primera vez), avisa en lugar de fallar.
ssh -t $destino "mkdir -p ~/cajanegra && tar -xzf /tmp/cajanegra.tgz -C ~/cajanegra && rm /tmp/cajanegra.tgz && if [ -f /etc/systemd/system/cajanegra.service ]; then sudo systemctl restart cajanegra && systemctl --no-pager status cajanegra | head -5; else echo 'Primera vez: ejecuta  bash ~/cajanegra/scripts/instalar.sh  en la Pi'; fi"
Remove-Item $paquete
