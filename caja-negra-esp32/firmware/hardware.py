"""Hardware real del ESP32-C3 para bucle.ejecutar (solo MicroPython). Pines en config.py."""

import gc
import time

import dht
import machine
from machine import I2C, SPI, UART, Pin

import config
import ds3231


class Monotonico:
    """Milisegundos desde el arranque sin desbordarse (time.ticks_ms da la vuelta cada ~12 días)."""

    def __init__(self):
        self.ultimo, self.total = time.ticks_ms(), 0

    def ms(self):
        t = time.ticks_ms()
        self.total += time.ticks_diff(t, self.ultimo)
        self.ultimo = t
        return self.total


def montar_sd(p, led, intentos=15):
    """Monta la microSD en config.PUNTO_MONTAJE; reintenta ~15 s (LED en parpadeo rápido)."""
    import sdcard
    import vfs

    for _ in range(intentos):
        try:
            spi = SPI(1, baudrate=1_000_000, sck=Pin(p["sd_sck"]), mosi=Pin(p["sd_mosi"]), miso=Pin(p["sd_miso"]))
            tarjeta = sdcard.SDCard(spi, Pin(p["sd_cs"], Pin.OUT), baudrate=config.SD_BAUDIOS)
            vfs.mount(vfs.VfsFat(tarjeta), config.PUNTO_MONTAJE)
            return
        except OSError:
            for _ in range(5):
                led.value(0)
                time.sleep_ms(100)
                led.value(1)
                time.sleep_ms(100)
    raise OSError("microSD no disponible: revisa la tarjeta y sus cables")


class Hardware:
    simulado = False

    def __init__(self):
        p = config.PINES
        self._mono = Monotonico()
        self.ms = self._mono.ms
        self.led_pin = Pin(p["led"], Pin.OUT, value=1)
        self.boton = Pin(p["boton"], Pin.IN, Pin.PULL_UP)
        montar_sd(p, self.led_pin)
        self.carpeta_datos = config.CARPETA_DATOS
        self.uart = UART(1, baudrate=config.GPS_BAUDIOS, rx=p["gps_rx"], tx=p["gps_tx"], rxbuf=2048, timeout=0)

        sensor = dht.DHT22(Pin(p["dht"]))

        def medir_dht():
            sensor.measure()
            return sensor.temperature(), sensor.humidity()

        self.medir_dht = medir_dht
        self.ds3231 = None
        try:
            rtc = ds3231.DS3231(I2C(0, sda=Pin(p["i2c_sda"]), scl=Pin(p["i2c_scl"]), freq=100_000))
            if rtc.presente():
                self.ds3231 = rtc
        except OSError:
            pass  # sin reloj: la hora sale del GPS y, sin GPS, del reloj interno (HORA_NO_SINC)
        self.wdt = machine.WDT(timeout=config.WATCHDOG_MS) if config.WATCHDOG_MS else None

    def alimentar_watchdog(self):
        if self.wdt is not None:
            self.wdt.feed()

    def dormir(self, ms):
        time.sleep_ms(ms)

    def recolectar(self):
        gc.collect()
