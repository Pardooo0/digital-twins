import csv
import json
import os

from cajanegra import registro
from cajanegra.registro import COLUMNAS, Registro


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def test_columnas_respetan_el_contrato():
    assert COLUMNAS == ["sesion", "seq", "t_mono_s", "utc", "fuente_hora", "lat", "lon", "alt_m",
                        "fix", "sats", "hdop", "temp_c", "hr_pct", "dht_edad_s", "espesor_mm",
                        "banderas", "version"]


def test_primera_sesion_crea_csv_con_encabezado(tmp_path):
    r = Registro(tmp_path, {"version": "x"})
    assert r.nombre == "sesion_0001"
    r.cerrar()
    primera = (tmp_path / "sesion_0001.csv").read_text(encoding="utf-8").splitlines()[0]
    assert primera == ",".join(COLUMNAS)
    assert json.loads((tmp_path / "estado.json").read_text())["ultima_sesion"] == 1


def test_cada_arranque_abre_sesion_nueva(tmp_path):
    Registro(tmp_path, {}).cerrar()
    assert Registro(tmp_path, {}).nombre == "sesion_0002"


def test_no_sobrescribe_si_se_pierde_estado_json(tmp_path):
    (tmp_path / "sesion_0003.csv").write_text("algo")
    (tmp_path / "estado.json").write_text("{corrupto")
    assert Registro(tmp_path, {}).nombre == "sesion_0004"
    assert (tmp_path / "sesion_0003.csv").read_text() == "algo"


def test_filas_quedan_en_disco_sin_cerrar_y_con_fsync(tmp_path, monkeypatch):
    llamadas = []
    fsync_real = os.fsync
    monkeypatch.setattr(registro.os, "fsync", lambda fd: (llamadas.append(fd), fsync_real(fd)))
    r = Registro(tmp_path, {})
    antes = len(llamadas)
    r.escribir({"seq": 1, "lat": 20.1, "banderas": ""})
    r.escribir({"seq": 2, "lat": None, "banderas": "SIN_FIX"})
    assert len(llamadas) - antes == 2  # un fsync por fila
    filas = leer_csv(r.ruta_csv)  # se lee sin cerrar: simula un corte de energía
    assert [f["seq"] for f in filas] == ["1", "2"]
    assert filas[0]["sesion"] == "sesion_0001"
    assert filas[1]["lat"] == ""  # None → vacío
    assert filas[1]["banderas"] == "SIN_FIX"


def test_metadatos_se_escriben_al_abrir_y_se_actualizan(tmp_path):
    r = Registro(tmp_path, {"version": "0.1.0", "config": {"a": 1}})
    meta = json.loads(r.ruta_json.read_text(encoding="utf-8"))
    assert meta["version"] == "0.1.0" and meta["sesion"] == "sesion_0001"
    assert meta["hora_cierre"] is None
    r.actualizar_metadatos(primer_fix_utc="2026-11-21T15:45:01Z")
    r.cerrar(hora_cierre="2026-11-21T16:00:00Z", filas=10)
    meta = json.loads(r.ruta_json.read_text(encoding="utf-8"))
    assert meta["primer_fix_utc"] == "2026-11-21T15:45:01Z"
    assert meta["hora_cierre"] == "2026-11-21T16:00:00Z"
    assert meta["filas"] == 10
    assert meta["config"] == {"a": 1}
