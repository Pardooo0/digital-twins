# Se ejecuta EN WINDOWS: baja las sesiones de la Pi a gemelo/datos/cajanegra.
#   .\caja-negra\scripts\descargar.ps1 [-Usuario host] [-Equipo cajanegra]
param(
    [string]$Usuario = "host",
    [string]$Equipo = "cajanegra"
)
$ErrorActionPreference = "Stop"
$raiz = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)   # raíz del repo
$destino = Join-Path $raiz "gemelo\datos\cajanegra"
New-Item -ItemType Directory -Force $destino | Out-Null

scp "${Usuario}@${Equipo}:~/cajanegra/datos/sesion_*" "$destino\"
if ($LASTEXITCODE -ne 0) { throw "Falló scp" }
Get-ChildItem $destino -Filter "sesion_*" | Select-Object Name, Length, LastWriteTime
