"""Etapa M3 — corre la caja negra 60 filas sin watchdog y muestra el resultado (prueba desde la PC).

Uso (con el firmware cargado y la placa en modo mantenimiento):
    mpremote connect COM9 run caja-negra-esp32/pruebas_hardware/prueba_m3.py
"""

import gc
import time

import config

config.WATCHDOG_MS = 0  # en la prueba no se activa el watchdog (no reinicia la placa al terminar)
gc.collect()
libre_inicio = gc.mem_free()

import bucle  # noqa: E402
import hardware  # noqa: E402

hw = hardware.Hardware()
gc.collect()
print("RAM libre: %d KB al inicio, %d KB con el programa cargado y la microSD montada"
      % (libre_inicio // 1024, gc.mem_free() // 1024))
print("Reloj DS3231:", "presente" if hw.ds3231 is not None else "no conectado (hora: GPS o reloj interno)")

t = time.ticks_ms()
reg = bucle.ejecutar(hw, config, max_filas=60)
gc.collect()
print("Sesión %s: %d filas en %.1f s | RAM libre al final: %d KB"
      % (reg.nombre, reg.filas, time.ticks_diff(time.ticks_ms(), t) / 1000, gc.mem_free() // 1024))
with open(reg.ruta_csv) as f:
    lineas = f.read().splitlines()
for i in (0, 1, 2, len(lineas) // 2, len(lineas) - 1):
    print(lineas[i])
with open(reg.ruta_json) as f:
    print(f.read())

import vfs  # noqa: E402

vfs.umount(config.PUNTO_MONTAJE)
