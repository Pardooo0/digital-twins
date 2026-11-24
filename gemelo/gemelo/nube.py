"""Nube de puntos de ODM: lectura, nivel del suelo, recorte y volumen simplificado (LOD1) de la estructura.

Con fotos casi horizontales la nube trae puntos sueltos muy arriba y muy abajo (cielo, horizonte);
por eso el suelo se mide junto al camino de la caja negra (que siempre va por el suelo) y la nube se
recorta en planta y en altura antes de usarla.

Uso: python -m gemelo.nube [--config config.yaml]
Necesita la nube de ODM y salidas/lecturas_fusionadas.csv. Escribe salidas/volumen_lod1.json
(suelo, esquinas en UTM y en WGS84, altura, largo, ancho, orientación) para el mapa y el visor 3D.
"""

import argparse
import json
from pathlib import Path

import numpy as np


def leer(ruta_laz, con_color=False):
    """xyz (N×3) y, si se pide, colores RGB 0–255 (N×3, o None si la nube no trae color)."""
    import laspy

    with laspy.open(ruta_laz) as f:
        n = f.read()
    xyz = np.column_stack([n.x, n.y, n.z])
    if not con_color:
        return xyz
    try:
        rgb = np.column_stack([n.red, n.green, n.blue]).astype(float)
        rgb = (rgb / (256.0 if rgb.max() > 255 else 1.0)).clip(0, 255).astype(np.uint8)
    except AttributeError:
        rgb = None
    return xyz, rgb


def leer_malla(ruta_obj, ruta_coords=None):
    """Malla texturizada de ODM (.obj + .mtl + texturas) → (vértices N×3, caras M×3, color RGB por cara M×3).

    El color de cada cara se toma de su textura en el centro de la cara (coordenadas UV). ODM guarda x, y
    restando el desplazamiento de `coords.txt` (2.ª línea: este norte); aquí se suma para quedar en UTM.
    """
    import trimesh

    escena = trimesh.load(ruta_obj, process=False)
    geometrias = list(escena.geometry.values()) if isinstance(escena, trimesh.Scene) else [escena]
    vertices, caras, colores, base = [], [], [], 0
    for g in geometrias:
        f = np.asarray(g.faces)
        try:
            img = np.asarray(g.visual.material.image.convert("RGB"))
            uv = np.asarray(g.visual.uv)[f].mean(axis=1)
            alto, ancho = img.shape[:2]
            px = np.clip(np.round(uv[:, 0] * (ancho - 1)).astype(int), 0, ancho - 1)
            py = np.clip(np.round((1 - uv[:, 1]) * (alto - 1)).astype(int), 0, alto - 1)
            colores.append(img[py, px])
        except AttributeError:  # parte sin textura
            colores.append(np.full((len(f), 3), 160, dtype=np.uint8))
        vertices.append(np.asarray(g.vertices, dtype=float))
        caras.append(f + base)
        base += len(g.vertices)
    v = np.vstack(vertices)
    if ruta_coords is not None:
        este, norte = map(float, open(ruta_coords, encoding="utf-8").read().splitlines()[1].split()[:2])
        v[:, 0] += este
        v[:, 1] += norte
    return v, np.vstack(caras), np.vstack(colores).astype(np.uint8)


def recortar_malla(vertices, caras, colores, mascara_cara):
    """Conserva solo las caras de `mascara_cara` y reindexa los vértices que usan."""
    caras, colores = caras[mascara_cara], colores[mascara_cara]
    usados, nuevas = np.unique(caras, return_inverse=True)
    return vertices[usados], nuevas.reshape(caras.shape), colores


def suelo_del_recorrido(xyz, camino_xy, radio_m=1.5, paso_m=0.25):
    """Altura del suelo: la z más frecuente (moda) de los puntos a menos de `radio_m` del camino."""
    from scipy.spatial import cKDTree

    dist, _ = cKDTree(np.asarray(camino_xy, dtype=float)).query(xyz[:, :2])
    z = xyz[dist < radio_m, 2]
    if len(z) < 20:
        raise ValueError("Muy pocos puntos de la nube junto al camino de la caja negra para medir el suelo")
    conteo, bordes = np.histogram(z, bins=np.arange(z.min(), z.max() + paso_m, paso_m))
    i = int(conteo.argmax())
    return float(np.median(z[(z >= bordes[i]) & (z <= bordes[i + 1])]))


def orientacion_camino(camino_xy, paso_m=0.5):
    """Ángulo (grados, 0–90) de los lados de la estructura: dirección dominante del camino de la caja negra."""
    p = np.asarray(camino_xy, dtype=float)
    q = [p[0]]
    for punto in p[1:]:  # un punto cada paso_m: la caja quieta no pesa más que la caminata
        if np.hypot(*(punto - q[-1])) >= paso_m:
            q.append(punto)
    d = np.diff(np.array(q), axis=0)
    largos = np.hypot(d[:, 0], d[:, 1])
    angulos = np.degrees(np.arctan2(d[:, 1], d[:, 0])) % 90
    h, _ = np.histogram(angulos, bins=90, range=(0, 90), weights=largos)
    suavizado = np.convolve(np.r_[h[-3:], h, h[:3]], np.ones(7), "valid")  # circular: 89° ≈ 0°
    grueso = (suavizado.argmax() + 0.5) % 90
    # Afinar: promedio ponderado de los ángulos a ±5° del pico (el histograma solo da la estimación gruesa).
    dif = (angulos - grueso + 45) % 90 - 45
    cerca = np.abs(dif) <= 5
    return float((grueso + np.average(dif[cerca], weights=largos[cerca])) % 90), np.array(q)


