"""Tiempo de humectación por sesión y por zona, con el criterio de la ISO 9223 (HR > 80 % y T > 0 °C).

Es un indicador de la sesión medida, NO una clasificación anual de corrosividad: la ISO 9223
clasifica con las horas húmedas de un año completo.

Uso: python -m gemelo.humectacion [--config config.yaml]
Escribe salidas/humectacion_por_sesion.csv y salidas/humectacion_por_zona.csv.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, fusion

SIN_POSICION = "sin_posicion"


def marcar_humedo(df, hr_min_pct, temp_min_c):
    """Agrega `humedo`: HR > hr_min y T > temp_min (desigualdades estrictas, como la norma)."""
    df = df.copy()
    df["humedo"] = (df["hr_pct"] > hr_min_pct) & (df["temp_c"] > temp_min_c)
    return df


def duraciones(df, max_dt_s):
    """Agrega `dt_s`: tiempo que representa cada lectura (hasta la siguiente de su sesión).

    Se limita a `max_dt_s` para que un hueco o un apagado no cuente como tiempo medido. La última
    fila de cada sesión toma la mediana de su sesión.
    """
    df = df.sort_values(["sesion", "t_mono_s"]).copy()
    dt = df.groupby("sesion")["t_mono_s"].diff(-1).abs()
    mediana = df.assign(dt=dt).groupby("sesion")["dt"].transform("median")
    df["dt_s"] = dt.fillna(mediana).fillna(1.0).clip(upper=max_dt_s)
    return df


def asignar_zona(df, tam_zona_m):
    """Agrega `zona` (celda de tam_zona_m × tam_zona_m en UTM) y el centro de la celda.

    Las lecturas sin posición válida van a la zona 'sin_posicion'.
    """
    df = df.copy()
    con_pos = df["x_m"].notna() & df["y_m"].notna()
    ix = np.floor(df["x_m"] / tam_zona_m)
    iy = np.floor(df["y_m"] / tam_zona_m)
    df["zona"] = SIN_POSICION
    df.loc[con_pos, "zona"] = (ix[con_pos].astype(int).astype(str) + "_"
                               + iy[con_pos].astype(int).astype(str))
    df["zona_x_m"] = (ix + 0.5) * tam_zona_m
    df["zona_y_m"] = (iy + 0.5) * tam_zona_m
    return df


def resumir(df, claves):
    """Fracción de tiempo húmedo y estadísticos de T y HR por grupo."""
    df = df.assign(dt_humedo_s=df["dt_s"] * df["humedo"])
    g = df.groupby(claves, dropna=False)
    r = g.agg(lecturas=("humedo", "size"), tiempo_s=("dt_s", "sum"), tiempo_humedo_s=("dt_humedo_s", "sum"),
              temp_media_c=("temp_c", "mean"), temp_min_c=("temp_c", "min"), temp_max_c=("temp_c", "max"),
              hr_media_pct=("hr_pct", "mean"), hr_min_pct=("hr_pct", "min"), hr_max_pct=("hr_pct", "max"),
              inicio_utc=("utc", "min"), fin_utc=("utc", "max"))
    r["fraccion_humeda"] = r["tiempo_humedo_s"] / r["tiempo_s"]
    return r.reset_index().round({"tiempo_s": 1, "tiempo_humedo_s": 1, "fraccion_humeda": 4,
                                  "temp_media_c": 2, "hr_media_pct": 2})


def calcular(df_fusion, cfg_humectacion):
    """Lecturas válidas para ambiente → (detalle por lectura, resumen por sesión, resumen por zona)."""
    h = cfg_humectacion
    df = duraciones(df_fusion, h["max_dt_s"])  # antes de filtrar: el dt va hasta la siguiente fila real
    df = df[df["valida_ambiente"]]
    df = marcar_humedo(df, h["hr_min_pct"], h["temp_min_c"])
    df = asignar_zona(df, h["tam_zona_m"])
    por_sesion = resumir(df, ["sesion"])
    por_zona = resumir(df, ["zona"])
    centros = df.groupby("zona")[["zona_x_m", "zona_y_m"]].first().reset_index()
    por_zona = por_zona.merge(centros, on="zona")
    por_zona.loc[por_zona["zona"] == SIN_POSICION, ["zona_x_m", "zona_y_m"]] = np.nan
    return df, por_sesion, por_zona


def main(argv=None):
    p = argparse.ArgumentParser(prog="gemelo.humectacion", description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(config.RUTA_DEFECTO))
    args = p.parse_args(argv)
    cfg = config.cargar(args.config)
    h = cfg["humectacion"]

    _, por_sesion, por_zona = calcular(fusion.fusionar(cfg), h)
    salidas = Path(cfg["carpeta_salidas"])
    salidas.mkdir(parents=True, exist_ok=True)
    formato = "%Y-%m-%dT%H:%M:%SZ"
    por_sesion.to_csv(salidas / "humectacion_por_sesion.csv", index=False, date_format=formato)
    por_zona.to_csv(salidas / "humectacion_por_zona.csv", index=False, date_format=formato)

    print(f"Criterio: HR > {h['hr_min_pct']} % y T > {h['temp_min_c']} °C (ISO 9223). "
          "Indicador de la sesión, no clasificación anual.\n")
    columnas = ["sesion", "lecturas", "tiempo_s", "fraccion_humeda", "temp_media_c", "hr_media_pct", "hr_max_pct"]
    print(por_sesion[columnas].to_string(index=False))
    total = por_sesion["tiempo_s"].sum()
    print(f"\nTotal: {total / 3600:.2f} h medidas, "
          f"{por_sesion['tiempo_humedo_s'].sum() / total:.1%} del tiempo húmedo")
    print(f"Zonas: {len(por_zona)} ({(por_zona['zona'] != SIN_POSICION).sum()} con posición)")
    print(f"Escrito: {salidas / 'humectacion_por_sesion.csv'}, {salidas / 'humectacion_por_zona.csv'}")


if __name__ == "__main__":
    main()
