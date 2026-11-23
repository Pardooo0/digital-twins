"""Hilo que lee NMEA continuamente y guarda el último estado del GPS."""

import logging
import threading
import time

from . import nmea

log = logging.getLogger(__name__)


class LectorGPS(threading.Thread):
    """`fuente` es un iterable (normalmente infinito) de líneas NMEA en texto."""

    def __init__(self, fuente):
        super().__init__(daemon=True, name="gps")
        self._fuente = fuente
        self._lock = threading.Lock()
        # t_gga / t_rmc: reloj monotónico de la última frase válida de cada tipo
        self._estado = {"fix": 0, "lat": None, "lon": None, "alt_m": None, "sats": 0, "hdop": None,
                        "t_gga": None, "utc": None, "t_rmc": None}

    def run(self):
        for linea in self._fuente:
            d = nmea.parsear(linea)
            if d is None:
                continue
            ahora = time.monotonic()
            with self._lock:
                if d["tipo"] == "GGA":
                    self._estado.update({k: d[k] for k in ("fix", "lat", "lon", "alt_m", "sats", "hdop")},
                                        t_gga=ahora)
                elif d["valido"] and d["utc"]:  # RMC: la hora solo se confía con fix
                    self._estado.update(utc=d["utc"], t_rmc=ahora)

    def estado(self):
        with self._lock:
            return dict(self._estado)


def lineas_serial(puerto, baudios):
    """Líneas del puerto serie; si el puerto falla, reintenta cada 2 s sin terminar."""
    import serial  # importado aquí para que --simular funcione sin pyserial

    while True:
        try:
            with serial.Serial(puerto, baudios, timeout=2) as s:
                log.info("GPS abierto en %s a %d baudios", puerto, baudios)
                while True:
                    crudo = s.readline()
                    if crudo:
                        yield crudo.decode("ascii", errors="replace")
        except serial.SerialException as e:
            log.warning("Error en el puerto del GPS: %s; reintentando", e)
            time.sleep(2)
