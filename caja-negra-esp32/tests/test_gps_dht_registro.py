"""Lector del GPS (con UART falsa), lector del DHT22 y registro en archivos (carpeta temporal)."""

import json

import pytest

import tiempo
from conftest import EJEMPLO_NMEA
from dht_lector import LectorDHT
from fila import COLUMNAS
from gps import LectorGPS
from registro import Registro, siguiente_numero


class UARTFalsa:
    """Entrega los bytes por pedazos, como la UART real (las líneas pueden llegar partidas)."""

    def __init__(self, datos, trozo=17):
        self.datos, self.trozo = datos, trozo

    def read(self):
        if not self.datos:
            return None
        parte, self.datos = self.datos[:self.trozo], self.datos[self.trozo:]
        return parte


def test_gps_arma_estado_con_lineas_partidas():
    lineas = EJEMPLO_NMEA.read_bytes().replace(b"\r\n", b"\n").split(b"\n")
    datos = b"\r\n".join(lineas[:4]) + b"\r\n"  # sin fix, sin fix, GGA con fix, RMC válido
    g = LectorGPS(UARTFalsa(datos))
    for t in range(0, 2000, 20):
        g.actualizar(t)
    e = g.estado
    assert (e["fix"], e["sats"], e["lat_e7"], e["hdop"]) == (1, 7, 201426000, "1.20")
    assert tiempo.iso(e["utc_ms"]) == "2026-11-21T15:45:01.000Z" and e["t_rmc"] is not None
    assert g.frases == 4 and g.malas == 0


def test_gps_cuenta_checksums_malos_y_aguanta_basura():
    g = LectorGPS(UARTFalsa(b"\xff\xfe basura\n$GPGGA,154502.00,2008.5560,N,10110.5360,W,1,07,1.20,1915.3,M,,M,,*00\n"
                            + b"x" * 5000))
    for t in range(0, 20000, 20):
        g.actualizar(t)
    # malas = 2: la línea de ruido con bytes inválidos y la GGA con checksum malo
    assert g.malas == 2 and g.estado["t_gga"] is None and len(g.bufer) <= 2048


def test_dht_respeta_periodo_y_conserva_la_ultima_valida():
    respuestas = iter([(21.4, 55.0), OSError("timeout"), (99.0, 50.0), (22.0, 56.0)])

    def medir():
        r = next(respuestas)
        if isinstance(r, Exception):
            raise r
        return r

    d = LectorDHT(medir, 3000)
    d.actualizar(0)
    assert d.estado == {"temp_c": 21.4, "hr_pct": 55.0, "t_valida": 0}
    d.actualizar(1000)  # antes de 3 s no vuelve a medir
    d.actualizar(3000)  # falla: conserva la anterior
    d.actualizar(6000)  # fuera de rango (99 °C): la descarta
    assert d.estado["t_valida"] == 0 and d.fallas == 2
    d.actualizar(9000)
    assert d.estado == {"temp_c": 22.0, "hr_pct": 56.0, "t_valida": 9000}


def fila_ejemplo(seq):
    f = {c: "" for c in COLUMNAS}
    f.update(seq=str(seq), t_mono_s="%d.000" % (seq - 1), utc="2026-11-25T01:00:%02d.000Z" % seq,
             fuente_hora="rtc", fix="0", temp_c="21.4", hr_pct="55.0", dht_edad_s="1.0",
             banderas="SIN_FIX", version="esp32-0.1.0")
    return f


def test_registro_numera_desde_1001_y_sigue_el_contador(tmp_path):
    carpeta = str(tmp_path / "datos")
    r = Registro(carpeta, 1001, {"version": "esp32-0.1.0"})
    assert r.nombre == "sesion_1001"
    r.escribir(fila_ejemplo(1))
    r.cerrar(hora_cierre="2026-11-25T01:00:05.000Z")
    assert siguiente_numero(carpeta, 1001) == 1002
    (tmp_path / "datos" / "estado.json").unlink()  # si se pierde el contador, manda el CSV más alto
    assert Registro(carpeta, 1001, {}).nombre == "sesion_1002"


def test_registro_csv_y_metadatos(tmp_path):
    r = Registro(str(tmp_path), 1001, {"version": "esp32-0.1.0", "reloj": "DS3231"})
    for i in range(1, 4):
        r.escribir(fila_ejemplo(i))
    r.actualizar_metadatos(primer_fix_utc="2026-11-25T01:00:02.000Z")
    r.cerrar(hora_cierre="2026-11-25T01:00:04.000Z")
    lineas = (tmp_path / "sesion_1001.csv").read_text().splitlines()
    assert lineas[0] == ",".join(COLUMNAS) and len(lineas) == 4 and lineas[1].startswith("sesion_1001,1,")
    meta = json.loads((tmp_path / "sesion_1001.json").read_text())
    assert meta["filas"] == 3 and meta["reloj"] == "DS3231" and meta["primer_fix_utc"].endswith("02.000Z")
    assert not list(tmp_path.glob("*.tmp"))


def test_registro_nunca_escribe_encima(tmp_path):
    (tmp_path / "sesion_1001.csv").write_text("x")
    (tmp_path / "estado.json").write_text('{"ultima_sesion": 1000}')
    assert Registro(str(tmp_path), 1001, {}).nombre == "sesion_1002"
