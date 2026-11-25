"""Verifica los CSV de la caja negra contra el contrato de datos (CLAUDE.md, sección 7).

Uso (en la Pi o en Windows; solo biblioteca estándar):
    python tests/verificar_sesion.py                 # todas las sesiones de ./datos
    python tests/verificar_sesion.py datos/sesion_0003.csv otra_carpeta/

Errores: encabezado distinto, consecutivo que salta, filas corruptas o fuera de rango.
Avisos (no cuentan como error): última fila cortada por un corte de energía, sesión sin
cerrar en el JSON y huecos de tiempo entre filas. Sale con código 1 si hay algún error.
"""

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from cajanegra.registro import COLUMNAS  # noqa: E402  (el contrato vive en un solo lugar)

BANDERAS = {"SIN_FIX", "DHT_ERROR", "DHT_VIEJO", "HORA_SISTEMA", "HORA_NO_SINC"}
HUECO_S = 1.5  # entre filas consecutivas a 1 Hz; más que esto se reporta como aviso
SALTO_RELOJ_S = 2.0  # si utc avanza distinto que t_mono_s por más de esto, el reloj se ajustó


def verificar_csv(ruta):
    """Devuelve (errores, avisos, filas_validas) de un CSV de sesión."""
    ruta = Path(ruta)
    errores, avisos = [], []
    texto = ruta.read_bytes().decode("utf-8", errors="replace")
    lineas = texto.splitlines()
    if not lineas:
        return ["archivo vacío (sin encabezado)"], avisos, 0
    if next(csv.reader([lineas[0]])) != COLUMNAS:
        return [f"encabezado distinto al contrato: {lineas[0]}"], avisos, 0

    cortada = not texto.endswith("\n")  # un corte de energía puede dejar la última fila a medias
    filas = list(csv.reader(lineas[1:]))
    seq_ant = t_ant = utc_ant = None
    validas = 0
    for i, campos in enumerate(filas):
        num = i + 2  # número de línea en el archivo
        ultima = i == len(filas) - 1
        problemas = _revisar_fila(campos, ruta.stem)
        if problemas:
            if ultima and cortada:
                avisos.append(f"línea {num}: última fila incompleta (corte de energía): {'; '.join(problemas)}")
            else:
                errores.extend(f"línea {num}: {p}" for p in problemas)
            continue
        fila = dict(zip(COLUMNAS, campos))
        seq, t = int(fila["seq"]), float(fila["t_mono_s"])
        utc = datetime.fromisoformat(fila["utc"][:-1])
        esperado = 1 if seq_ant is None else seq_ant + 1
        if seq != esperado:
            errores.append(f"línea {num}: seq {seq}, se esperaba {esperado}")
        if t_ant is not None:
            if t < t_ant:
                errores.append(f"línea {num}: t_mono_s retrocede ({t_ant} → {t})")
            elif t - t_ant > HUECO_S:
                avisos.append(f"línea {num}: hueco de {t - t_ant:.1f} s entre filas")
            salto = (utc - utc_ant).total_seconds() - (t - t_ant)
            if abs(salto) > SALTO_RELOJ_S:
                avisos.append(f"línea {num}: salto de reloj de {salto:+.0f} s ({fila['fuente_hora']}); "
                              "las filas anteriores pueden tener mal utc")
        seq_ant, t_ant, utc_ant = seq, t, utc
        validas += 1

    errores_json, avisos_json = _revisar_metadatos(ruta, validas)
    return errores + errores_json, avisos + avisos_json, validas


