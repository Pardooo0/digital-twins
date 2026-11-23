from datetime import datetime, time, timezone
from pathlib import Path

import pytest

from cajanegra import nmea

LINEAS = (Path(__file__).parent / "datos" / "ejemplo.nmea").read_text().splitlines()


def test_checksum_valido_e_invalido():
    assert nmea.checksum_valido(LINEAS[2])
    assert not nmea.checksum_valido(LINEAS[4])  # *00 a propósito
    assert not nmea.checksum_valido("$GPGGA,1545")  # sin checksum


def test_gga_con_fix_convierte_coordenadas():
    d = nmea.parsear(LINEAS[2])
    assert d["tipo"] == "GGA"
    assert d["hora"] == time(15, 45, 1)
    assert d["lat"] == pytest.approx(20 + 8.556 / 60)
    assert d["lon"] == pytest.approx(-(101 + 10.536 / 60))  # W es negativo
    assert d["fix"] == 1
    assert d["sats"] == 7
    assert d["hdop"] == pytest.approx(1.2)
    assert d["alt_m"] == pytest.approx(1915.3)


def test_gga_sin_fix_deja_campos_vacios_en_none():
    d = nmea.parsear(LINEAS[0])
    assert d["fix"] == 0
    assert d["lat"] is None and d["lon"] is None and d["alt_m"] is None


def test_rmc_valido_da_fecha_y_hora_utc():
    d = nmea.parsear(LINEAS[3])
    assert d["tipo"] == "RMC"
    assert d["valido"] is True
    assert d["utc"] == datetime(2026, 11, 21, 15, 45, 1, tzinfo=timezone.utc)


def test_rmc_conserva_fracciones_de_segundo():
    d = nmea.parsear(LINEAS[7])
    assert d["utc"] == datetime(2026, 11, 21, 23, 59, 59, 500000, tzinfo=timezone.utc)


def test_rmc_sin_fix_se_marca_no_valido():
    assert nmea.parsear(LINEAS[1])["valido"] is False


def test_acepta_talker_gn():
    assert nmea.parsear(LINEAS[6])["tipo"] == "GGA"


@pytest.mark.parametrize("i", [4, 5, 8])  # checksum malo, línea cortada, tipo no soportado
def test_lineas_invalidas_o_ignoradas_dan_none(i):
    assert nmea.parsear(LINEAS[i]) is None


def test_basura_no_lanza_excepcion():
    for basura in ["", "\x00\xff", "$", "*", "$GPGGA,a,b,c*FF", "$GPRMC*" + "0" * 2]:
        assert nmea.parsear(basura) is None
