"""Armado de filas, banderas, fuente de hora y estado del LED (mismos criterios que la caja con Pi)."""

import pytest

import tiempo
from fila import COLUMNAS, armar_fila, grados_txt, linea_csv, segundos_txt
from led import Led, elegir_estado
from reloj import SIN_HORA, Reloj

T0 = 100_000
UTC = tiempo.a_epoch_ms(2026, 11, 21, 15, 45, 1)
GPS_FIX = {"fix": 1, "lat_e7": 201426000, "lon_e7": -1011756000, "alt_m": "1915.3", "sats": 7, "hdop": "1.20",
           "t_gga": 109_800, "utc_ms": UTC, "t_rmc": 109_500}
GPS_VACIO = {"fix": 0, "lat_e7": None, "lon_e7": None, "alt_m": None, "sats": 0, "hdop": None,
             "t_gga": None, "utc_ms": None, "t_rmc": None}
DHT_OK = {"temp_c": 21.4, "hr_pct": 55.0, "t_valida": 108_000}
DHT_NUNCA = {"temp_c": None, "hr_pct": None, "t_valida": None}


def fila(gps=GPS_FIX, dht=DHT_OK, hora=(UTC + 500, "gps", True), ahora=110_000):
    return armar_fila(gps, dht, hora, ahora, T0, 7, "sesion_1001", "esp32-0.1.0")


def test_textos_numericos_sin_flotantes():
    assert grados_txt(201426000) == "20.1426000" and grados_txt(-1011756000) == "-101.1756000"
    assert grados_txt(-5) == "-0.0000005"
    assert segundos_txt(10_000) == "10.000" and segundos_txt(2049, 1) == "2.0" and segundos_txt(2050, 1) == "2.1"


def test_con_fix_fila_completa_igual_que_la_pi():
    f, con_fix, falla = fila()
    assert con_fix and not falla
    assert f["utc"] == "2026-11-21T15:45:01.500Z" and f["fuente_hora"] == "gps" and f["banderas"] == ""
    assert (f["seq"], f["t_mono_s"], f["version"]) == ("7", "10.000", "esp32-0.1.0")
    assert (f["lat"], f["lon"], f["alt_m"], f["fix"], f["sats"], f["hdop"]) == \
        ("20.1426000", "-101.1756000", "1915.3", "1", "7", "1.20")
    assert (f["temp_c"], f["hr_pct"], f["dht_edad_s"], f["espesor_mm"]) == ("21.4", "55.0", "2.0", "")
    assert linea_csv(f).count(",") == len(COLUMNAS) - 1


def test_hora_del_rtc_sin_hora_sistema():
    f, _, _ = fila(gps=GPS_VACIO, hora=(UTC, "rtc", True))
    assert f["fuente_hora"] == "rtc" and f["banderas"] == "SIN_FIX"


def test_rtc_que_perdio_la_hora_marca_hora_no_sinc():
    f, _, _ = fila(gps=GPS_VACIO, hora=(UTC, "rtc", False))
    assert f["banderas"] == "SIN_FIX;HORA_NO_SINC"


def test_reloj_interno_sin_sincronizar():
    f, _, _ = fila(gps=GPS_VACIO, hora=(SIN_HORA, "sistema", False))
    assert f["banderas"] == "SIN_FIX;HORA_SISTEMA;HORA_NO_SINC" and f["utc"].startswith("2000-01-01")


def test_gps_callado_no_repite_posicion_y_marca_falla():
    f, con_fix, falla = fila(ahora=120_000)  # última GGA hace 10 s
    assert not con_fix and falla and f["lat"] == "" and f["fix"] == "0" and f["sats"] == ""


def test_dht_sin_lectura_y_viejo():
    f, _, falla = fila(dht=DHT_NUNCA)
    assert f["banderas"] == "DHT_ERROR" and f["temp_c"] == "" and not falla  # margen al arrancar
    f, _, falla = fila(dht={"temp_c": 21.4, "hr_pct": 55.0, "t_valida": 99_000})
    assert f["dht_edad_s"] == "11.0" and "DHT_VIEJO" in f["banderas"] and falla


