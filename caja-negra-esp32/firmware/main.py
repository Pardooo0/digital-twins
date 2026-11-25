"""Arranque de la caja negra (MicroPython, ESP32-C3): corre solo al conectar la energía.

Modo mantenimiento (no graba y deja libre la consola para cargar programas desde la PC):
  - si existe el archivo /mantenimiento en la flash del ESP32, o
  - si se presiona BOOT mientras el LED parpadea muy rápido durante los primeros 2 s.

Si algo falla (p. ej. la microSD), se anota en errores.txt y la placa se reinicia en 5 s: equivale al
Restart=always de systemd en la Raspberry. Al cerrar la sesión con el botón, la placa se duerme hasta que
se reinicie o se desconecte.
"""

import os
import sys
import time

import machine
from machine import Pin


def modo_mantenimiento():
    try:
        os.stat("/mantenimiento")
        return True
    except OSError:
        pass
    led, boton = Pin(8, Pin.OUT), Pin(9, Pin.IN, Pin.PULL_UP)
    t0 = time.ticks_ms()
    while time.ticks_diff(time.ticks_ms(), t0) < 2000:
        led.value(not led.value())
        time.sleep_ms(50)
        if boton.value() == 0:
            led.value(0)  # encendido fijo: modo mantenimiento
            return True
    led.value(1)
    return False


def anotar_error(e):
    for ruta in ("/sd/errores.txt", "/errores.txt"):
        try:
            with open(ruta, "a") as f:
                f.write("--- %d ms desde el arranque\n" % time.ticks_ms())
                sys.print_exception(e, f)
            return
        except OSError:
            pass


if modo_mantenimiento():
    print("Caja negra en MODO MANTENIMIENTO: no graba. Para volver a grabar: borra /mantenimiento y reinicia.")
else:
    try:
        import bucle
        import hardware

        bucle.ejecutar(hardware.Hardware())
        print("Sesión cerrada con el botón. Desconecta la caja o presiona RST para grabar otra.")
        machine.deepsleep()  # detiene todo (y el watchdog) hasta reiniciar
    except KeyboardInterrupt:
        print("Detenida desde la PC (Ctrl-C); el watchdog reiniciará la placa en ~30 s.")
    except Exception as e:  # noqa: BLE001 — cualquier falla: anotar y reiniciar
        sys.print_exception(e)
        anotar_error(e)
        time.sleep(5)
        machine.reset()
