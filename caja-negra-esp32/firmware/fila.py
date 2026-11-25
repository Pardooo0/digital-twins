"""Armado de cada fila del CSV según el contrato de datos (CLAUDE.md, sección 7). Sin hardware.

Misma lógica que la caja negra con Raspberry Pi; la hora ya viene resuelta por reloj.py como
(utc_ms, fuente, confiable) con fuente ∈ {gps, rtc, sistema}.
"""

import tiempo

COLUMNAS = ["sesion", "seq", "t_mono_s", "utc", "fuente_hora", "lat", "lon", "alt_m",
            "fix", "sats", "hdop", "temp_c", "hr_pct", "dht_edad_s", "espesor_mm",
            "banderas", "version"]


def grados_txt(e7):
    """Entero en 10⁻⁷ grados → texto con 7 decimales (sin pasar por flotantes)."""
    signo = "-" if e7 < 0 else ""
    e, f = divmod(abs(e7), 10000000)
    return "%s%d.%07d" % (signo, e, f)


def segundos_txt(ms, decimales=3):
    """Milisegundos → segundos con 3 decimales (o 1, redondeado)."""
    if decimales == 1:
        d = (ms + 50) // 100
        return "%d.%d" % (d // 10, d % 10)
    return "%d.%03d" % (ms // 1000, ms % 1000)


def armar_fila(gps, dht, hora, ahora_ms, t0_ms, seq, sesion, version, gps_max_edad_ms=3000, dht_max_edad_ms=10000):
    """Devuelve (fila, con_fix, falla); fila es un dict columna → texto.

    gps: estado de gps.LectorGPS; dht: estado de dht_lector.LectorDHT; hora: (utc_ms, fuente, confiable).
    falla = algún sensor lleva demasiado tiempo sin responder (t0_ms da margen al arrancar).
    """
    banderas = []
    gps_fresco = gps["t_gga"] is not None and ahora_ms - gps["t_gga"] <= gps_max_edad_ms
    con_fix = gps_fresco and gps["fix"] > 0 and gps["lat_e7"] is not None and gps["lon_e7"] is not None
    if not con_fix:
        banderas.append("SIN_FIX")

    temp = hr = edad = ""
    if dht["t_valida"] is None:
        banderas.append("DHT_ERROR")
    else:
        edad_ms = ahora_ms - dht["t_valida"]
        temp, hr, edad = "%.1f" % dht["temp_c"], "%.1f" % dht["hr_pct"], segundos_txt(edad_ms, 1)
        if edad_ms > dht_max_edad_ms:
            banderas.append("DHT_VIEJO")

    utc_ms, fuente, confiable = hora
    if fuente == "sistema":
        banderas.append("HORA_SISTEMA")
    if fuente != "gps" and not confiable:
        banderas.append("HORA_NO_SINC")  # hora dudosa: el gemelo la corrige con t_mono_s

    ultimo_gps = t0_ms if gps["t_gga"] is None else gps["t_gga"]
    ultimo_dht = t0_ms if dht["t_valida"] is None else dht["t_valida"]
    falla = ahora_ms - ultimo_gps > gps_max_edad_ms or ahora_ms - ultimo_dht > dht_max_edad_ms

    fila = {
        "sesion": sesion,
        "seq": str(seq),
        "t_mono_s": segundos_txt(ahora_ms - t0_ms),
        "utc": tiempo.iso(utc_ms),
        "fuente_hora": fuente,
        "lat": grados_txt(gps["lat_e7"]) if con_fix else "",
        "lon": grados_txt(gps["lon_e7"]) if con_fix else "",
        "alt_m": (gps["alt_m"] or "") if con_fix else "",
        "fix": str(gps["fix"]) if gps_fresco else "0",
        "sats": str(gps["sats"]) if gps_fresco else "",
        "hdop": (gps["hdop"] or "") if gps_fresco else "",
        "temp_c": temp,
        "hr_pct": hr,
        "dht_edad_s": edad,
        "espesor_mm": "",
        "banderas": ";".join(banderas),
        "version": version,
    }
    return fila, con_fix, falla


def linea_csv(fila):
    return ",".join(fila[c] for c in COLUMNAS) + "\n"


def encabezado_csv():
    return ",".join(COLUMNAS) + "\n"
