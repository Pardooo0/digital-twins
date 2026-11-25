# Se ejecuta EN WINDOWS con el ESP32 conectado: pone en hora el DS3231 con la hora UTC de la PC.
#   .\caja-negra-esp32\scripts\ajustar_rtc.ps1 [-Puerto COM9]
# Precisión de ~1 s: basta, porque con fix del GPS la caja vuelve a ajustar el reloj con la hora del GPS.
param(
    [string]$Puerto = "COM9",
    [string]$Mpremote = "$env:USERPROFILE\.venvs\esp32\Scripts\mpremote.exe"
)
$ErrorActionPreference = "Stop"
$u = (Get-Date).ToUniversalTime().AddSeconds(1)   # +1 s: lo que tarda en llegar la orden al ESP32
$codigo = "from machine import I2C, Pin; import ds3231; " +
          "r = ds3231.DS3231(I2C(0, sda=Pin(1), scl=Pin(0), freq=100000)); " +
          "r.ajustar($($u.Year), $($u.Month), $($u.Day), $($u.Hour), $($u.Minute), $($u.Second)); " +
          "print('Reloj ajustado a', r.leer(), 'UTC; perdio la hora:', r.perdio_hora())"
& $Mpremote connect $Puerto exec $codigo
if ($LASTEXITCODE -ne 0) { throw "No se pudo ajustar el reloj (¿está conectado el DS3231 y ds3231.py en el ESP32?)" }
