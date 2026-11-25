"""Etapa M2 — prueba del shield GPS (NEO-6M) en el ESP32-C3.

Escucha el GPS 15 s por la UART1 (RX = GPIO20, 9600 baudios), cuenta las frases NMEA, verifica su checksum y
muestra lo último que dijo: calidad del fix, satélites, HDOP y hora UTC. Bajo techo es normal que no haya fix:
lo que se comprueba aquí es que los datos llegan bien.

Conexiones: 5V del shield → 5V; GND → GND; pin 2 del shield (TX del GPS) → GPIO20.
Uso:  mpremote connect COM9 run caja-negra-esp32/pruebas_hardware/prueba_gps.py
"""

import time

from machine import UART


def checksum_ok(linea):
    """`$CUERPO*HH` con HH = XOR de los caracteres de CUERPO."""
    if not linea.startswith("$") or len(linea) < 4 or linea[-3] != "*":
        return False
    x = 0
    for c in linea[1:-3]:
        x ^= ord(c)
    try:
        return x == int(linea[-2:], 16)
    except ValueError:
        return False


SEGUNDOS = 15
uart = UART(1, baudrate=9600, rx=20, tx=21, timeout=50)
print("== Prueba del GPS (etapa M2): escuchando %d s en GPIO20 a 9600 baudios..." % SEGUNDOS)
buf, total_bytes, validas, malas, tipos = b"", 0, 0, 0, {}
gga = rmc = None
t0 = time.ticks_ms()
while time.ticks_diff(time.ticks_ms(), t0) < SEGUNDOS * 1000:
    datos = uart.read()
    if not datos:
        continue
    total_bytes += len(datos)
    buf += datos
    while b"\n" in buf:
        crudo, buf = buf.split(b"\n", 1)
        linea = crudo.decode("ascii", "replace").strip()
        if not linea.startswith("$"):
            continue
        if checksum_ok(linea):
            validas += 1
            tipo = linea[3:6]
            tipos[tipo] = tipos.get(tipo, 0) + 1
            if tipo == "GGA":
                gga = linea
            elif tipo == "RMC":
                rmc = linea
        else:
            malas += 1

print("Bytes recibidos: %d | frases válidas: %d | con checksum malo: %d" % (total_bytes, validas, malas))
print("Tipos de frase:", tipos)
if gga:
    c = gga.split(",")
    print("Última GGA:", gga[:80])
    print("  hora UTC %s | fix %s | satélites %s | HDOP %s" % (c[1] or "-", c[6] or "0", c[7] or "0", c[8] or "-"))
if rmc:
    c = rmc.split(",")
    print("Última RMC: estado %s (A = válido, V = sin fix) | fecha %s" % (c[2] or "-", c[9] or "-"))
if total_bytes == 0:
    print("RESULTADO: no llega nada. Revisa: 5V y GND del shield, cable del pin 2 del shield a GPIO20, LED PWR encendido.")
elif validas == 0:
    print("RESULTADO: llegan bytes pero ninguna frase válida (¿velocidad distinta de 9600 o ruido en el cable?).")
else:
    print("RESULTADO: el GPS se comunica bien con el ESP32" + (" y tiene fix." if gga and gga.split(",")[6] not in ("", "0") else
                                                         "; aún sin fix (normal bajo techo)."))
