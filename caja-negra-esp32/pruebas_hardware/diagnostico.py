"""Etapa M2 — diagnóstico rápido de los cuatro módulos conectados al ESP32-C3.

Revisa, sin escribir nada en la microSD: reloj DS3231 (I²C), DHT22, GPS (UART) y la microSD (SPI, con varias
velocidades y el nivel de sus líneas). Sirve para saber qué módulo responde y cuál tiene problema de conexión.

Uso:  mpremote connect COM9 run caja-negra-esp32/pruebas_hardware/diagnostico.py
"""

import time

from machine import I2C, SPI, UART, Pin

print("== 1. Reloj DS3231 (I2C: SDA=GPIO1, SCL=GPIO0)")
try:
    i2c = I2C(0, sda=Pin(1), scl=Pin(0), freq=100_000)
    dispositivos = i2c.scan()
    print("   Dispositivos I2C:", [hex(d) for d in dispositivos] or "ninguno")
    print("   DS3231 (0x68):", "SÍ" if 0x68 in dispositivos else "NO", "| EEPROM (0x57):", "SÍ" if 0x57 in dispositivos else "NO")
except Exception as e:
    print("   ERROR:", e)

print("== 2. DHT22 (GPIO3)")
try:
    import dht
    sensor = dht.DHT22(Pin(3))
    for intento in range(3):
        try:
            sensor.measure()
            print("   Temperatura %.1f °C, humedad %.1f %%" % (sensor.temperature(), sensor.humidity()))
            break
        except OSError as e:
            print("   intento %d: sin respuesta (%s)" % (intento + 1, e))
            time.sleep(2.5)
except Exception as e:
    print("   ERROR:", e)

print("== 3. GPS (UART1 RX=GPIO20, 9600 baudios), 3 s")
try:
    uart = UART(1, baudrate=9600, rx=20, tx=21, timeout=100)
    t0, datos = time.ticks_ms(), b""
    while time.ticks_diff(time.ticks_ms(), t0) < 3000:
        n = uart.read()
        if n:
            datos += n
    lineas = [l for l in datos.split(b"\n") if l.startswith(b"$")]
    print("   Bytes recibidos:", len(datos), "| líneas NMEA:", len(lineas))
    for l in lineas[:3]:
        print("  ", l.strip()[:80].decode("ascii", "replace"))
except Exception as e:
    print("   ERROR:", e)

print("== 4. microSD (SPI: SCK=4, MISO=5, MOSI=6, CS=7)")
miso = Pin(5, Pin.IN)
print("   Nivel de MISO en reposo:", miso.value(), "(1 = hay algo conectado que lo sube; 0 = flotando o a tierra)")
miso_pu = Pin(5, Pin.IN, Pin.PULL_DOWN)
print("   MISO con pull-down interno:", miso_pu.value(), "(si sigue en 1, el adaptador sí está alimentado y conectado)")
try:
    import sdcard
    for vel in (100_000, 400_000, 1_000_000):
        try:
            spi = SPI(1, baudrate=vel, sck=Pin(4), mosi=Pin(6), miso=Pin(5))
            tarjeta = sdcard.SDCard(spi, Pin(7, Pin.OUT), baudrate=vel)
            print("   SPI a %d Hz: tarjeta OK, %d sectores (%.2f GB)" % (vel, tarjeta.sectors, tarjeta.sectors * 512 / 1e9))
            break
        except OSError as e:
            print("   SPI a %d Hz: %s" % (vel, e))
except Exception as e:
    print("   ERROR:", e)
print("== Fin del diagnóstico")