def volumen_lod1(xyz, camino_xy, suelo, umbral=0.25, muro_m=(1.5, 6.0), alto_max_m=15.0):
    """Volumen simplificado (LOD1) de la estructura: rectángulo de muros × altura.

    1. Orientación: dirección dominante del camino de la caja negra.
    2. Muros: en ejes girados, los picos más exteriores (≥ `umbral` del máximo) del histograma de los
       puntos entre suelo + muro_m[0] y suelo + muro_m[1], dentro del camino.
    3. Altura: percentil 90 de la nube dentro de la planta (suelo + 1 m a suelo + alto_max_m).
    Devuelve dict con esquinas (4×2, UTM), altura_m, largo_m, ancho_m y angulo_grados.
    """
    angulo, q = orientacion_camino(camino_xy)
    t = np.radians(angulo)
    R = np.array([[np.cos(t), np.sin(t)], [-np.sin(t), np.cos(t)]])
    centro = q.mean(axis=0)
    rq = (q - centro) @ R.T
    lo, hi = np.percentile(rq, 3, axis=0), np.percentile(rq, 97, axis=0)
    rr = (xyz[:, :2] - centro) @ R.T
    dentro_camino = np.all((rr > lo) & (rr < hi), axis=1)
    muro = dentro_camino & (xyz[:, 2] > suelo + muro_m[0]) & (xyz[:, 2] < suelo + muro_m[1])
    if muro.sum() < 100:
        raise ValueError("Muy pocos puntos de muro en la nube para estimar el volumen")
    limites = []
    for eje in (0, 1):
        h, e = np.histogram(rr[muro, eje], bins=np.arange(lo[eje], hi[eje] + 0.5, 0.5))
        fuertes = np.flatnonzero(h >= umbral * h.max())
        limites.append((e[fuertes[0]] + 0.25, e[fuertes[-1]] + 0.25))
    (u0, u1), (v0, v1) = limites
    dentro = ((rr[:, 0] > u0) & (rr[:, 0] < u1) & (rr[:, 1] > v0) & (rr[:, 1] < v1)
              & (xyz[:, 2] > suelo + 1) & (xyz[:, 2] < suelo + alto_max_m))
    altura = float(np.percentile(xyz[dentro, 2] - suelo, 90)) if dentro.any() else 3.0
    esquinas = np.array([[u0, v0], [u1, v0], [u1, v1], [u0, v1]]) @ R + centro
    return {"esquinas": esquinas, "altura_m": altura, "largo_m": float(u1 - u0), "ancho_m": float(v1 - v0),
            "angulo_grados": float(angulo)}


def recortar(xyz, region_xy=None, margen_m=8.0, z_min=None, z_max=None):
    """Máscara booleana: puntos dentro de la envolvente de `region_xy` (ampliada `margen_m`) y en [z_min, z_max]."""
    ok = np.ones(len(xyz), dtype=bool)
    if region_xy is not None and len(region_xy) >= 3:
        from scipy.spatial import ConvexHull, Delaunay

        r = np.asarray(region_xy, dtype=float)
        casco = r[ConvexHull(r).vertices]
        centro = casco.mean(axis=0)
        radios = np.linalg.norm(casco - centro, axis=1, keepdims=True)
        ampliado = centro + (casco - centro) * (radios + margen_m) / radios
        ok &= Delaunay(ampliado).find_simplex(xyz[:, :2]) >= 0
    if z_min is not None:
        ok &= xyz[:, 2] >= z_min
    if z_max is not None:
        ok &= xyz[:, 2] <= z_max
    return ok


def main(argv=None):
    import pandas as pd
    from pyproj import Transformer

    from . import config

    p = argparse.ArgumentParser(prog="gemelo.nube", description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(config.RUTA_DEFECTO))
    args = p.parse_args(argv)
    cfg = config.cargar(args.config)
    fusionadas = Path(cfg["carpeta_salidas"]) / "lecturas_fusionadas.csv"
    for ruta, como in ((cfg["ruta_nube"], "corre ODM (fase 6)"), (fusionadas, "corre  python -m gemelo.fusion")):
        if not Path(ruta).exists():
            raise SystemExit(f"Falta {ruta}: {como}")

    f = pd.read_csv(fusionadas)
    f = f[f["valida_posicion"]]
    camino = f[["x_m", "y_m"]].to_numpy()
    xyz = leer(cfg["ruta_nube"])
    suelo = suelo_del_recorrido(xyz, camino)
    vol = volumen_lod1(xyz, camino, suelo)
    lon, lat = Transformer.from_crs(f["crs"].iloc[0], "EPSG:4326", always_xy=True).transform(
        vol["esquinas"][:, 0], vol["esquinas"][:, 1])
    salida = Path(cfg["carpeta_salidas"]) / "volumen_lod1.json"
    datos = {"crs": f["crs"].iloc[0], "suelo_m": round(suelo, 2),
             "esquinas_utm": np.round(vol["esquinas"], 2).tolist(),
             "esquinas_lat_lon": [[round(a, 7), round(b, 7)] for a, b in zip(lat, lon)],
             **{k: round(v, 2) for k, v in vol.items() if k != "esquinas"},
             "metodo": "orientación del camino de la caja negra; muros = picos exteriores de la nube entre "
                       "1.5 y 6 m sobre el suelo; altura = percentil 90 de la nube dentro de la planta"}
    salida.write_text(json.dumps(datos, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Puntos en la nube: {len(xyz):,}   suelo (junto al camino de la caja negra): {suelo:.2f} m")
    print(f"Volumen LOD1: {vol['largo_m']:.1f} m × {vol['ancho_m']:.1f} m en planta, altura {vol['altura_m']:.1f} m, "
          f"orientación {vol['angulo_grados']:.1f}°")
    print(f"Escrito: {salida}")


if __name__ == "__main__":
    main()
