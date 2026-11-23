from itertools import islice

import pytest

from cajanegra import nmea, simulado


def test_gps_simulado_produce_nmea_que_el_parser_acepta():
    lineas = list(islice(simulado.lineas_gps(segundos_sin_fix=1, pausa=0), 4))
    datos = [nmea.parsear(l) for l in lineas]
    assert all(d is not None for d in datos), lineas
    gga_sin_fix, rmc_sin_fix, gga, rmc = datos
    assert gga_sin_fix["fix"] == 0 and rmc_sin_fix["valido"] is False
    assert gga["fix"] == 1 and rmc["valido"] is True
    assert gga["lat"] == pytest.approx(simulado.LAT0, abs=0.001)
    assert gga["lon"] == pytest.approx(simulado.LON0, abs=0.001)
