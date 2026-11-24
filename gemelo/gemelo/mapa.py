"""Mapa web del gemelo (folium): ortomosaico de ODM + lecturas de la caja negra + puntos de espesor.

Capas (se encienden y apagan en el control de capas):
  - Ortomosaico de ODM (si existe) y, como referencia, satélite de Esri y OpenStreetMap.
  - Temperatura, humedad relativa y humectación (ISO 9223) de cada lectura válida.
  - Puntos de espesor sintéticos coloreados por vida remanente (VR).

Uso: python -m gemelo.mapa [--config config.yaml]
Necesita salidas/lecturas_fusionadas.csv (gemelo.fusion); usa salidas/espesores_por_punto.csv si existe.
Escribe salidas/mapa.html.
"""

import argparse
import base64
import io
from pathlib import Path

import numpy as np
import pandas as pd

from . import config

ESRI = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}"
MAX_PIXELES_ORTO = 2500  # lado mayor del ortomosaico incrustado en el HTML


def ortomosaico_png(ruta, max_px=MAX_PIXELES_ORTO):
    """GeoTIFF de ODM → (PNG en base64, límites [[sur, oeste], [norte, este]] en WGS84)."""
    import rasterio
    from PIL import Image
    from rasterio.warp import Resampling, calculate_default_transform, reproject

    with rasterio.open(ruta) as src:
        escala = max(src.width, src.height) / max_px
        ancho, alto = max(1, int(src.width / max(escala, 1))), max(1, int(src.height / max(escala, 1)))
        trans, w, h = calculate_default_transform(src.crs, "EPSG:4326", src.width, src.height, *src.bounds,
                                                  dst_width=ancho, dst_height=alto)
        bandas = min(src.count, 4)
        destino = np.zeros((bandas, h, w), dtype=np.uint8)
        for b in range(bandas):
            reproject(rasterio.band(src, b + 1), destino[b], src_transform=src.transform, src_crs=src.crs,
                      dst_transform=trans, dst_crs="EPSG:4326", resampling=Resampling.bilinear)
    modo = {1: "L", 3: "RGB", 4: "RGBA"}.get(bandas, "RGB")
    img = Image.fromarray(np.moveaxis(destino[:3 if modo == "RGB" else bandas], 0, -1).squeeze(), modo)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    oeste, norte = trans * (0, 0)
    este, sur = trans * (w, h)
    return base64.b64encode(buf.getvalue()).decode(), [[sur, oeste], [norte, este]]


def lecturas_para_mapa(ruta_fusionadas, cada_s=2):
    """Lecturas con posición y ambiente válidos, una cada `cada_s` filas para que el HTML no pese."""
    df = pd.read_csv(ruta_fusionadas)
    df = df[df["valida_posicion"] & df["valida_ambiente"]].copy()
    df["humedo"] = (df["hr_pct"] > 80.0) & (df["temp_c"] > 0.0)
    return df.iloc[::max(1, cada_s)]


def capa_puntos(df, columna, mapa_color, nombre, formato, unidad, mostrar=False):
    import folium

    capa = folium.FeatureGroup(name=nombre, show=mostrar)
    for _, f in df.iterrows():
        folium.CircleMarker(
            [f["lat"], f["lon"]], radius=4, weight=0, fill=True, fill_opacity=0.85,
            fill_color=mapa_color(f[columna]),
            tooltip=f"{nombre}: {format(f[columna], formato)} {unidad}<br>{str(f['utc'])[11:19]} UTC",
        ).add_to(capa)
    return capa


