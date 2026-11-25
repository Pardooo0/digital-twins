"""Las pruebas importan los módulos de firmware/ (MicroPython) como módulos normales de CPython."""

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(RAIZ / "firmware"))
sys.path.insert(0, str(RAIZ.parent / "caja-negra" / "tests"))  # verificar_sesion.py de la caja con Pi
sys.path.insert(0, str(RAIZ.parent / "caja-negra"))
EJEMPLO_NMEA = RAIZ.parent / "caja-negra" / "tests" / "datos" / "ejemplo.nmea"
