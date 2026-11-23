"""Parser NMEA 0183 mínimo: solo GGA y RMC, con verificación de checksum."""

from datetime import datetime, time, timezone


def calcular_checksum(cuerpo):
    """XOR de los caracteres entre `$` y `*`."""
    resultado = 0
    for c in cuerpo:
        resultado ^= ord(c)
    return resultado


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
    """Devuelve un dict con los datos de una frase GGA o RMC, o None si es inválida o de otro tipo."""
    if not checksum_valido(linea):
        return None
    campos = linea.strip()[1:-3].split(",")
    tipo = campos[0][2:]  # quita el talker (GP, GN, GL…)
    try:
        if tipo == "GGA" and len(campos) >= 10:
            return _gga(campos)
        if tipo == "RMC" and len(campos) >= 10:
            return _rmc(campos)
    except ValueError:
        return None
    return None


def _gga(c):
    return {
        "tipo": "GGA",
        "hora": _hora(c[1]),
        "lat": _coord(c[2], c[3]),
        "lon": _coord(c[4], c[5]),
        "fix": int(c[6] or 0),
        "sats": int(c[7] or 0),
        "hdop": float(c[8]) if c[8] else None,
        "alt_m": float(c[9]) if c[9] else None,
    }


def _rmc(c):
    hora, fecha = _hora(c[1]), c[9]
    utc = None
    if hora and len(fecha) == 6:
        utc = datetime(2000 + int(fecha[4:6]), int(fecha[2:4]), int(fecha[0:2]),
                       hora.hour, hora.minute, hora.second, hora.microsecond, tzinfo=timezone.utc)
    return {"tipo": "RMC", "valido": c[2] == "A", "utc": utc,
            "lat": _coord(c[3], c[4]), "lon": _coord(c[5], c[6])}


def _hora(texto):
    """'hhmmss.ss' → time, o None si viene vacío."""
    if not texto:
        return None
    segundos = float(texto[4:])
    entero = int(segundos)
    return time(int(texto[0:2]), int(texto[2:4]), entero, round((segundos - entero) * 1e6))


def _coord(valor, hemisferio):
    """'ddmm.mmmm' / 'dddmm.mmmm' + N/S/E/W → grados decimales (S y W negativos)."""
    if not valor or not hemisferio:
        return None
    punto = valor.index(".") if "." in valor else len(valor)
    grados = int(valor[:punto - 2]) + float(valor[punto - 2:]) / 60
    return -grados if hemisferio in "SW" else grados
