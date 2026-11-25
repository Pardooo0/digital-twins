"""Parser NMEA 0183 mínimo (GGA y RMC) con checksum, para MicroPython y CPython.

Adaptado del parser de la caja negra con Raspberry Pi. Diferencias por el ESP32-C3:
- MicroPython usa flotantes de precisión simple (la longitud −101.1875398 se vuelve −101.1875400): las
  coordenadas se convierten con enteros, en diezmillonésimas de grado (lat_e7, lon_e7), sin perder decimales.
- No hay datetime: la hora del RMC se entrega como milisegundos desde 1970 (utc_ms).
- La altitud y el HDOP se conservan como el texto del GPS (ya vienen con sus decimales).
"""

import tiempo


def calcular_checksum(cuerpo):
    """XOR de los caracteres entre `$` y `*`."""
    x = 0
    for c in cuerpo:
        x ^= ord(c)
    return x


def checksum_valido(linea):
    """True si la línea es `$CUERPO*HH` y HH es el checksum de CUERPO."""
    linea = linea.strip()
    if not linea.startswith("$") or len(linea) < 4 or linea[-3] != "*":
        return False
    try:
        return calcular_checksum(linea[1:-3]) == int(linea[-2:], 16)
    except ValueError:
        return False


def parsear(linea):
    """dict con los datos de una frase GGA o RMC, o None si es inválida o de otro tipo."""
    if not checksum_valido(linea):
        return None
    campos = linea.strip()[1:-3].split(",")
    tipo = campos[0][2:]  # quita el emisor (GP, GN, GL…)
    try:
        if tipo == "GGA" and len(campos) >= 10:
            return _gga(campos)
        if tipo == "RMC" and len(campos) >= 10:
            return _rmc(campos)
    except (ValueError, IndexError):
        return None
    return None


def _gga(c):
    return {
        "tipo": "GGA",
        "hora": _hora(c[1]),
        "lat_e7": _coord_e7(c[2], c[3]),
        "lon_e7": _coord_e7(c[4], c[5]),
        "fix": int(c[6] or 0),
        "sats": int(c[7] or 0),
        "hdop": _real_txt(c[8]),
        "alt_m": _real_txt(c[9]),
    }


def _rmc(c):
    hora, fecha = _hora(c[1]), c[9]
    utc_ms = None
    if hora is not None and len(fecha) == 6:
        utc_ms = tiempo.a_epoch_ms(2000 + int(fecha[4:6]), int(fecha[2:4]), int(fecha[0:2]), *hora)
    return {"tipo": "RMC", "valido": c[2] == "A", "utc_ms": utc_ms,
            "lat_e7": _coord_e7(c[3], c[4]), "lon_e7": _coord_e7(c[5], c[6])}


def _hora(texto):
    """'hhmmss.ss' → (hora, minuto, segundo, milisegundo), o None si viene vacío."""
    if not texto:
        return None
    entero, _, frac = texto.partition(".")
    ms = int((frac + "000")[:3]) if frac else 0
    return int(entero[0:2]), int(entero[2:4]), int(entero[4:6]), ms


def _coord_e7(valor, hemisferio):
    """'ddmm.mmmm' / 'dddmm.mmmm' + N/S/E/W → grados × 10⁷ como entero (S y W negativos), sin flotantes."""
    if not valor or not hemisferio:
        return None
    entero, _, frac = valor.partition(".")
    grados = int(entero[:-2])
    frac = (frac + "000000")[:6]  # minutos con 6 decimales como entero: mm.mmmmmm → mmmmmmmm
    minutos_e6 = int(entero[-2:]) * 1000000 + int(frac)
    e7 = grados * 10000000 + (minutos_e6 + 3) // 6  # min×10⁶ / 60 × 10 = min×10⁶ / 6 → grados × 10⁷, redondeado
    return -e7 if hemisferio in "SW" else e7


def _real_txt(texto):
    """Texto de un número real tal como viene del GPS, o None si está vacío o no es número."""
    if not texto:
        return None
    float(texto)  # valida (lanza ValueError si no es número)
    return texto
