"""Pruebas en la PC (CPython) de las conversiones del controlador DS3231."""

import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "firmware"))
import ds3231  # noqa: E402


@pytest.mark.parametrize("n", range(100))
def test_bcd_ida_y_vuelta(n):
    assert ds3231.bcd_a_int(ds3231.int_a_bcd(n)) == n


def test_bcd_valores_conocidos():
    assert ds3231.int_a_bcd(59) == 0x59 and ds3231.bcd_a_int(0x23) == 23


def test_codificar_y_decodificar_una_hora():
    regs = ds3231.codificar(2026, 11, 24, 20, 26, 47)
    assert regs == bytes([0x47, 0x26, 0x20, 2, 0x24, 0x11, 0x26])  # 24/11/2026 es martes (2)
    assert ds3231.decodificar(regs) == (2026, 11, 24, 20, 26, 47)


@pytest.mark.parametrize("fecha", ["2026-01-01", "2026-02-28", "2028-02-29", "2026-11-24", "2099-12-31"])
def test_dia_semana_coincide_con_python(fecha):
    d = dt.date.fromisoformat(fecha)
    assert ds3231.dia_semana(d.year, d.month, d.day) == d.isoweekday()


def test_decodifica_modo_12_horas():
    # 11 p. m. en modo 12 h: bit 6 = 12 h, bit 5 = PM, 0x11 = 11
    regs = bytes([0x00, 0x30, 0x40 | 0x20 | 0x11, 1, 0x01, 0x01, 0x26])
    assert ds3231.decodificar(regs)[3] == 23
    regs = bytes([0x00, 0x00, 0x40 | 0x12, 1, 0x01, 0x01, 0x26])  # 12 a. m.
    assert ds3231.decodificar(regs)[3] == 0


def test_temperatura_con_signo_y_cuartos():
    assert ds3231.temperatura_c(25, 0b01000000) == 25.25
    assert ds3231.temperatura_c(0xFF, 0b11000000) == -0.25 and ds3231.temperatura_c(0xFE, 0) == -2


def test_anio_fuera_de_rango():
    with pytest.raises(ValueError):
        ds3231.codificar(2100, 1, 1, 0, 0, 0)


class I2CFalso:
    """Simula el DS3231 en memoria para probar la clase sin hardware."""

    def __init__(self):
        self.mem = bytearray(0x13)
        self.mem[ds3231.REG_ESTADO] = ds3231.BIT_OSF  # primer uso: oscilador detenido

    def scan(self):
        return [0x57, 0x68]

    def readfrom_mem(self, direccion, reg, n):
        return bytes(self.mem[reg:reg + n])

    def writeto_mem(self, direccion, reg, datos):
        self.mem[reg:reg + len(datos)] = datos


def test_clase_ajusta_lee_y_borra_osf():
    rtc = ds3231.DS3231(I2CFalso())
    assert rtc.presente() and rtc.perdio_hora()
    rtc.ajustar(2026, 11, 24, 23, 59, 58)
    assert rtc.leer() == (2026, 11, 24, 23, 59, 58)
    assert not rtc.perdio_hora()
