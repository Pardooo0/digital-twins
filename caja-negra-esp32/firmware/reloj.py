"""Hora UTC de cada fila: GPS si está fresco; si no, el reloj DS3231 (rtc) o el reloj interno (sistema).

- Con hora GPS válida (RMC con fix de hace ≤ 3 s): fuente «gps». Además se usa para (re)sincronizar la base
  interna y para ajustar el DS3231 en el primer fix y después cada `sinc_rtc_ms`.
- Sin GPS y con DS3231: fuente «rtc». Es confiable salvo que el DS3231 haya perdido la hora (bandera OSF) y
  todavía no se haya ajustado con el GPS → HORA_NO_SINC.
- Sin GPS ni DS3231: fuente «sistema», confiable solo si en esta sesión ya hubo hora GPS.

Entre lecturas del DS3231 (resolución de 1 s) la hora avanza con el reloj monotónico del ESP32; el DS3231
se vuelve a leer cada `releer_rtc_ms` para corregir la deriva del cristal del ESP32.
"""

import tiempo

SIN_HORA = tiempo.a_epoch_ms(2000, 1, 1)  # si nunca hubo hora: 2000-01-01 + tiempo encendido (HORA_NO_SINC)


class Reloj:
    def __init__(self, ds3231=None, ahora_ms=0, sinc_rtc_ms=3600000, releer_rtc_ms=600000):
        self.ds = ds3231
        self.sinc_rtc_ms, self.releer_rtc_ms = sinc_rtc_ms, releer_rtc_ms
        self.base_utc = self.base_ms = None   # utc_ms conocido en el instante base_ms (monotónico)
        self.confiable = False
        self.ultima_sinc_rtc = None           # cuándo se ajustó el DS3231 con el GPS
        self.ultima_lectura_rtc = None
        self.rtc_perdio_hora = None           # estado del DS3231 al arrancar (para los metadatos)
        self.errores_rtc = 0
        if self.ds is not None:
            self._leer_rtc(ahora_ms)
            self.rtc_perdio_hora = not self.confiable if self.base_utc is not None else None

    @property
    def fuente_sin_gps(self):
        return "rtc" if self.ds is not None else "sistema"

    def _leer_rtc(self, ahora_ms):
        self.ultima_lectura_rtc = ahora_ms
        try:
            a, m, d, h, mi, s = self.ds.leer()
            perdio = self.ds.perdio_hora()
        except (OSError, ValueError):
            self.errores_rtc += 1
            return
        if perdio and self.ultima_sinc_rtc is not None:
            return  # se ajustó en esta sesión y luego falló: mejor seguir con la base del GPS
        self.base_utc, self.base_ms = tiempo.a_epoch_ms(a, m, d, h, mi, s), ahora_ms
        self.confiable = not perdio

    def _ajustar_rtc(self, utc_ms, ahora_ms):
        a, m, d, h, mi, s, ms = tiempo.desde_epoch_ms(utc_ms + 500)  # al segundo más cercano
        try:
            self.ds.ajustar(a, m, d, h, mi, s)
            self.ultima_sinc_rtc = ahora_ms
        except (OSError, ValueError):
            self.errores_rtc += 1

    def hora(self, ahora_ms, gps, gps_max_edad_ms=3000):
        """(utc_ms, fuente, confiable) para el instante ahora_ms."""
        if gps["utc_ms"] is not None and ahora_ms - gps["t_rmc"] <= gps_max_edad_ms:
            utc = gps["utc_ms"] + (ahora_ms - gps["t_rmc"])
            self.base_utc, self.base_ms, self.confiable = utc, ahora_ms, True
            if self.ds is not None and (self.ultima_sinc_rtc is None or ahora_ms - self.ultima_sinc_rtc >= self.sinc_rtc_ms):
                self._ajustar_rtc(utc, ahora_ms)
                self.ultima_lectura_rtc = ahora_ms
            return utc, "gps", True
        if self.ds is not None and (self.ultima_lectura_rtc is None or ahora_ms - self.ultima_lectura_rtc >= self.releer_rtc_ms):
            self._leer_rtc(ahora_ms)
        if self.base_utc is None:
            return SIN_HORA + ahora_ms, self.fuente_sin_gps, False
        return self.base_utc + (ahora_ms - self.base_ms), self.fuente_sin_gps, self.confiable
