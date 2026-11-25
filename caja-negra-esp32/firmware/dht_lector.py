"""Lectura periódica del DHT22: conserva la última lectura válida y su instante (como en la Pi).

`medir` es una función que devuelve (temp_c, hr_pct) o lanza OSError si el sensor no responde
(en el ESP32 envuelve dht.DHT22; en las pruebas es una función falsa).
"""


class LectorDHT:
    def __init__(self, medir, periodo_ms=3000):
        self.medir = medir
        self.periodo_ms = periodo_ms
        self.proxima = None
        self.fallas = 0
        self.estado = {"temp_c": None, "hr_pct": None, "t_valida": None}

    def actualizar(self, ahora_ms):
        if self.proxima is not None and ahora_ms < self.proxima:
            return
        self.proxima = ahora_ms + self.periodo_ms  # el DHT22 necesita ≥ 2 s entre lecturas
        try:
            temp, hr = self.medir()
            if not (-40 <= temp <= 80 and 0 <= hr <= 100):  # fuera del rango del DHT22
                raise ValueError("lectura fuera de rango")
            self.estado = {"temp_c": temp, "hr_pct": hr, "t_valida": ahora_ms}
        except (OSError, ValueError):
            self.fallas += 1  # es normal que alguna lectura falle: se conserva la última válida