def construir(cfg):
    import folium
    from branca.colormap import LinearColormap
    from pyproj import Transformer

    salidas = Path(cfg["carpeta_salidas"])
    df = lecturas_para_mapa(salidas / "lecturas_fusionadas.csv")
    centro = [df["lat"].mean(), df["lon"].mean()]
    m = folium.Map(location=centro, zoom_start=19, max_zoom=23, tiles=None, control_scale=True)
    folium.TileLayer("OpenStreetMap", name="OpenStreetMap", max_zoom=23, max_native_zoom=19).add_to(m)
    # Esri no tiene nivel 19 en la zona del proyecto: se amplía a partir del 18.
    folium.TileLayer(ESRI, name="Satélite (Esri)", attr="Esri World Imagery", max_zoom=23,
                     max_native_zoom=18).add_to(m)

    if Path(cfg["ruta_ortomosaico"]).exists():
        png, limites = ortomosaico_png(cfg["ruta_ortomosaico"])
        folium.raster_layers.ImageOverlay(f"data:image/png;base64,{png}", bounds=limites,
                                          name="Ortomosaico (ODM)", opacity=1.0,
                                          show=bool(cfg["mapa"]["mostrar_ortomosaico"])).add_to(m)

    t = LinearColormap(["#2c7bb6", "#ffffbf", "#d7191c"], vmin=df["temp_c"].min(), vmax=df["temp_c"].max(),
                       caption="Temperatura (°C)")
    h = LinearColormap(["#f6e8c3", "#5ab4ac", "#01665e"], vmin=df["hr_pct"].min(), vmax=df["hr_pct"].max(),
                       caption="Humedad relativa (%)")
    capa_puntos(df, "temp_c", t, "Temperatura", ".1f", "°C", mostrar=True).add_to(m)
    capa_puntos(df, "hr_pct", h, "Humedad relativa", ".1f", "%").add_to(m)
    capa_puntos(df.assign(humedo_n=df["humedo"].astype(int)), "humedo_n",
                lambda v: "#08519c" if v else "#bdbdbd", "Humectación (HR > 80 % y T > 0 °C)", "d",
                "(1 = húmedo)").add_to(m)
    t.add_to(m)
    h.add_to(m)

    ruta_vol = salidas / "volumen_lod1.json"
    if ruta_vol.exists():  # planta del volumen simplificado (gemelo.nube)
        import json
        vol = json.loads(ruta_vol.read_text(encoding="utf-8"))
        folium.Polygon(vol["esquinas_lat_lon"], color="#08306b", weight=3, fill=True, fill_opacity=0.08,
                       name="Planta del edificio (LOD1)",
                       tooltip=f"Planta LOD1: {vol['largo_m']:.1f} × {vol['ancho_m']:.1f} m, altura "
                               f"{vol['altura_m']:.1f} m, orientación {vol['angulo_grados']:.0f}°").add_to(m)

    ruta_esp = salidas / "espesores_por_punto.csv"
    if ruta_esp.exists():
        e = pd.read_csv(ruta_esp)
        lon, lat = Transformer.from_crs(df["crs"].iloc[0], "EPSG:4326", always_xy=True).transform(
            e["x_m"].to_numpy(), e["y_m"].to_numpy())
        e["lat"], e["lon"] = lat, lon
        vr = LinearColormap(["#d7191c", "#fdae61", "#1a9641"], vmin=float(e["vr_anios"].min()),
                            vmax=float(e["vr_anios"].max()), caption="Vida remanente (años, sintética)")
        capa = folium.FeatureGroup(name="Espesores sintéticos (VR)", show=True)
        for _, f in e.iterrows():
            folium.RegularPolygonMarker(
                [f["lat"], f["lon"]], number_of_sides=4, radius=7, weight=1, color="#000",
                fill_color=vr(f["vr_anios"]) if pd.notna(f["vr_anios"]) else "#777", fill_opacity=0.95,
                tooltip=(f"Punto {int(f['punto'])} (z = {f['z_m']:.1f} m)<br>t_ant {f['t_ant_mm']:.2f} mm → "
                         f"t_act {f['t_act_mm']:.2f} mm<br>VC {f['vc_mm_anio']:.3f} mm/año "
                         f"(real {f['vc_real_mm_anio']:.3f})<br>VR {f['vr_anios']:.1f} años "
                         f"(real {f['vr_real_anios']:.1f})"),
            ).add_to(capa)
        capa.add_to(m)
        vr.add_to(m)

    folium.LayerControl(collapsed=False).add_to(m)
    m.fit_bounds([[df["lat"].min(), df["lon"].min()], [df["lat"].max(), df["lon"].max()]], padding=(30, 30))
    return m


def main(argv=None):
    p = argparse.ArgumentParser(prog="gemelo.mapa", description=__doc__.splitlines()[0])
    p.add_argument("--config", default=str(config.RUTA_DEFECTO))
    args = p.parse_args(argv)
    cfg = config.cargar(args.config)
    if not (Path(cfg["carpeta_salidas"]) / "lecturas_fusionadas.csv").exists():
        raise SystemExit("Falta salidas/lecturas_fusionadas.csv: corre primero  python -m gemelo.fusion")
    salida = Path(cfg["carpeta_salidas"]) / "mapa.html"
    construir(cfg).save(str(salida))
    print(f"Escrito: {salida}" + ("" if Path(cfg["ruta_ortomosaico"]).exists() else "  (sin ortomosaico de ODM)"))


if __name__ == "__main__":
    main()
