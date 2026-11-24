"""Fusión: CSV de la caja negra → lecturas con hora corregida, banderas de validez y puntos UTM con altura del DSM.

Uso: python -m gemelo.fusion [--config config.yaml]
Escribe salidas/lecturas_fusionadas.csv (todas las filas, con el motivo de descarte de cada una).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

# Contrato de datos de la caja negra (CLAUDE.md, sección 7). Se repite aquí porque corre en otra máquina.
COLUMNAS = ["sesion", "seq", "t_mono_s", "utc", "fuente_hora", "lat", "lon", "alt_m",
            "fix", "sats", "hdop", "temp_c", "hr_pct", "dht_edad_s", "espesor_mm",
            "banderas", "version"]
SALTO_RELOJ_S = 2.0  # cambio en (utc − t_mono_s) mayor que esto = el reloj se ajustó


def leer_sesiones(carpeta, sesiones=None):
    """Une los sesion_*.csv de la carpeta. Descarta la última fila si quedó cortada por un apagón.

    `sesiones`: nombres a usar (p. ej. ["sesion_0027"]); vacío o None = todas las de la carpeta.
    """
    rutas = sorted(Path(carpeta).glob("sesion_*.csv"))
    if sesiones:
        faltan = set(sesiones) - {r.stem for r in rutas}
        if faltan:
            raise FileNotFoundError(f"No están en {carpeta}: {sorted(faltan)}")
        rutas = [r for r in rutas if r.stem in sesiones]
    if not rutas:
        raise FileNotFoundError(f"No hay archivos sesion_*.csv en {carpeta}")
    partes = []
    for ruta in rutas:
        df = pd.read_csv(ruta, dtype={"sesion": str, "fuente_hora": str, "banderas": str, "version": str},
                         on_bad_lines="skip")
        faltan = set(COLUMNAS) - set(df.columns)
        if faltan:
            raise ValueError(f"{ruta.name}: faltan columnas del contrato {sorted(faltan)}")
        partes.append(df[COLUMNAS])
    df = pd.concat(partes, ignore_index=True)
    # Una fila cortada no llega hasta la última columna (version).
    df = df.dropna(subset=["sesion", "seq", "t_mono_s", "version"]).copy()
    df["seq"] = df["seq"].astype(int)
    df["banderas"] = df["banderas"].fillna("")
    df["utc"] = pd.to_datetime(df["utc"], utc=True, format="ISO8601", errors="coerce")
    return df.sort_values(["sesion", "seq"]).reset_index(drop=True)


def tiene(banderas, bandera):
    """Serie booleana: la columna `banderas` (separadas por ;) contiene `bandera`."""
    return banderas.str.split(";").apply(lambda b: bandera in b)


def corregir_hora(df):
    """Corrige `utc` de las filas cuya hora no es confiable, usando el reloj monotónico de su sesión.

    Confiables: hora GPS, o del sistema sin HORA_NO_SINC. Si dentro de ellas el reloj salta (sesiones
    v0.1.0, sin la bandera), solo vale el último tramo, porque los ajustes del reloj (NTP, GPS) lo
    acercan a la hora real. Agrega `hora_corregida` y `hora_valida` (False si la sesión no tiene
    ninguna fila confiable).
    """
    df = df.copy()
    df["hora_corregida"] = False
    df["hora_valida"] = True
    for _, g in df.groupby("sesion"):
        arranque = g["utc"] - pd.to_timedelta(g["t_mono_s"], unit="s")  # hora del arranque según cada fila
        candidatas = g["utc"].notna() & ~tiene(g["banderas"], "HORA_NO_SINC")
        if not candidatas.any():
            df.loc[g.index, "hora_valida"] = False
            continue
        a = arranque[candidatas]
        tramo = (a.diff().dt.total_seconds().abs() > SALTO_RELOJ_S).cumsum()
        referencia = a[tramo == tramo.iloc[-1]].median()
        malas = g.index[~g.index.isin(a.index[tramo == tramo.iloc[-1]])]
        corregida = referencia + pd.to_timedelta(df.loc[malas, "t_mono_s"], unit="s")
        # El CSV trae milisegundos; redondear evita restos de coma flotante y respeta la unidad de la columna.
        df.loc[malas, "utc"] = corregida.dt.round("ms").dt.as_unit(df["utc"].dt.unit)
        df.loc[malas, "hora_corregida"] = True
    return df


def clasificar(df, hdop_max):
    """Agrega `valida_ambiente` (T y HR usables), `valida_posicion` y `motivo_descarte`."""
    df = df.copy()
    motivos = {
        "dht_error": tiene(df["banderas"], "DHT_ERROR") | df["temp_c"].isna() | df["hr_pct"].isna(),
        "dht_viejo": tiene(df["banderas"], "DHT_VIEJO"),
        "hora_invalida": ~df["hora_valida"],
        "sin_fix": (df["fix"].fillna(0) <= 0) | df["lat"].isna() | df["lon"].isna(),
        "hdop_alto": df["hdop"].isna() | (df["hdop"] > hdop_max),
    }
    df["valida_ambiente"] = ~(motivos["dht_error"] | motivos["dht_viejo"] | motivos["hora_invalida"])
    df["valida_posicion"] = ~(motivos["sin_fix"] | motivos["hdop_alto"])
    # Sin fix el HDOP no significa nada: no se reporta también como hdop_alto.
    motivos["hdop_alto"] = motivos["hdop_alto"] & ~motivos["sin_fix"]
    df["motivo_descarte"] = [";".join(m for m, v in zip(motivos, fila) if v)
                             for fila in zip(*motivos.values())]
    return df


def crs_destino(cfg):
    """CRS del DSM de ODM si existe; si no, el de config.yaml."""
    if Path(cfg["ruta_dsm"]).exists():
        import rasterio
        with rasterio.open(cfg["ruta_dsm"]) as r:
            return r.crs.to_string()
    return cfg["crs_defecto"]


def a_utm(df, crs):
    """Agrega x_m, y_m en `crs` para las filas con posición válida (NaN en las demás)."""
    from pyproj import Transformer

    df = df.copy()
    df["x_m"] = df["y_m"] = np.nan
    ok = df["valida_posicion"]
    if ok.any():
        t = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x, y = t.transform(df.loc[ok, "lon"].to_numpy(), df.loc[ok, "lat"].to_numpy())
        df.loc[ok, "x_m"], df.loc[ok, "y_m"] = x, y
    df["crs"] = crs
    return df


def altura_dsm(df, ruta_dsm):
    """Agrega z_dsm_m: altura del DSM bajo cada punto (NaN sin posición, fuera del ráster o sin dato)."""
    df = df.copy()
    df["z_dsm_m"] = np.nan
    ok = df["x_m"].notna()
    if not ok.any() or not Path(ruta_dsm).exists():
        return df
    import rasterio

    with rasterio.open(ruta_dsm) as r:
        b = r.bounds
        x, y = df.loc[ok, "x_m"], df.loc[ok, "y_m"]
        dentro = ok.copy()
        dentro[ok] = (x >= b.left) & (x < b.right) & (y > b.bottom) & (y <= b.top)
        if dentro.any():
            puntos = list(zip(df.loc[dentro, "x_m"], df.loc[dentro, "y_m"]))
            valores = np.ma.vstack(list(r.sample(puntos, masked=True)))[:, 0]
            df.loc[dentro, "z_dsm_m"] = valores.astype(float).filled(np.nan)  # sin dato → NaN
    return df


def fusionar(cfg):
    """Pipeline completo a partir de la configuración."""
    df = leer_sesiones(cfg["carpeta_cajanegra"], cfg.get("sesiones"))
    df = corregir_hora(df)
    df = clasificar(df, cfg["hdop_max"])
    df = a_utm(df, crs_destino(cfg))
    return altura_dsm(df, cfg["ruta_dsm"])


def resumen(df):
    """Métricas para el informe: lecturas totales, válidas y descartadas por motivo."""
    motivos = df["motivo_descarte"].str.split(";").explode()
    return {
        "sesiones": df["sesion"].nunique(),
        "lecturas": len(df),
        "validas_ambiente": int(df["valida_ambiente"].sum()),
        "validas_posicion": int(df["valida_posicion"].sum()),
        "con_altura_dsm": int(df["z_dsm_m"].notna().sum()),
        "hora_corregida": int(df["hora_corregida"].sum()),
        "descartes": motivos[motivos != ""].value_counts().to_dict(),
    }


def main(argv=None):
    p = argparse.ArgumentParser(prog="gemelo.fusion", description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(config.RUTA_DEFECTO))
    args = p.parse_args(argv)
    cfg = config.cargar(args.config)

    df = fusionar(cfg)
    salida = Path(cfg["carpeta_salidas"]) / "lecturas_fusionadas.csv"
    salida.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(salida, index=False, date_format="%Y-%m-%dT%H:%M:%S.%fZ")

    r = resumen(df)
    print(f"Sesiones: {r['sesiones']}   lecturas: {r['lecturas']}")
    print(f"Válidas para ambiente (T, HR): {r['validas_ambiente']}")
    print(f"Válidas para posición (fix, HDOP <= {cfg['hdop_max']}): {r['validas_posicion']}"
          f"   con altura del DSM: {r['con_altura_dsm']}"
          + ("" if Path(cfg["ruta_dsm"]).exists() else "  (aún no hay DSM de ODM)"))
    print(f"Filas con hora corregida: {r['hora_corregida']}")
    print("Motivos de descarte (una fila puede tener varios):")
    for motivo, n in r["descartes"].items():
        print(f"  {motivo}: {n}")
    print(f"CRS: {df['crs'].iloc[0]}\nEscrito: {salida}")


if __name__ == "__main__":
    main()
