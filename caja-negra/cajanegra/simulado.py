"""Fuentes falsas de GPS y DHT22 para probar en Windows sin la Pi."""

import math
import random
import time
from datetime import datetime, timezone

from .nmea import calcular_checksum

LAT0, LON0 = 20.1426, -101.1756  # Uriangato, Gto.
RADIO_GRADOS = 0.0002  # ~22 m: simula caminar alrededor de la estructura


def lineas_gps(segundos_sin_fix=5, pausa=1.0):
    """Pares GGA + RMC por segundo; los primeros `segundos_sin_fix` sin fix, luego una vuelta circular."""
    i = 0
    while True:
        ahora = datetime.now(timezone.utc)
        hora, fecha = ahora.strftime("%H%M%S.00"), ahora.strftime("%d%m%y")
        if i < segundos_sin_fix:
            gga = f"GPGGA,{hora},,,,,0,00,99.99,,,,,,"
            rmc = f"GPRMC,{hora},V,,,,,,,{fecha},,,N"
        else:
            angulo = 2 * math.pi * (i - segundos_sin_fix) / 120
            lat = _coord(LAT0 + RADIO_GRADOS * math.sin(angulo), "NS", 2)
            lon = _coord(LON0 + RADIO_GRADOS * math.cos(angulo), "EW", 3)
            gga = f"GPGGA,{hora},{lat},{lon},1,07,1.20,1915.3,M,-9.1,M,,"
            rmc = f"GPRMC,{hora},A,{lat},{lon},0.80,,{fecha},,,A"
        yield f"${gga}*{calcular_checksum(gga):02X}"
        yield f"${rmc}*{calcular_checksum(rmc):02X}"
        i += 1
        time.sleep(pausa)


def leer_dht():
    """Como dht.leer_iio, pero inventado; falla ~10 % de las veces, igual que el sensor real."""
    if random.random() < 0.1:
        raise OSError("lectura simulada fallida")
    return 22.0 + random.uniform(-0.5, 0.5), 60.0 + random.uniform(-2, 2)


def _coord(grados, hemisferios, digitos_grados):
    """Grados decimales → 'ddmm.mmmm,N' (o 'dddmm.mmmm,W')."""
    h = hemisferios[0] if grados >= 0 else hemisferios[1]
    grados = abs(grados)
    g = int(grados)
    return f"{g:0{digitos_grados}d}{(grados - g) * 60:07.4f},{h}"
