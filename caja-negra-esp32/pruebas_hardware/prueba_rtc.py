"""Etapa M2 — prueba del reloj DS3231 (I²C: SDA=GPIO1, SCL=GPIO0, VCC a 3.3 V).

Busca el reloj en el bus, muestra su hora (UTC), si perdió la hora (bandera OSF), su temperatura interna y
cuánto avanza en 5 s. Para ponerlo en hora se usa  scripts/ajustar_rtc.ps1  (toma la hora UTC de la PC).

Uso:  mpremote connect COM9 run caja-negra-esp32/pruebas_hardware/prueba_rtc.py
Requiere ds3231.py en la flash del ESP32.
"""

import time

from machine import I2C, Pin

import ds3231

i2c = I2C(0, sda=Pin(1), scl=Pin(0), freq=100_000)
encontrados = i2c.scan()
print("== Prueba del reloj DS3231 (etapa M2)")
print("Dispositivos I2C:", [hex(d) for d in encontrados] or "ninguno",
      "| DS3231 (0x68):", "SÍ" if 0x68 in encontrados else "NO",
      "| EEPROM AT24C32 (0x57):", "SÍ" if 0x57 in encontrados else "NO")
if 0x68 not in encontrados:
    print("No se encontró el DS3231. Revisa: VCC→3.3V, GND, SDA→GPIO1, SCL→GPIO0, y el contacto de la placa.")
    raise SystemExit

rtc = ds3231.DS3231(i2c)
fmt = "%04d-%02d-%02d %02d:%02d:%02d UTC"
a = rtc.leer()
print("Hora del reloj:", fmt % a)
print("¿Perdió la hora? (OSF):", "SÍ — hay que ajustarlo" if rtc.perdio_hora() else "NO — la hora es confiable")
print("Temperatura interna: %.2f °C" % rtc.temperatura())
time.sleep(5)
b = rtc.leer()
print("Hora 5 s después:", fmt % b, "(debe haber avanzado 5 s)")
