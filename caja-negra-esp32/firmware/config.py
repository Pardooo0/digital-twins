"""Configuración de la caja negra con ESP32-C3 Super Mini (pines y tiempos). Ver docs/pines_esp32c3.svg."""

VERSION = "esp32-0.1.0"
DISPOSITIVO = "ESP32-C3 Super Mini + DS3231 + microSD"
PRIMERA_SESION = 1001          # la Raspberry llegó a sesion_0028: así no se repiten nombres en el gemelo

PUNTO_MONTAJE = "/sd"
CARPETA_DATOS = "/sd/datos"
SD_BAUDIOS = 4_000_000         # SPI de la microSD tras el arranque (el controlador inicia a 100 kHz)

PERIODO_REGISTRO_MS = 1000     # una fila por segundo
PERIODO_DHT_MS = 3000          # el DHT22 necesita ≥ 2 s entre lecturas
DHT_MAX_EDAD_MS = 10000        # lectura más vieja que esto → DHT_VIEJO
GPS_MAX_EDAD_MS = 3000         # sin frases del GPS por más de esto = datos viejos, no se repiten
GPS_BAUDIOS = 9600
SINC_RTC_CADA_S = 3600         # ajustar el DS3231 con el GPS en el primer fix y luego cada hora
RELEER_RTC_CADA_S = 600        # releer el DS3231 para corregir la deriva del reloj del ESP32
PAUSA_MS = 20                  # pausa del bucle: el GPS se lee ~50 veces por segundo
BOTON_CERRAR_MS = 1000         # BOOT presionado 1 s → cerrar la sesión y detener
WATCHDOG_MS = 30000            # si el programa se traba 30 s, la placa se reinicia (nueva sesión)

PINES = {
    "gps_rx": 20, "gps_tx": 21,                      # UART1: TX del GPS (pin 2 del shield) → GPIO20
    "sd_sck": 4, "sd_miso": 5, "sd_mosi": 6, "sd_cs": 7,
    "i2c_sda": 1, "i2c_scl": 0,                      # DS3231
    "dht": 3,
    "led": 8,                                        # LED azul de la placa (activo en bajo)
    "boton": 9,                                      # botón BOOT de la placa
}


def como_dict():
    """Configuración para los metadatos de cada sesión."""
    return {k: v for k, v in globals().items() if k.isupper()}
