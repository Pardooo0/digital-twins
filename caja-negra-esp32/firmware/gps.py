"""Lector del GPS por UART, sin hilos: se llama muchas veces por segundo y guarda el último estado.

`uart` es cualquier objeto con read() → bytes o None (machine.UART en el ESP32; uno falso en las pruebas).
Los tiempos (ahora_ms) son milisegundos de un reloj monotónico.
"""

import nmea

MAX_BUFER = 2048  # si llega basura sin fin de línea, no crecer sin límite


class LectorGPS:
    def __init__(self, uart):
        self.uart = uart
        self.bufer = b""
        self.frases = 0
        self.malas = 0
        # t_gga / t_rmc: instante (ms monotónicos) de la última frase válida de cada tipo
        self.estado = {"fix": 0, "lat_e7": None, "lon_e7": None, "alt_m": None, "sats": 0, "hdop": None,
                       "t_gga": None, "utc_ms": None, "t_rmc": None}

    def actualizar(self, ahora_ms):
        datos = self.uart.read()
        if not datos:
            return
        self.bufer += datos
        if len(self.bufer) > MAX_BUFER:
            self.bufer = self.bufer[-256:]
        while b"\n" in self.bufer:
            crudo, self.bufer = self.bufer.split(b"\n", 1)
            try:
                linea = crudo.decode()
            except UnicodeError:  # ruido en la línea
                self.malas += 1
                continue
            if not linea.startswith("$"):
                continue
            d = nmea.parsear(linea)
            if d is None:
                self.malas += 1 if linea[3:6] in ("GGA", "RMC") else 0
                continue
            self.frases += 1
            e = self.estado
            if d["tipo"] == "GGA":
                for k in ("fix", "lat_e7", "lon_e7", "alt_m", "sats", "hdop"):
                    e[k] = d[k]
                e["t_gga"] = ahora_ms
            elif d["valido"] and d["utc_ms"] is not None:  # la hora del RMC solo se confía con fix
                e["utc_ms"], e["t_rmc"] = d["utc_ms"], ahora_ms
