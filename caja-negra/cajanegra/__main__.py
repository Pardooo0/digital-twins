"""Punto de entrada: python -m cajanegra [--simular] [--segundos N]."""

import argparse
import functools
import logging
import signal
import threading
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from . import __version__, config, dht, gps
from .led import Led, elegir_estado
from .registro import Registro

log = logging.getLogger("cajanegra")

GPS_MAX_EDAD_S = 3.0  # sin frases del GPS por más de esto = datos viejos, no se repiten
# systemd-timesyncd crea este archivo cuando el reloj del sistema queda sincronizado por NTP.
# La Pi no tiene RTC: al arrancar retoma la última hora guardada (fake-hwclock), que puede ser de días atrás.
RUTA_RELOJ_SINC = Path("/run/systemd/timesync/synchronized")
LENTO_S = 1.0  # grabar una fila o despertar más tarde que esto se registra como advertencia (huecos)


def reloj_sincronizado():
    return RUTA_RELOJ_SINC.exists()


def iso(dt):
    """ISO 8601 UTC con milisegundos y sufijo Z."""
    return dt.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def armar_fila(estado_gps, estado_dht, ahora, ahora_sistema, t0, seq, cfg, version, reloj_sinc=True):
    """Arma una fila del contrato de datos. Devuelve (fila, con_fix, falla_sensor).

    `reloj_sinc`: si el reloj del sistema está sincronizado (NTP); solo importa cuando no hay hora GPS.
    """
    g, d = estado_gps, estado_dht
    banderas = []

    gps_fresco = g["t_gga"] is not None and ahora - g["t_gga"] <= GPS_MAX_EDAD_S
    con_fix = gps_fresco and g["fix"] > 0 and g["lat"] is not None
    if not con_fix:
        banderas.append("SIN_FIX")

    temp = hr = edad_dht = None
    if d["t_valida"] is None:
        banderas.append("DHT_ERROR")
    else:
        temp, hr, edad_dht = d["temp_c"], d["hr_pct"], round(ahora - d["t_valida"], 1)
        if edad_dht > cfg["dht_max_edad_s"]:
            banderas.append("DHT_VIEJO")

    if g["utc"] is not None and ahora - g["t_rmc"] <= GPS_MAX_EDAD_S:
        # shortcut: no corrige la latencia serie (~0.1–0.5 s a 9600 baudios); basta para registros a 1 Hz
        utc, fuente_hora = g["utc"] + timedelta(seconds=ahora - g["t_rmc"]), "gps"
    else:
        utc, fuente_hora = ahora_sistema, "sistema"
        banderas.append("HORA_SISTEMA")
        if not reloj_sinc:
            banderas.append("HORA_NO_SINC")  # utc puede estar muy mal: corregir después con t_mono_s

    # Rojo si un sensor lleva demasiado sin responder; t0 da margen al arrancar.
    ultimo_gps = t0 if g["t_gga"] is None else g["t_gga"]
    ultimo_dht = t0 if d["t_valida"] is None else d["t_valida"]
    falla = ahora - ultimo_gps > GPS_MAX_EDAD_S or ahora - ultimo_dht > cfg["dht_max_edad_s"]

    fila = {
        "seq": seq,
        "t_mono_s": round(ahora - t0, 3),
        "utc": iso(utc),
        "fuente_hora": fuente_hora,
        "lat": round(g["lat"], 7) if con_fix else None,
        "lon": round(g["lon"], 7) if con_fix else None,
        "alt_m": g["alt_m"] if con_fix else None,
        "fix": g["fix"] if gps_fresco else 0,
        "sats": g["sats"] if gps_fresco else None,
        "hdop": g["hdop"] if gps_fresco else None,
        "temp_c": temp,
        "hr_pct": hr,
        "dht_edad_s": edad_dht,
        "espesor_mm": None,
        "banderas": ";".join(banderas),
        "version": version,
    }
    return fila, con_fix, falla


def main(argv=None):
    p = argparse.ArgumentParser(prog="cajanegra", description="Caja negra RPAS: GPS + DHT22 a CSV.")
    p.add_argument("--simular", action="store_true", help="GPS y DHT22 falsos, sin GPIO (para Windows)")
    p.add_argument("--config", default=str(Path(__file__).resolve().parent.parent / "config.yaml"))
    p.add_argument("--segundos", type=float, help="detenerse después de N segundos (pruebas)")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

    cfg = config.cargar(args.config)
    if args.simular:
        from . import simulado
        fuente_gps, leer_dht, pines = simulado.lineas_gps(), simulado.leer_dht, None
    else:
        fuente_gps = gps.lineas_serial(cfg["puerto_gps"], cfg["baudios_gps"])
        leer_dht = functools.partial(dht.leer_iio, cfg["ruta_iio_dht"])
        pines = cfg["led"]

    led = Led(pines)
    led.poner("arrancando")
    parar = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: parar.set())  # systemd stop / botón de apagado

    lector_gps = gps.LectorGPS(fuente_gps)
    lector_dht = dht.LectorDHT(leer_dht, cfg["periodo_dht_s"])
    lector_gps.start()
    lector_dht.start()

    registro = Registro(cfg["carpeta_datos"], {
        "version": __version__, "simulado": args.simular, "config": cfg,
        "inicio_sistema_utc": iso(datetime.now(timezone.utc)),
        "reloj_sinc_al_inicio": args.simular or reloj_sincronizado(),
    })
    log.info("Grabando %s en %s", registro.nombre, registro.ruta_csv)

    t0 = siguiente = time.monotonic()
    seq, hubo_fix = 0, False
    try:
        while not parar.is_set():
            ahora = time.monotonic()
            if args.segundos is not None and ahora - t0 >= args.segundos:
                break
            if ahora - siguiente > LENTO_S:  # el proceso despertó tarde (CPU ocupada, no la microSD)
                log.warning("Fila %d: el ciclo despertó %.1f s tarde", seq + 1, ahora - siguiente)
            # En Windows (--simular) no existe el archivo de timesyncd: se da por buena la hora del sistema.
            sinc = args.simular or reloj_sincronizado()
            fila, con_fix, falla = armar_fila(lector_gps.estado(), lector_dht.estado(), ahora,
                                              datetime.now(timezone.utc), t0, seq + 1, cfg, __version__,
                                              reloj_sinc=sinc)
            try:
                antes = time.monotonic()
                registro.escribir(fila)  # incluye flush + fsync
                tardo = time.monotonic() - antes
                if tardo > LENTO_S:
                    log.warning("Fila %d: grabar en la microSD (fsync) tardó %.1f s", seq + 1, tardo)
                seq += 1  # solo cuenta filas grabadas: el consecutivo no salta
                if con_fix and not hubo_fix:
                    hubo_fix = True
                    registro.actualizar_metadatos(primer_fix_utc=fila["utc"])
            except OSError as e:
                log.error("No se pudo escribir en la microSD: %s", e)
                falla = True
            led.poner(elegir_estado(con_fix, hubo_fix, falla))

            siguiente += cfg["periodo_registro_s"]
            siguiente = max(siguiente, time.monotonic())  # si se atrasó, no grabar en ráfaga
            parar.wait(siguiente - time.monotonic())
    except KeyboardInterrupt:
        pass
    finally:
        try:
            registro.cerrar(hora_cierre=iso(datetime.now(timezone.utc)), filas=seq)
        except OSError as e:
            log.error("No se pudieron cerrar los metadatos: %s", e)
        led.poner("apagado")
        log.info("Detenido: %d filas en %s", seq, registro.ruta_csv)


if __name__ == "__main__":
    main()
