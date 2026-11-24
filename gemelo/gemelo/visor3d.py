"""Visor 3D del gemelo en HTML (plotly): nube de puntos de ODM a color + capas de datos.

Capas (se encienden y apagan en la leyenda):
  - Nube de puntos georreferenciada de ODM con sus colores (submuestreada para el navegador).
  - Lecturas de la caja negra coloreadas por temperatura y por humedad relativa, a la altura a la que
    se cargó la caja (suelo local + altura_caja_m).
  - Puntos de espesor sintéticos coloreados por vida remanente (VR).

Uso: python -m gemelo.visor3d [--config config.yaml] [--max-puntos 250000]
Necesita la nube de ODM y salidas/lecturas_fusionadas.csv; usa salidas/espesores_por_punto.csv si existe.
Escribe salidas/visor3d.html (autocontenido: funciona sin internet).
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

from . import config, nube

ALTURA_CAJA_M = 1.2   # altura aproximada a la que se cargó la caja negra
RADIO_SUELO_M = 3.0   # radio para estimar el suelo local bajo cada lectura


def nube_recortada(cfg, camino_xy, rng):
    """(xyz, colores 'rgb(r,g,b)', suelo): nube de ODM recortada a la estructura y submuestreada."""
    v = cfg["visor3d"]
    xyz, rgb = nube.leer(cfg["ruta_nube"], con_color=True)
    suelo = nube.suelo_del_recorrido(xyz, camino_xy)
    ok = nube.recortar(xyz, camino_xy, v["margen_m"], suelo - v["bajo_suelo_m"], suelo + v["sobre_suelo_m"])
    idx = np.flatnonzero(ok)
    idx = rng.choice(idx, size=min(v["max_puntos"], len(idx)), replace=False)
    colores = "#888" if rgb is None else [f"rgb({r},{g},{b})" for r, g, b in rgb[idx]]
    return xyz[idx], colores, suelo


def suelo_local(xyz_nube, xy, radio=RADIO_SUELO_M, percentil=5):
    """Altura del suelo bajo cada punto `xy`: percentil bajo de z de la nube en un radio."""
    from scipy.spatial import cKDTree

    arbol = cKDTree(xyz_nube[:, :2])
    z_global = np.percentile(xyz_nube[:, 2], percentil)
    vecinos = arbol.query_ball_point(xy, r=radio)
    return np.array([np.percentile(xyz_nube[v, 2], percentil) if len(v) >= 5 else z_global for v in vecinos])


def trazas_volumen(esquinas, altura, z0, info):
    """Bloque semitransparente (4 muros y azotea) y sus aristas, en coordenadas locales."""
    import plotly.graph_objects as go

    abajo = np.column_stack([esquinas, np.full(4, z0)])
    arriba = np.column_stack([esquinas, np.full(4, z0 + altura)])
    v = np.vstack([abajo, arriba])  # 0–3 abajo, 4–7 arriba
    caras = [(a, b, b + 4) for a, b in ((0, 1), (1, 2), (2, 3), (3, 0))] \
        + [(a, b + 4, a + 4) for a, b in ((0, 1), (1, 2), (2, 3), (3, 0))] + [(4, 5, 6), (4, 6, 7)]
    i, j, k = np.array(caras).T
    nombre = f"Volumen del edificio (LOD1: {info['largo_m']:.0f} × {info['ancho_m']:.0f} × {info['altura_m']:.1f} m)"
    bloque = go.Mesh3d(x=v[:, 0], y=v[:, 1], z=v[:, 2], i=i, j=j, k=k, color="#9ecae1", opacity=0.22,
                       name=nombre, showlegend=True, legendgroup="lod1", hoverinfo="name", flatshading=True)
    orden = [0, 1, 2, 3, 0, 4, 5, 6, 7, 4, None, 1, 5, None, 2, 6, None, 3, 7]
    aristas = go.Scatter3d(x=[None if n is None else v[n, 0] for n in orden],
                           y=[None if n is None else v[n, 1] for n in orden],
                           z=[None if n is None else v[n, 2] for n in orden], mode="lines",
                           line=dict(color="#08306b", width=5), legendgroup="lod1", showlegend=False, hoverinfo="skip")
    return [bloque, aristas]


def construir(cfg):
    import plotly.graph_objects as go

    salidas = Path(cfg["carpeta_salidas"])
    df = pd.read_csv(salidas / "lecturas_fusionadas.csv")
    df = df[df["valida_posicion"] & df["valida_ambiente"]].iloc[::2]
    xy = df[["x_m", "y_m"]].to_numpy()

    rng = np.random.default_rng(0)
    xyz, colores, suelo = nube_recortada(cfg, xy, rng)
    origen = np.array([*xyz[:, :2].mean(axis=0), suelo])  # coordenadas locales; z = 0 en el suelo
    local = xyz - origen

    figura = go.Figure()
    hay_malla = Path(cfg["ruta_modelo"]).exists()
    if hay_malla:  # superficie con los colores de las fotos (se ve mejor que la nube)
        v = cfg["visor3d"]
        mv, mc, mcol = nube.leer_malla(cfg["ruta_modelo"], cfg["ruta_coords"] if Path(cfg["ruta_coords"]).exists() else None)
        centros = mv[mc].mean(axis=1)
        ok = nube.recortar(centros, xy, v["margen_m"], suelo - v["bajo_suelo_m"], suelo + v["sobre_suelo_m"])
        mv, mc, mcol = nube.recortar_malla(mv, mc, mcol, ok)
        mv = mv - origen
        figura.add_trace(go.Mesh3d(x=mv[:, 0], y=mv[:, 1], z=mv[:, 2], i=mc[:, 0], j=mc[:, 1], k=mc[:, 2],
                                   facecolor=[f"rgb({r},{g},{b})" for r, g, b in mcol], flatshading=True,
                                   lighting=dict(ambient=0.85, diffuse=0.25, specular=0.0, roughness=1.0),
                                   name="Modelo con textura (malla ODM)", showlegend=True, hoverinfo="skip"))
    figura.add_trace(go.Scatter3d(x=local[:, 0], y=local[:, 1], z=local[:, 2], mode="markers",
                                  marker=dict(size=1.6, color=colores), name="Nube de puntos (ODM)",
                                  hoverinfo="skip", visible="legendonly" if hay_malla else True))

    ruta_vol = salidas / "volumen_lod1.json"
    if ruta_vol.exists():  # volumen simplificado: da la forma del edificio aunque falten muros en la malla
        import json
        vol = json.loads(ruta_vol.read_text(encoding="utf-8"))
        for traza in trazas_volumen(np.array(vol["esquinas_utm"]) - origen[:2], vol["altura_m"],
                                    vol["suelo_m"] - origen[2], vol):
            figura.add_trace(traza)
    z = suelo_local(xyz, xy) + ALTURA_CAJA_M
    hover = [f"{str(u)[11:19]} UTC<br>T {t:.1f} °C<br>HR {h:.1f} %"
             for u, t, h in zip(df["utc"], df["temp_c"], df["hr_pct"])]
    comun = dict(x=xy[:, 0] - origen[0], y=xy[:, 1] - origen[1], z=z - origen[2], mode="markers",
                 text=hover, hoverinfo="text")
    figura.add_trace(go.Scatter3d(**comun, name="Temperatura (°C)", marker=dict(
        size=3.5, color=df["temp_c"], colorscale="RdYlBu_r",
        colorbar=dict(title="T (°C)", x=1.0, len=0.45, y=0.78))))
    figura.add_trace(go.Scatter3d(**comun, name="Humedad relativa (%)", visible="legendonly", marker=dict(
        size=3.5, color=df["hr_pct"], colorscale="YlGnBu", colorbar=dict(title="HR (%)", x=1.08, len=0.45, y=0.78))))

    ruta_esp = salidas / "espesores_por_punto.csv"
    if ruta_esp.exists():
        e = pd.read_csv(ruta_esp)
        texto = [f"Punto {int(p)}<br>VC {vc:.3f} mm/año (real {vcr:.3f})<br>VR {vr:.1f} años (real {vrr:.1f})"
                 for p, vc, vcr, vr, vrr in zip(e["punto"], e["vc_mm_anio"], e["vc_real_mm_anio"],
                                                 e["vr_anios"], e["vr_real_anios"])]
        figura.add_trace(go.Scatter3d(
            x=e["x_m"] - origen[0], y=e["y_m"] - origen[1], z=e["z_m"] - origen[2], mode="markers",
            name="Espesores sintéticos (VR, años)", text=texto, hoverinfo="text",
            marker=dict(size=6, symbol="diamond", color=e["vr_anios"], colorscale="RdYlGn",
                        line=dict(color="black", width=1),
                        colorbar=dict(title="VR (años)", x=1.0, len=0.45, y=0.25))))

    figura.update_layout(
        title=f"Gemelo digital · {cfg['proyecto']} (origen local: E {origen[0]:.1f}, N {origen[1]:.1f} UTM; "
              f"altura 0 = suelo, {origen[2]:.1f} m)",
        scene=dict(aspectmode="data", xaxis_title="Este (m)", yaxis_title="Norte (m)",
                   zaxis_title="Altura sobre el suelo (m)",
                   camera=dict(eye=dict(x=1.1, y=-1.3, z=0.8))),
        legend=dict(x=0, y=1), margin=dict(l=0, r=0, t=40, b=0), paper_bgcolor="#f4f4f4")
    return figura


def main(argv=None):
    p = argparse.ArgumentParser(prog="gemelo.visor3d", description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(config.RUTA_DEFECTO))
    p.add_argument("--max-puntos", type=int, help="puntos de la nube en el HTML (por defecto, config.yaml)")
    args = p.parse_args(argv)
    cfg = config.cargar(args.config)
    if args.max_puntos:
        cfg["visor3d"]["max_puntos"] = args.max_puntos
    for ruta, como in ((cfg["ruta_nube"], "corre ODM (fase 6)"),
                       (Path(cfg["carpeta_salidas"]) / "lecturas_fusionadas.csv", "corre  python -m gemelo.fusion")):
        if not Path(ruta).exists():
            raise SystemExit(f"Falta {ruta}: {como}")
    salida = Path(cfg["carpeta_salidas"]) / "visor3d.html"
    construir(cfg).write_html(str(salida), include_plotlyjs=True)
    print(f"Escrito: {salida}")


if __name__ == "__main__":
    main()