def _revisar_fila(c, sesion):
    """Lista de problemas de una fila (vacía si cumple el contrato)."""
    if len(c) != len(COLUMNAS):
        return [f"{len(c)} campos, se esperaban {len(COLUMNAS)}"]
    f = dict(zip(COLUMNAS, c))
    p = []
    if f["sesion"] != sesion:
        p.append(f"sesion '{f['sesion']}' no coincide con el archivo")
    if not _es_entero(f["seq"], minimo=1):
        p.append(f"seq inválido: '{f['seq']}'")
    if not _es_real(f["t_mono_s"], 0, math.inf):
        p.append(f"t_mono_s inválido: '{f['t_mono_s']}'")
    if not _es_utc(f["utc"]):
        p.append(f"utc inválido: '{f['utc']}'")
    if f["fuente_hora"] not in ("gps", "rtc", "sistema"):  # rtc: caja negra con ESP32 + DS3231
        p.append(f"fuente_hora inválida: '{f['fuente_hora']}'")
    banderas = set(f["banderas"].split(";")) - {""}
    if banderas - BANDERAS:
        p.append(f"banderas desconocidas: {sorted(banderas - BANDERAS)}")
    if ("HORA_SISTEMA" in banderas) != (f["fuente_hora"] == "sistema"):
        p.append("HORA_SISTEMA no concuerda con fuente_hora")
    if "HORA_NO_SINC" in banderas and f["fuente_hora"] == "gps":
        p.append("HORA_NO_SINC con hora del GPS (solo aplica a hora del sistema o del RTC)")

    hay_posicion = f["lat"] != "" or f["lon"] != ""
    if ("SIN_FIX" in banderas) == hay_posicion:
        p.append("SIN_FIX no concuerda con lat/lon")
    if hay_posicion and not (_es_real(f["lat"], -90, 90) and _es_real(f["lon"], -180, 180)):
        p.append(f"lat/lon fuera de rango: '{f['lat']}', '{f['lon']}'")
    for col, minimo, maximo in (("alt_m", -500, 10000), ("hdop", 0, 100), ("temp_c", -40, 80),
                                ("hr_pct", 0, 100), ("dht_edad_s", 0, math.inf),
                                ("espesor_mm", 0, 1000)):
        if f[col] != "" and not _es_real(f[col], minimo, maximo):
            p.append(f"{col} inválido: '{f[col]}'")
    if not _es_entero(f["fix"], minimo=0):
        p.append(f"fix inválido: '{f['fix']}'")
    if f["sats"] != "" and not _es_entero(f["sats"], minimo=0):
        p.append(f"sats inválido: '{f['sats']}'")
    if ("DHT_ERROR" in banderas) != (f["temp_c"] == ""):
        p.append("DHT_ERROR no concuerda con temp_c")
    if not f["version"]:
        p.append("version vacía")
    return p


def _revisar_metadatos(ruta_csv, filas):
    ruta = ruta_csv.with_suffix(".json")
    try:
        meta = json.loads(ruta.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return [f"falta {ruta.name}"], []
    except ValueError as e:
        return [f"{ruta.name} corrupto: {e}"], []
    errores, avisos = [], []
    if meta.get("sesion") != ruta_csv.stem:
        errores.append(f"{ruta.name}: sesion '{meta.get('sesion')}' no coincide")
    if meta.get("hora_cierre") is None:
        avisos.append(f"{ruta.name}: sesión sin cerrar (apagado sin aviso o sigue grabando)")
    elif meta.get("filas") is not None and meta["filas"] != filas:
        errores.append(f"{ruta.name}: dice {meta['filas']} filas y el CSV tiene {filas}")
    return errores, avisos


def _es_entero(texto, minimo):
    try:
        return int(texto) >= minimo
    except ValueError:
        return False


def _es_real(texto, minimo, maximo):
    try:
        x = float(texto)
    except ValueError:
        return False
    return math.isfinite(x) and minimo <= x <= maximo


def _es_utc(texto):
    if not texto.endswith("Z"):
        return False
    try:
        datetime.fromisoformat(texto[:-1])
        return True
    except ValueError:
        return False


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    rutas = []
    for arg in argv or ["datos"]:
        r = Path(arg)
        rutas.extend(sorted(r.glob("sesion_*.csv")) if r.is_dir() else [r])
    if not rutas:
        print("No se encontraron archivos sesion_*.csv")
        return 1

    total_errores = total_filas = 0
    for ruta in rutas:
        errores, avisos, filas = verificar_csv(ruta)
        total_errores += len(errores)
        total_filas += filas
        estado = "OK" if not errores else f"{len(errores)} ERRORES"
        print(f"{ruta.name}: {filas} filas válidas, {estado}, {len(avisos)} avisos")
        for e in errores[:20]:
            print(f"  ERROR  {e}")
        if len(errores) > 20:
            print(f"  ... y {len(errores) - 20} errores más")
        for a in avisos[:10]:
            print(f"  aviso  {a}")
        if len(avisos) > 10:
            print(f"  ... y {len(avisos) - 10} avisos más")
    print(f"\nTotal: {len(rutas)} sesiones, {total_filas} filas, {total_errores} errores")
    return 1 if total_errores else 0


if __name__ == "__main__":
    sys.exit(main())
