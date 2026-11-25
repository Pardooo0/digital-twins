"""Etapa M2 — prueba de la microSD en el ESP32-C3 (MicroPython).

Monta la tarjeta por SPI, graba filas del tamaño real del CSV con flush() + os.sync() (como lo hará la caja
negra), mide cuánto tarda cada fila, las vuelve a leer y reporta capacidad y formato.

Conexiones: SCK→GPIO4, MISO→GPIO5, MOSI→GPIO6, CS→GPIO7, VCC→5V, GND→GND.
Uso (desde la PC):  mpremote connect COM9 run caja-negra-esp32/pruebas_hardware/prueba_sd.py
Requiere sdcard.py (micropython-lib) en la flash del ESP32.
"""

import os
import time

from machine import SPI, Pin

import sdcard

try:  # MicroPython ≥ 1.23: montaje en el módulo vfs
    import vfs
except ImportError:
    vfs = os

FILAS = 200
FILA = ("sesion_0001,{n},{t:.3f},2026-11-24T20:26:47.000Z,gps,20.1389000,-101.1509000,1902.2,2,7,1.4,"
        "24.4,53.8,1.0,,,esp-0.1.0\n")

print("== Prueba de la microSD (etapa M2)")
spi = SPI(1, baudrate=1_000_000, sck=Pin(4), mosi=Pin(6), miso=Pin(5))
try:
    tarjeta = sdcard.SDCard(spi, Pin(7, Pin.OUT))
except OSError as e:
    print("ERROR: no responde la tarjeta:", e)
    print("Revisa: VCC del adaptador en 5V, GND común, SCK 4 / MISO 5 / MOSI 6 / CS 7, tarjeta bien insertada.")
    raise SystemExit
vfs.mount(vfs.VfsFat(tarjeta), "/sd")

st = os.statvfs("/sd")
print("Montada en /sd: capacidad %.2f GB, libre %.2f GB, bloque %d bytes"
      % (st[0] * st[2] / 1e9, st[0] * st[3] / 1e9, st[0]))

ruta = "/sd/prueba_m2.csv"
tiempos = []
with open(ruta, "w") as f:
    f.write("sesion,seq,t_mono_s,utc,fuente_hora,lat,lon,alt_m,fix,sats,hdop,temp_c,hr_pct,"
            "dht_edad_s,espesor_mm,banderas,version\n")
    t0 = time.ticks_ms()
    for n in range(1, FILAS + 1):
        inicio = time.ticks_us()
        f.write(FILA.format(n=n, t=time.ticks_diff(time.ticks_ms(), t0) / 1000))
        f.flush()
        os.sync()  # como el fsync de la Pi: un corte de energía pierde como máximo la última fila
        tiempos.append(time.ticks_diff(time.ticks_us(), inicio) / 1000)

tiempos.sort()
print("Escritura de %d filas con flush + sync: media %.1f ms, mediana %.1f ms, p95 %.1f ms, máx %.1f ms"
      % (FILAS, sum(tiempos) / FILAS, tiempos[FILAS // 2], tiempos[int(FILAS * 0.95)], tiempos[-1]))

with open(ruta) as f:
    lineas = f.read().splitlines()
ok = len(lineas) == FILAS + 1 and lineas[-1].startswith("sesion_0001,%d," % FILAS)
print("Lectura: %d líneas (encabezado + %d filas) -> %s" % (len(lineas), len(lineas) - 1,
                                                         "OK" if ok else "ERROR: faltan filas"))
print("Archivo de prueba:", ruta, "(%d bytes)" % os.stat(ruta)[6])
vfs.umount("/sd")
print("Desmontada. Resultado:", "OK" if ok else "FALLÓ")
