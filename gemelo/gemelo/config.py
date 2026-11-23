"""Carga config.yaml encima de valores por defecto y resuelve las rutas."""

from pathlib import Path

import yaml

RUTA_DEFECTO = Path(__file__).resolve().parent.parent / "config.yaml"

DEFECTOS = {
    "proyecto": "estructura1",
    "carpeta_fotos": "datos/fotos",
    "carpeta_odm": "datos/odm",
    "carpeta_cajanegra": "datos/cajanegra",
    "carpeta_salidas": "salidas",
    "crs_defecto": "EPSG:32614",
    "hdop_max": 5.0,
    "humectacion": {"hr_min_pct": 80.0, "temp_min_c": 0.0, "tam_zona_m": 5.0, "max_dt_s": 5.0},
}
CARPETAS = ("carpeta_fotos", "carpeta_odm", "carpeta_cajanegra", "carpeta_salidas")


def cargar(ruta=RUTA_DEFECTO):
    """Devuelve la configuración con rutas absolutas (relativas a la carpeta de config.yaml)."""
    ruta = Path(ruta)
    leido = (yaml.safe_load(ruta.read_text(encoding="utf-8")) or {}) if ruta.exists() else {}
    cfg = {**DEFECTOS, **leido}
    cfg["humectacion"] = {**DEFECTOS["humectacion"], **(leido.get("humectacion") or {})}
    base = ruta.resolve().parent
    for clave in CARPETAS:
        carpeta = Path(cfg[clave]).expanduser()
        cfg[clave] = carpeta if carpeta.is_absolute() else base / carpeta
    odm = cfg["carpeta_odm"] / cfg["proyecto"]
    cfg["ruta_dsm"] = odm / "odm_dem" / "dsm.tif"
    cfg["ruta_ortomosaico"] = odm / "odm_orthophoto" / "odm_orthophoto.tif"
    return cfg
