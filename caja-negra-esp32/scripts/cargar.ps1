# Se ejecuta EN WINDOWS con el ESP32 conectado por USB: copia firmware/*.py a la flash del ESP32.
#   .\caja-negra-esp32\scripts\cargar.ps1 [-Puerto COM9] [-Mantenimiento]
# 1) pone la placa en modo mantenimiento (archivo /mantenimiento) y la reinicia, para que no grabe ni la
#    reinicie el watchdog mientras se copian los archivos; 2) copia; 3) quita el modo mantenimiento y reinicia
#    (empieza a grabar). Con -Mantenimiento la deja en mantenimiento (no graba al encender).
param(
    [string]$Puerto = "COM9",
    [switch]$Mantenimiento,
    [string]$Mpremote = "$env:USERPROFILE\.venvs\esp32\Scripts\mpremote.exe"
)
$ErrorActionPreference = "Stop"
$firmware = Join-Path (Split-Path -Parent $PSScriptRoot) "firmware"

function Invocar([string[]]$argumentos) {
    & $Mpremote connect $Puerto @argumentos
    if ($LASTEXITCODE -ne 0) { throw "mpremote falló: $($argumentos -join ' ')" }
}

Write-Host "1/3 Modo mantenimiento y reinicio..."
Invocar @("exec", "open('/mantenimiento','w').close()")
Invocar @("reset")
Start-Sleep -Seconds 4   # el USB del ESP32 se desconecta y reconecta al reiniciar

Write-Host "2/3 Copiando el firmware..."
$archivos = Get-ChildItem $firmware -Filter *.py | Sort-Object { $_.Name -eq "main.py" }, Name   # main.py al final
foreach ($a in $archivos) { Invocar @("cp", $a.FullName, ":$($a.Name)") }

if ($Mantenimiento) {
    Write-Host "3/3 Listo. La placa queda en MODO MANTENIMIENTO (no graba)."
} else {
    Write-Host "3/3 Quitando el modo mantenimiento y reiniciando: la caja negra empieza a grabar."
    Invocar @("exec", "import os; os.remove('/mantenimiento')")
    Invocar @("reset")
}
