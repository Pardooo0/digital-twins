"""Registro en CSV: un archivo por encendido, fsync por fila y metadatos en JSON."""

import csv
import json
import os
import re
from pathlib import Path

# Contrato de datos (CLAUDE.md, sección 7). El gemelo depende de este orden.
COLUMNAS = ["sesion", "seq", "t_mono_s", "utc", "fuente_hora", "lat", "lon", "alt_m",
            "fix", "sats", "hdop", "temp_c", "hr_pct", "dht_edad_s", "espesor_mm",
            "banderas", "version"]


class Registro:
    def __init__(self, carpeta, metadatos):
        self.carpeta = Path(carpeta)
        self.carpeta.mkdir(parents=True, exist_ok=True)
        numero = _siguiente_numero(self.carpeta)
        _escribir_json(self.carpeta / "estado.json", {"ultima_sesion": numero})
        self.nombre = f"sesion_{numero:04d}"
        self.ruta_csv = self.carpeta / f"{self.nombre}.csv"
        self.ruta_json = self.carpeta / f"{self.nombre}.json"
        self.metadatos = {"sesion": self.nombre, "primer_fix_utc": None, "hora_cierre": None, **metadatos}
        _escribir_json(self.ruta_json, self.metadatos)
        # "x": nunca abrir encima de una sesión existente
        self._archivo = open(self.ruta_csv, "x", newline="", encoding="utf-8")
        self._csv = csv.DictWriter(self._archivo, fieldnames=COLUMNAS, extrasaction="ignore")
        self._csv.writeheader()
        self._sincronizar()

    def escribir(self, fila):
        """Graba una fila y la fuerza a la microSD: un corte pierde como máximo esta fila."""
        self._csv.writerow({**fila, "sesion": self.nombre})
        self._sincronizar()

    def actualizar_metadatos(self, **campos):
        self.metadatos.update(campos)
        _escribir_json(self.ruta_json, self.metadatos)

    def cerrar(self, **campos):
        self._archivo.close()
        self.actualizar_metadatos(**campos)

    def _sincronizar(self):
        self._archivo.flush()
        os.fsync(self._archivo.fileno())


def _siguiente_numero(carpeta):
    """Mayor entre el contador de estado.json y los CSV existentes, +1 (por si estado.json se pierde)."""
    try:
        ultimo = int(json.loads((carpeta / "estado.json").read_text())["ultima_sesion"])
    except (OSError, ValueError, KeyError, TypeError):
        ultimo = 0
    for ruta in carpeta.glob("sesion_*.csv"):
        m = re.fullmatch(r"sesion_(\d+)\.csv", ruta.name)
        if m:
            ultimo = max(ultimo, int(m.group(1)))
    return ultimo + 1


def _escribir_json(ruta, datos):
    """Escritura atómica: un corte deja el archivo viejo o el nuevo, nunca uno a medias."""
    temporal = ruta.with_suffix(".tmp")
    with open(temporal, "w", encoding="utf-8") as f:
        json.dump(datos, f, ensure_ascii=False, indent=2, default=str)
        f.flush()
        os.fsync(f.fileno())
    os.replace(temporal, ruta)
