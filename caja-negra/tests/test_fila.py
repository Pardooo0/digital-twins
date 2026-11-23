from datetime import datetime, timezone

import pytest

from cajanegra.__main__ import armar_fila
from cajanegra.led import elegir_estado

T0 = 100.0
SISTEMA = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
CFG = {"dht_max_edad_s": 10.0}
GPS_FIX = {"fix": 1, "lat": 20.1426, "lon": -101.1756, "alt_m": 1915.3, "sats": 7, "hdop": 1.2,
           "t_gga": 109.8, "utc": datetime(2026, 11, 21, 15, 45, 1, tzinfo=timezone.utc), "t_rmc": 109.5}
GPS_VACIO = {"fix": 0, "lat": None, "lon": None, "alt_m": None, "sats": 0, "hdop": None,
             "t_gga": None, "utc": None, "t_rmc": None}
DHT_OK = {"temp_c": 21.4, "hr_pct": 55.0, "t_valida": 108.0}
DHT_NUNCA = {"temp_c": None, "hr_pct": None, "t_valida": None}


def fila(gps=GPS_FIX, dht=DHT_OK, ahora=110.0):
    return armar_fila(gps, dht, ahora, SISTEMA, T0, 7, CFG, "0.1.0")


def test_con_fix_usa_hora_gps_adelantada_al_instante_de_la_fila():
    f, con_fix, falla = fila()
    assert con_fix and not falla
    assert f["utc"] == "2026-11-21T15:45:01.500Z"  # RMC de hace 0.5 s
    assert f["fuente_hora"] == "gps"
    assert f["banderas"] == ""
    assert (f["seq"], f["t_mono_s"], f["version"]) == (7, 10.0, "0.1.0")
    assert (f["lat"], f["lon"], f["fix"], f["sats"], f["hdop"]) == (20.1426, -101.1756, 1, 7, 1.2)
    assert (f["temp_c"], f["hr_pct"], f["dht_edad_s"]) == (21.4, 55.0, 2.0)
    assert f["espesor_mm"] is None


def test_sin_gps_usa_hora_del_sistema_y_marca_banderas():
    f, con_fix, _ = fila(gps=GPS_VACIO)
    assert not con_fix
    assert f["utc"] == "2026-01-01T00:00:00.000Z"
    assert f["fuente_hora"] == "sistema"
    assert f["banderas"] == "SIN_FIX;HORA_SISTEMA"
    assert f["lat"] is None and f["lon"] is None and f["fix"] == 0


def test_reloj_sin_sincronizar_marca_hora_no_sinc():
    f, _, _ = armar_fila(GPS_VACIO, DHT_OK, 110.0, SISTEMA, T0, 7, CFG, "0.2.0", reloj_sinc=False)
    assert f["fuente_hora"] == "sistema"
    assert f["banderas"] == "SIN_FIX;HORA_SISTEMA;HORA_NO_SINC"


def test_con_hora_gps_no_importa_el_reloj_del_sistema():
    f, _, _ = armar_fila(GPS_FIX, DHT_OK, 110.0, SISTEMA, T0, 7, CFG, "0.2.0", reloj_sinc=False)
    assert f["fuente_hora"] == "gps" and f["banderas"] == ""


def test_gps_que_deja_de_hablar_no_repite_la_ultima_posicion():
    f, con_fix, falla = fila(ahora=120.0)  # última GGA hace 10 s
    assert not con_fix and falla
    assert f["lat"] is None and f["fix"] == 0
    assert "SIN_FIX" in f["banderas"] and "HORA_SISTEMA" in f["banderas"]


def test_dht_sin_lectura_valida_marca_error_y_deja_vacio():
    f, _, falla = fila(dht=DHT_NUNCA)
    assert f["banderas"] == "DHT_ERROR"
    assert f["temp_c"] is None and f["dht_edad_s"] is None
    assert falla is False  # al arrancar hay margen de dht_max_edad_s antes de encender el rojo


def test_dht_viejo_conserva_ultimo_valor_y_marca_bandera():
    f, _, falla = fila(dht={"temp_c": 21.4, "hr_pct": 55.0, "t_valida": 99.0}, ahora=110.0)
    assert f["temp_c"] == 21.4 and f["dht_edad_s"] == 11.0
    assert "DHT_VIEJO" in f["banderas"]
    assert falla


@pytest.mark.parametrize("con_fix, hubo_fix, falla, esperado", [
    (False, False, False, "buscando"),
    (False, True, False, "sin_fix"),
    (True, True, False, "fix"),
    (True, True, True, "error"),
])
def test_estado_del_led(con_fix, hubo_fix, falla, esperado):
    assert elegir_estado(con_fix, hubo_fix, falla) == esperado
