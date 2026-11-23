"""Carga config.yaml encima de valores por defecto."""

from pathlib import Path

import yaml

DEFECTOS = {
    "puerto_gps": "/dev/serial0",
    "baudios_gps": 9600,
    "periodo_registro_s": 1.0,
    "periodo_dht_s": 3.0,
    "dht_max_edad_s": 10.0,
    "ruta_iio_dht": "/sys/bus/iio/devices/iio:device0",
    "carpeta_datos": "datos",
    "led": {"r": 17, "g": 27, "b": 22},
}


def cargar(ruta):
    """Devuelve la configuración; una carpeta_datos relativa se toma desde la carpeta de config.yaml."""
    ruta = Path(ruta)
    cfg = dict(DEFECTOS)
    if ruta.exists():
        cfg.update(yaml.safe_load(ruta.read_text(encoding="utf-8")) or {})
    carpeta = Path(cfg["carpeta_datos"]).expanduser()
    if not carpeta.is_absolute():
        carpeta = ruta.resolve().parent / carpeta
    cfg["carpeta_datos"] = str(carpeta)
    return cfg