# --- reloj ---

class DSFalso:
    def __init__(self, hora=(2026, 11, 25, 1, 2, 3), perdio=False, falla=False):
        self.h, self.perdio, self.falla, self.ajustes = hora, perdio, falla, []

    def leer(self):
        if self.falla:
            raise OSError("I2C")
        return self.h

    def perdio_hora(self):
        return self.perdio

    def ajustar(self, *h):
        self.ajustes.append(h)
        self.h, self.perdio = h, False


def test_reloj_con_gps_usa_gps_y_ajusta_el_ds3231_una_vez_por_hora():
    ds = DSFalso(perdio=True)
    r = Reloj(ds, 0)
    assert r.rtc_perdio_hora is True
    assert r.hora(110_000, GPS_FIX) == (UTC + 500, "gps", True)
    assert ds.ajustes == [(2026, 11, 21, 15, 45, 2)]  # redondeado al segundo
    r.hora(111_000, dict(GPS_FIX, t_rmc=110_500, utc_ms=UTC + 1000))
    assert len(ds.ajustes) == 1  # no vuelve a ajustar antes de una hora


def test_reloj_sin_gps_usa_ds3231_y_avanza_con_el_monotonico():
    r = Reloj(DSFalso(hora=(2026, 11, 25, 1, 2, 3)), ahora_ms=1000)
    utc, fuente, confiable = r.hora(4500, GPS_VACIO)
    assert (tiempo.iso(utc), fuente, confiable) == ("2026-11-25T01:02:06.500Z", "rtc", True)


def test_reloj_ds3231_sin_hora_no_es_confiable_hasta_el_gps():
    r = Reloj(DSFalso(perdio=True), 0)
    assert r.hora(1000, GPS_VACIO)[1:] == ("rtc", False)
    r.hora(110_000, GPS_FIX)  # llega el GPS: ajusta el DS3231
    utc, fuente, confiable = r.hora(200_000, GPS_FIX)  # GPS ya viejo: sigue con la base del GPS
    assert (fuente, confiable) == ("rtc", True) and utc == UTC + 500 + 90_000


def test_reloj_sin_ds3231_ni_gps():
    r = Reloj(None, 0)
    assert r.hora(5000, GPS_VACIO) == (SIN_HORA + 5000, "sistema", False)
    r.hora(110_000, GPS_FIX)
    assert r.hora(115_000, GPS_VACIO) == (UTC + 500 + 5000, "sistema", True)  # sincronizado en la sesión


def test_reloj_con_ds3231_que_falla_por_i2c():
    r = Reloj(DSFalso(falla=True), 0)
    assert r.errores_rtc == 1 and r.hora(1000, GPS_VACIO) == (SIN_HORA + 1000, "rtc", False)


# --- LED ---

@pytest.mark.parametrize("con_fix, hubo_fix, falla, esperado", [
    (False, False, False, "buscando"), (False, True, False, "sin_fix"),
    (True, True, False, "fix"), (True, True, True, "error")])
def test_estado_del_led(con_fix, hubo_fix, falla, esperado):
    assert elegir_estado(con_fix, hubo_fix, falla) == esperado


class PinFalso:
    def __init__(self):
        self.v = None

    def value(self, v=None):
        if v is not None:
            self.v = v
        return self.v


def test_patrones_del_led_activo_en_bajo():
    pin = PinFalso()
    led = Led(pin)
    assert pin.v == 1  # apagado (activo en bajo)
    led.poner("buscando", 0)
    led.actualizar(100)
    assert pin.v == 0  # encendido la primera mitad
    led.actualizar(600)
    assert pin.v == 1
    led.poner("fix", 700)
    led.actualizar(5000)
    assert pin.v == 0
    led.poner("error", 0)
    assert [led.encendido(t) for t in (50, 150, 300, 500)] == [True, False, True, False]
