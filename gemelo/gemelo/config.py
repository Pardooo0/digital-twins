"""Carga config.yaml encima de valores por defecto y resuelve las rutas."""

from pathlib import Path

import yaml

RUTA_DEFECTO = Path(__file__).resolve().parent.parent / "config.yaml"

DEFECTOS = {
    "proyecto": "estructura1",
    "odm_proyecto": None,  # carpeta de salida de ODM a usar (p. ej. un reproceso); None = la de `proyecto`
    "carpeta_fotos": "datos/fotos",
    "carpeta_odm": "datos/odm",
    "carpeta_cajanegra": "datos/cajanegra",
    "carpeta_salidas": "salidas",
    "sesiones": [],  # sesiones de la caja negra que pertenecen al proyecto; vacío = todas
    "crs_defecto": "EPSG:32614",
    "hdop_max": 5.0,
    "humectacion": {"hr_min_pct": 80.0, "temp_min_c": 0.0, "tam_zona_m": 5.0, "max_dt_s": 5.0},
    "espesores": {"n_puntos": 30, "semilla": 42, "altura_min_m": 1.0, "altura_max_m": 15.0, "t_inicial_mm": 6.0,
                  "anios_previos": 10.0, "dt_anios": 2.0, "t_req_mm": 3.0, "vc_min_mm_anio": 0.05,
                  "vc_max_mm_anio": 0.20, "ruido_mm": 0.05, "niveles_ruido_mm": [0.0, 0.01, 0.05, 0.10],
                  "repeticiones": 200},
    "mapa": {"mostrar_ortomosaico": True},
    "visor3d": {"max_puntos": 250_000, "margen_m": 8.0, "bajo_suelo_m": 1.5, "sobre_suelo_m": 15.0},
}
SECCIONES = ("humectacion", "espesores", "mapa", "visor3d")
CARPETAS = ("carpeta_fotos", "carpeta_odm", "carpeta_cajanegra", "carpeta_salidas")


def cargar(ruta=RUTA_DEFECTO):
    """Devuelve la configuración con rutas absolutas (relativas a la carpeta de config.yaml)."""
    ruta = Path(ruta)
    leido = (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.exists() else {}
    cfg = {**DEFECTOS, **leido}
    for seccion in SECCIONES:
        cfg[seccion] = {**DEFECTOS[seccion], **(leido.get(seccion) or {})}
    base = ruta.resolve().parent
    for clave in CARPETAS:
        carpeta = Path(cfg[clave]).expanduser()
        cfg[clave] = carpeta if carpeta.is_absolute() else base / carpeta
    odm = cfg["carpeta_odm"] / (cfg.get("odm_proyecto") or cfg["proyecto"])
    cfg["ruta_dsm"] = odm / "odm_dem" / "dsm.tif"
    cfg["ruta_ortomosaico"] = odm / "odm_orthophoto" / "odm_orthophoto.tif"
    cfg["ruta_nube"] = odm / "odm_georeferencing" / "odm_georeferenced_model.laz"
    cfg["ruta_modelo"] = odm / "odm_texturing" / "odm_textured_model_geo.obj"
    cfg["ruta_coords"] = odm / "odm_georeferencing" / "coords.txt"  # desplazamiento UTM del modelo
    return cfg
