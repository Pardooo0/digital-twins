"""Fechas y horas UTC como milisegundos desde 1970-01-01 (época Unix), sin el módulo datetime.

MicroPython no trae datetime; estas funciones de enteros corren igual en el ESP32 y en la PC (pytest).
Algoritmo de días civiles de H. Hinnant (válido para el calendario gregoriano).
"""


def dias_desde_civil(a, m, d):
    """Días desde 1970-01-01 para la fecha (año, mes, día)."""
    if m <= 2:
        a -= 1
    era = a // 400
    aoe = a - era * 400
    doy = (153 * (m - 3 if m > 2 else m + 9) + 2) // 5 + d - 1
    doe = aoe * 365 + aoe // 4 - aoe // 100 + doy
    return era * 146097 + doe - 719468


def civil_desde_dias(z):
    """(año, mes, día) para z días desde 1970-01-01."""
    z += 719468
    era = z // 146097
    doe = z - era * 146097
    aoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    doy = doe - (365 * aoe + aoe // 4 - aoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + 3 if mp < 10 else mp - 9
    a = aoe + era * 400 + (1 if m <= 2 else 0)
    return a, m, d


def a_epoch_ms(a, m, d, h=0, mi=0, s=0, ms=0):
    return (((dias_desde_civil(a, m, d) * 24 + h) * 60 + mi) * 60 + s) * 1000 + ms


def desde_epoch_ms(t):
    """(año, mes, día, hora, minuto, segundo, milisegundo) para t ms desde 1970."""
    dias, resto = divmod(t, 86400000)
    a, m, d = civil_desde_dias(dias)
    h, resto = divmod(resto, 3600000)
    mi, resto = divmod(resto, 60000)
    s, ms = divmod(resto, 1000)
    return a, m, d, h, mi, s, ms


def iso(t):
    """ISO 8601 UTC con milisegundos y sufijo Z, como en el contrato de datos: 2026-11-24T20:26:47.000Z."""
    return "%04d-%02d-%02dT%02d:%02d:%02d.%03dZ" % desde_epoch_ms(t)
