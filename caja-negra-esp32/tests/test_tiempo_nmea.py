"""Fechas sin datetime y parser NMEA del firmware (mismos casos que el parser de la Pi)."""

import datetime as dt

import pytest

import nmea
import tiempo
from conftest import EJEMPLO_NMEA

LINEAS = EJEMPLO_NMEA.read_text().splitlines()
EPOCA = dt.datetime(1970, 1, 1, tzinfo=dt.timezone.utc)


@pytest.mark.parametrize("fecha", ["1970-01-01T00:00:00.000", "2000-02-29T12:34:56.789", "2026-11-25T03:04:05.006",
                                   "2028-12-31T23:59:59.999", "2099-03-01T00:00:00.000"])
def test_epoch_coincide_con_datetime(fecha):
    d = dt.datetime.fromisoformat(fecha).replace(tzinfo=dt.timezone.utc)
    ms = int((d - EPOCA).total_seconds() * 1000 + 0.5)
    assert tiempo.a_epoch_ms(d.year, d.month, d.day, d.hour, d.minute, d.second, d.microsecond // 1000) == ms
    assert tiempo.desde_epoch_ms(ms) == (d.year, d.month, d.day, d.hour, d.minute, d.second, d.microsecond // 1000)
    assert tiempo.iso(ms) == fecha + "Z"


def test_epoch_ida_y_vuelta_cada_dia_de_varios_anios():
    for dias in range(dt.date(2024, 1, 1).toordinal(), dt.date(2030, 1, 1).toordinal(), 7):
        d = dt.date.fromordinal(dias)
        assert tiempo.civil_desde_dias(tiempo.dias_desde_civil(d.year, d.month, d.day)) == (d.year, d.month, d.day)


def test_checksum_valido_e_invalido():
    assert nmea.checksum_valido(LINEAS[2])
    assert not nmea.checksum_valido(LINEAS[4])
    assert not nmea.checksum_valido("$GPGGA,1545")


def test_gga_con_fix_coordenadas_exactas_en_enteros():
    d = nmea.parsear(LINEAS[2])
    assert d["tipo"] == "GGA" and d["hora"] == (15, 45, 1, 0)
    assert d["lat_e7"] == 201426000 and d["lon_e7"] == -1011756000  # 20.1426000, −101.1756000 (W negativo)
    assert (d["fix"], d["sats"], d["hdop"], d["alt_m"]) == (1, 7, "1.20", "1915.3")


def test_coordenadas_con_cinco_decimales_de_minuto():
    # 2008.55678 N = 20 + 8.55678/60 = 20.142613 grados
    assert nmea._coord_e7("2008.55678", "N") == round((20 + 8.55678 / 60) * 1e7)
    assert nmea._coord_e7("10110.53601", "W") == -round((101 + 10.53601 / 60) * 1e7)


def test_gga_sin_fix_deja_campos_en_none():
    d = nmea.parsear(LINEAS[0])
    assert d["fix"] == 0 and d["lat_e7"] is None and d["lon_e7"] is None and d["alt_m"] is None


def test_rmc_valido_da_utc_en_ms():
    d = nmea.parsear(LINEAS[3])
    assert d["valido"] is True and tiempo.iso(d["utc_ms"]) == "2026-11-21T15:45:01.000Z"


def test_rmc_conserva_fracciones_de_segundo():
    assert tiempo.iso(nmea.parsear(LINEAS[7])["utc_ms"]) == "2026-11-21T23:59:59.500Z"


def test_rmc_sin_fix_no_valido_y_talker_gn():
    assert nmea.parsear(LINEAS[1])["valido"] is False
    assert nmea.parsear(LINEAS[6])["tipo"] == "GGA"


@pytest.mark.parametrize("i", [4, 5, 8])
def test_lineas_invalidas_o_ignoradas_dan_none(i):
    assert nmea.parsear(LINEAS[i]) is None


def test_basura_no_lanza_excepcion():
    for basura in ["", "\x00\xff", "$", "*", "$GPGGA,a,b,c*FF", "$GPRMC*00", "$GPGGA,,,,,,x,,,*" + "00"]:
        assert nmea.parsear(basura) is None
