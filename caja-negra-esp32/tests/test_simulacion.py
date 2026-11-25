"""El bucle completo de la caja negra con hardware simulado en la PC (equivale al --simular de la Pi).

Se genera una sesión de 2 minutos: el GPS habla sin fix y luego con fix, el DHT22 falla a veces y el DS3231
perdió la hora al inicio. El CSV resultante se revisa con verificar_sesion.py de la caja con Pi: el gemelo
digital debe poder leer igual los datos del ESP32.
"""

import json

import bucle
import config
import nmea
from verificar_sesion import verificar_csv


def con_checksum(cuerpo):
    return "$%s*%02X\r\n" % (cuerpo, nmea.calcular_checksum(cuerpo))


class GPSSimulado:
    """UART falsa: entrega GGA + RMC una vez por segundo; con fix a partir del segundo 30."""

    def __init__(self, reloj):
        self.reloj, self.ultimo_s = reloj, -1

    def read(self):
        s = self.reloj.t // 1000
        if s == self.ultimo_s:
            return None
        self.ultimo_s = s
        h, m, seg = 15, 45 + s // 60, s % 60
        hora = "%02d%02d%02d.00" % (h, m, seg)
        if s < 30:
            return (con_checksum("GPGGA,%s,,,,,0,00,99.99,,,,,," % hora) +
                    con_checksum("GPRMC,%s,V,,,,,,,251126,,,N" % hora)).encode()
        return (con_checksum("GPGGA,%s,2008.5560,N,10110.5360,W,1,07,1.20,1915.3,M,-9.1,M,," % hora) +
                con_checksum("GPRMC,%s,A,2008.5560,N,10110.5360,W,0.12,,251126,,,A" % hora)).encode()


class RelojSimulado:
    def __init__(self):
        self.t = 0

    def ms(self):
        return self.t

    def dormir(self, ms):
        self.t += ms


class DSSimulado:
    def __init__(self):
        self.h, self.perdio, self.ajustes = (2000, 1, 1, 0, 0, 0), True, []

    def leer(self):
        return self.h

    def perdio_hora(self):
        return self.perdio

    def ajustar(self, *h):
        self.h, self.perdio = h, False
        self.ajustes.append(h)


class HardwareSimulado:
    simulado = True
    led_pin = None
    boton = None

    def __init__(self, carpeta):
        self._reloj = RelojSimulado()
        self.ms, self.dormir = self._reloj.ms, self._reloj.dormir
        self.uart = GPSSimulado(self._reloj)
        self.ds3231 = DSSimulado()
        self.carpeta_datos = carpeta
        self._n = 0

    def medir_dht(self):
        self._n += 1
        if self._n % 5 == 0:
            raise OSError("ETIMEDOUT")  # falla de vez en cuando, como el real
        return 24.0 + self._n * 0.1, 55.0

    def alimentar_watchdog(self):
        pass

    def recolectar(self):
        pass


def test_sesion_simulada_completa_pasa_el_verificador_de_la_pi(tmp_path):
    hw = HardwareSimulado(str(tmp_path / "datos"))
    reg = bucle.ejecutar(hw, config, max_filas=120)
    errores, avisos, filas = verificar_csv(reg.ruta_csv)
    assert errores == [] and filas == 120
    assert all("sin cerrar" not in a for a in avisos)

    lineas = [l.split(",") for l in open(reg.ruta_csv).read().splitlines()[1:]]
    col = {c: i for i, c in enumerate(lineas[0] and __import__("fila").COLUMNAS)}
    primeras, ultimas = lineas[0], lineas[-1]
    # al inicio: sin fix y el DS3231 sin hora → hora del RTC no confiable
    assert primeras[col["fuente_hora"]] == "rtc" and "HORA_NO_SINC" in primeras[col["banderas"]]
    # al final: con fix, hora del GPS, posición exacta
    assert ultimas[col["fuente_hora"]] == "gps" and ultimas[col["lat"]] == "20.1426000"
    assert ultimas[col["utc"]].startswith("2026-11-25T15:46:")
    assert hw.ds3231.ajustes and hw.ds3231.ajustes[0][:3] == (2026, 11, 25)  # el GPS ajustó el reloj

    meta = json.loads(open(reg.ruta_json).read())
    assert meta["sesion"] == "sesion_1001" and meta["filas"] == 120 and meta["simulado"] is True
    assert meta["rtc_perdio_hora"] is True and meta["primer_fix_utc"].startswith("2026-11-25T15:45:30")
    assert meta["dht_fallas"] > 0 and meta["gps_frases"] >= 240


def test_boton_cierra_la_sesion(tmp_path):
    hw = HardwareSimulado(str(tmp_path))

    class Boton:
        def value(self):
            return 0 if hw.ms() >= 10_000 else 1  # se presiona a los 10 s

    hw.boton = Boton()
    reg = bucle.ejecutar(hw, config)
    meta = json.loads(open(reg.ruta_json).read())
    assert meta["hora_cierre"] is not None and 10 <= meta["filas"] <= 12
