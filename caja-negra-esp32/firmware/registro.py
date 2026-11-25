"""Registro en la microSD: un CSV por encendido (sesion_NNNN.csv) + metadatos (sesion_NNNN.json).

Cada fila se graba con flush() + os.sync(): un corte de energía pierde como máximo la última fila.
Corre igual en MicroPython y en la PC (solo usa open, os y json); en Windows no existe os.sync y basta flush().
"""

import json
import os

import fila as filas

_sync = getattr(os, "sync", None)


def _existe(ruta):
    try:
        os.stat(ruta)
        return True
    except OSError:
        return False


def _numero_de(nombre):
    """'sesion_1003.csv' → 1003; None si no es un archivo de sesión."""
    if nombre.startswith("sesion_") and nombre.endswith(".csv") and nombre[7:-4].isdigit():
        return int(nombre[7:-4])
    return None


def siguiente_numero(carpeta, primera):
    """Mayor entre estado.json y los CSV existentes, +1; nunca menor que `primera`."""
    ultimo = primera - 1
    try:
        with open(carpeta + "/estado.json") as f:
            ultimo = max(ultimo, int(json.loads(f.read())["ultima_sesion"]))
    except (OSError, ValueError, KeyError, TypeError):
        pass
    for nombre in os.listdir(carpeta):
        n = _numero_de(nombre)
        if n is not None:
            ultimo = max(ultimo, n)
    return ultimo + 1


def escribir_json(ruta, datos):
    """Escribe a un temporal y lo renombra: un corte deja el archivo viejo o el nuevo, no uno a medias."""
    temporal = ruta + ".tmp"
    with open(temporal, "w") as f:
        f.write(json.dumps(datos))
        f.flush()
    if _sync:
        _sync()
    if _existe(ruta):
        os.remove(ruta)
    os.rename(temporal, ruta)
    if _sync:
        _sync()


class Registro:
    def __init__(self, carpeta, primera_sesion, metadatos):
        if not _existe(carpeta):
            os.mkdir(carpeta)
        self.carpeta = carpeta
        numero = siguiente_numero(carpeta, primera_sesion)
        escribir_json(carpeta + "/estado.json", {"ultima_sesion": numero})
        self.nombre = "sesion_%04d" % numero
        self.ruta_csv = "%s/%s.csv" % (carpeta, self.nombre)
        self.ruta_json = "%s/%s.json" % (carpeta, self.nombre)
        if _existe(self.ruta_csv):
            raise OSError("ya existe " + self.ruta_csv)  # nunca escribir encima de una sesión
        self.metadatos = {"sesion": self.nombre, "primer_fix_utc": None, "hora_cierre": None, "filas": None}
        self.metadatos.update(metadatos)
        escribir_json(self.ruta_json, self.metadatos)
        self.filas = 0
        self._archivo = open(self.ruta_csv, "w")
        self._grabar(filas.encabezado_csv())

    def _grabar(self, texto):
        self._archivo.write(texto)
        self._archivo.flush()
        if _sync:
            _sync()

    def escribir(self, fila):
        """Graba una fila (dict columna → texto) y la fuerza a la microSD."""
        fila["sesion"] = self.nombre
        self._grabar(filas.linea_csv(fila))
        self.filas += 1

    def actualizar_metadatos(self, **campos):
        self.metadatos.update(campos)
        escribir_json(self.ruta_json, self.metadatos)

    def cerrar(self, **campos):
        self._archivo.close()
        campos["filas"] = self.filas
        self.actualizar_metadatos(**campos)
