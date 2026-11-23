"""Lectura del DHT22 con el driver del kernel (overlay dht11) vía /sys/bus/iio."""

import logging
import threading
import time
from pathlib import Path

log = logging.getLogger(__name__)


def leer_iio(ruta):
    """(temp_c, hr_pct). El kernel entrega milésimas; lanza OSError si la lectura falla (es normal a veces)."""
    ruta = Path(ruta)
    temp = int((ruta / "in_temp_input").read_text()) / 1000
    hr = int((ruta / "in_humidityrelative_input").read_text()) / 1000
    return temp, hr


class LectorDHT(threading.Thread):
    """Lee cada `periodo` s; conserva la última lectura válida y su hora monotónica (t_valida)."""

    def __init__(self, leer, periodo):
        super().__init__(daemon=True, name="dht")
        self._leer, self._periodo = leer, periodo
        self._lock = threading.Lock()
        self._estado = {"temp_c": None, "hr_pct": None, "t_valida": None}

    def run(self):
        while True:
            try:
                temp, hr = self._leer()
                if not (-40 <= temp <= 80 and 0 <= hr <= 100):  # fuera del rango del DHT22
                    raise ValueError(f"lectura fuera de rango: {temp} °C, {hr} %")
                with self._lock:
                    self._estado = {"temp_c": round(temp, 1), "hr_pct": round(hr, 1),
                                    "t_valida": time.monotonic()}
            except (OSError, ValueError) as e:
                log.debug("Lectura del DHT22 fallida: %s", e)
            time.sleep(self._periodo)

    def estado(self):
        with self._lock:
            return dict(self._estado)
