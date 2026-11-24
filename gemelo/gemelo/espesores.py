"""Espesores sintéticos de dos campañas, velocidad de corrosión (VC) y vida remanente (VR).

Se generan puntos sobre el modelo de ODM con una VC conocida por punto, se simulan dos campañas
de medición con ruido del instrumento y se recalcula:

    VC = (t_ant − t_act) / Δt          [mm/año]
    VR = (t_act − t_req) / VC          [años]

para comprobar que se recupera el valor conocido y medir cuánto error introduce el ruido.
Los espesores son sintéticos: todavía no hay medidor de espesores en la caja negra.

Uso: python -m gemelo.espesores [--config config.yaml]
Escribe salidas/espesores_por_punto.csv y salidas/espesores_ruido.csv.
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, nube


def puntos_de_nube(xyz, n, rng, region_xy=None, altura_min_m=1.0, suelo=None, altura_max_m=None):
    """Elige `n` puntos al azar de la nube `xyz` (N×3), sobre la estructura.

    `region_xy` (M×2, opcional): solo puntos dentro de su envolvente convexa (p. ej. el recorrido de la
    caja negra alrededor del edificio). Se conservan los puntos entre `suelo + altura_min_m` y
    `suelo + altura_max_m`; si no se da `suelo`, se usa el percentil 5 de z de la región.
    """
    xyz = np.asarray(xyz, dtype=float)
    ok = np.ones(len(xyz), dtype=bool)
    if region_xy is not None and len(region_xy) >= 3:
        from scipy.spatial import Delaunay
        ok &= Delaunay(np.asarray(region_xy, dtype=float)).find_simplex(xyz[:, :2]) >= 0
    if ok.any():
        suelo = np.percentile(xyz[ok, 2], 5) if suelo is None else suelo
        ok &= xyz[:, 2] >= suelo + altura_min_m
        if altura_max_m is not None:
            ok &= xyz[:, 2] <= suelo + altura_max_m
    candidatos = np.flatnonzero(ok)
    if len(candidatos) < n:
        raise ValueError(f"Solo hay {len(candidatos)} puntos candidatos sobre la estructura; se pidieron {n}")
    return xyz[rng.choice(candidatos, size=n, replace=False)]


def generar_campanas(xyz, p, rng, ruido_mm=None):
    """Espesores reales y medidos de dos campañas para cada punto.

    `p`: parámetros de config.yaml (sección `espesores`). Cada punto recibe una VC real uniforme en
    [vc_min, vc_max]; las mediciones llevan ruido uniforme ±ruido_mm (resolución del instrumento).
    """
    ruido = p["ruido_mm"] if ruido_mm is None else ruido_mm
    n = len(xyz)
    vc_real = rng.uniform(p["vc_min_mm_anio"], p["vc_max_mm_anio"], n)
    t_ant_real = p["t_inicial_mm"] - vc_real * p["anios_previos"]
    t_act_real = t_ant_real - vc_real * p["dt_anios"]
    return pd.DataFrame({
        "punto": np.arange(1, n + 1),
        "x_m": xyz[:, 0], "y_m": xyz[:, 1], "z_m": xyz[:, 2],
        "vc_real_mm_anio": vc_real,
        "t_ant_real_mm": t_ant_real, "t_act_real_mm": t_act_real,
        "t_ant_mm": t_ant_real + rng.uniform(-ruido, ruido, n),
        "t_act_mm": t_act_real + rng.uniform(-ruido, ruido, n),
    })


def calcular_vc_vr(df, dt_anios, t_req_mm):
    """Agrega VC y VR estimadas (de las mediciones), las reales y sus errores.

    Si la VC medida no es positiva (la pérdida queda dentro del ruido), la VR no se puede estimar: NaN.
    """
    df = df.copy()
    df["vc_mm_anio"] = (df["t_ant_mm"] - df["t_act_mm"]) / dt_anios
    df["vr_real_anios"] = (df["t_act_real_mm"] - t_req_mm) / df["vc_real_mm_anio"]
    vc = df["vc_mm_anio"].where(df["vc_mm_anio"] > 0)
    df["vr_anios"] = (df["t_act_mm"] - t_req_mm) / vc
    df["error_vc_mm_anio"] = df["vc_mm_anio"] - df["vc_real_mm_anio"]
    df["error_vr_anios"] = df["vr_anios"] - df["vr_real_anios"]
    return df


def resumen_errores(df):
    """Errores de VC (mm/año) y VR (años): medio absoluto, RMSE, máximo y relativo medio."""
    r = {}
    for var, real in (("vc", "vc_real_mm_anio"), ("vr", "vr_real_anios")):
        e = df[f"error_{var}_{'mm_anio' if var == 'vc' else 'anios'}"].dropna()
        rel = (e.abs() / df.loc[e.index, real].abs()).mean() if len(e) else np.nan
        r[f"{var}_error_medio_abs"] = float(e.abs().mean()) if len(e) else np.nan
        r[f"{var}_rmse"] = float(np.sqrt((e ** 2).mean())) if len(e) else np.nan
        r[f"{var}_error_max_abs"] = float(e.abs().max()) if len(e) else np.nan
        r[f"{var}_error_relativo_medio"] = float(rel)
    r["vr_no_estimable"] = int(df["vr_anios"].isna().sum())
    return r


def barrido_ruido(xyz, p, niveles_mm, repeticiones, semilla):
    """Monte Carlo: errores de VC y VR para cada nivel de ruido del instrumento."""
    filas = []
    for ruido in niveles_mm:
        rng = np.random.default_rng(semilla)
        partes = [calcular_vc_vr(generar_campanas(xyz, p, rng, ruido), p["dt_anios"], p["t_req_mm"])
                  for _ in range(repeticiones)]
        filas.append({"ruido_mm": ruido, "repeticiones": repeticiones,
                      **resumen_errores(pd.concat(partes, ignore_index=True))})
    return pd.DataFrame(filas)


def main(argv=None):
    p = argparse.ArgumentParser(prog="gemelo.espesores", description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(config.RUTA_DEFECTO))
    args = p.parse_args(argv)
    cfg = config.cargar(args.config)
    e = cfg["espesores"]
    rng = np.random.default_rng(e["semilla"])

    ruta_nube = Path(cfg["ruta_nube"])
    if not ruta_nube.exists():
        raise SystemExit(f"No existe la nube de puntos de ODM: {ruta_nube}")
    region = suelo = None
    nube_xyz = nube.leer(ruta_nube)
    fusionadas = Path(cfg["carpeta_salidas"]) / "lecturas_fusionadas.csv"
    if fusionadas.exists():  # recorrido de la caja negra alrededor de la estructura
        f = pd.read_csv(fusionadas, usecols=["x_m", "y_m"]).dropna()
        if len(f) >= 3:
            region = f[["x_m", "y_m"]].to_numpy()
            suelo = nube.suelo_del_recorrido(nube_xyz, region)
    xyz = puntos_de_nube(nube_xyz, e["n_puntos"], rng, region, e["altura_min_m"], suelo, e["altura_max_m"])

    df = calcular_vc_vr(generar_campanas(xyz, e, rng), e["dt_anios"], e["t_req_mm"])
    barrido = barrido_ruido(xyz, e, e["niveles_ruido_mm"], e["repeticiones"], e["semilla"])
    salidas = Path(cfg["carpeta_salidas"])
    salidas.mkdir(parents=True, exist_ok=True)
    df.round(4).to_csv(salidas / "espesores_por_punto.csv", index=False)
    barrido.round(4).to_csv(salidas / "espesores_ruido.csv", index=False)

    r = resumen_errores(df)
    print(f"{len(df)} puntos sobre la estructura" + (f" (dentro del recorrido de la caja negra; suelo a "
                                                      f"{suelo:.1f} m)" if region is not None else ""))
    print(f"Campañas separadas {e['dt_anios']} años; espesor mínimo requerido {e['t_req_mm']} mm; "
          f"ruido del instrumento ±{e['ruido_mm']} mm")
    print(f"VC: error medio {r['vc_error_medio_abs']:.4f} mm/año ({r['vc_error_relativo_medio']:.1%}), "
          f"máx {r['vc_error_max_abs']:.4f} mm/año")
    print(f"VR: error medio {r['vr_error_medio_abs']:.2f} años ({r['vr_error_relativo_medio']:.1%}), "
          f"máx {r['vr_error_max_abs']:.2f} años; VR no estimable en {r['vr_no_estimable']} puntos")
    print("\nError según el ruido del instrumento (Monte Carlo):")
    print(barrido[["ruido_mm", "vc_error_medio_abs", "vc_error_relativo_medio", "vr_error_medio_abs",
                   "vr_error_relativo_medio", "vr_no_estimable"]].round(4).to_string(index=False))
    print(f"\nEscrito: {salidas / 'espesores_por_punto.csv'}, {salidas / 'espesores_ruido.csv'}")


if __name__ == "__main__":
    main()
