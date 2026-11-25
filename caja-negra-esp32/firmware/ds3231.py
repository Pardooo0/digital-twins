"""Controlador mínimo del reloj de tiempo real DS3231 (I²C, dirección 0x68), para MicroPython.

El DS3231 guarda la hora en BCD (registros 0x00–0x06) y sigue contando con su pila aunque se apague la caja.
Su bandera OSF (bit 7 del registro de estado 0x0F) indica que el oscilador se detuvo (pila agotada o primer uso):
en ese caso la hora no es confiable y las filas se marcan HORA_NO_SINC.

Las funciones de conversión no usan hardware: corren igual en la PC (CPython) para probarlas con pytest.
La hora se guarda siempre en UTC y en formato de 24 h.
"""

DIRECCION = 0x68
REG_HORA = 0x00
REG_ESTADO = 0x0F
REG_TEMP = 0x11
BIT_OSF = 0x80


def bcd_a_int(b):
    return (b >> 4) * 10 + (b & 0x0F)


def int_a_bcd(n):
    return ((n // 10) << 4) | (n % 10)


def dia_semana(anio, mes, dia):
    """1 = lunes … 7 = domingo (Zeller); el DS3231 solo lo guarda, no lo usa para calcular."""
    if mes < 3:
        mes += 12
        anio -= 1
    k, j = anio % 100, anio // 100
    h = (dia + 13 * (mes + 1) // 5 + k + k // 4 + j // 4 + 5 * j) % 7  # 0 = sábado
    return (h + 5) % 7 + 1


def decodificar(regs):
    """7 bytes de los registros 0x00–0x06 → (año, mes, día, hora, minuto, segundo)."""
    segundo = bcd_a_int(regs[0] & 0x7F)
    minuto = bcd_a_int(regs[1] & 0x7F)
    if regs[2] & 0x40:  # modo 12 h (no lo usamos, pero se interpreta por si el módulo venía así)
        hora = bcd_a_int(regs[2] & 0x1F) % 12 + (12 if regs[2] & 0x20 else 0)
    else:
        hora = bcd_a_int(regs[2] & 0x3F)
    dia = bcd_a_int(regs[4] & 0x3F)
    mes = bcd_a_int(regs[5] & 0x1F)
    anio = 2000 + bcd_a_int(regs[6]) + (100 if regs[5] & 0x80 else 0)
    return (anio, mes, dia, hora, minuto, segundo)


def codificar(anio, mes, dia, hora, minuto, segundo):
    """(año, mes, día, hora, minuto, segundo) → 7 bytes para los registros 0x00–0x06 (24 h, siglo 2000)."""
    if not 2000 <= anio <= 2099:
        raise ValueError("el DS3231 se usa para años 2000–2099")
    return bytes([int_a_bcd(segundo), int_a_bcd(minuto), int_a_bcd(hora), dia_semana(anio, mes, dia),
                  int_a_bcd(dia), int_a_bcd(mes), int_a_bcd(anio - 2000)])


def temperatura_c(msb, lsb):
    """Registros 0x11–0x12 → °C (resolución 0.25 °C, con signo)."""
    entero = msb - 256 if msb & 0x80 else msb
    return entero + (lsb >> 6) * 0.25


class DS3231:
    def __init__(self, i2c, direccion=DIRECCION):
        self.i2c, self.dir = i2c, direccion

    def presente(self):
        return self.dir in self.i2c.scan()

    def leer(self):
        """Hora UTC como (año, mes, día, hora, minuto, segundo)."""
        return decodificar(self.i2c.readfrom_mem(self.dir, REG_HORA, 7))

    def ajustar(self, anio, mes, dia, hora, minuto, segundo):
        """Pone la hora (UTC) y borra la bandera OSF: a partir de aquí la hora del reloj es confiable."""
        self.i2c.writeto_mem(self.dir, REG_HORA, codificar(anio, mes, dia, hora, minuto, segundo))
        estado = self.i2c.readfrom_mem(self.dir, REG_ESTADO, 1)[0]
        self.i2c.writeto_mem(self.dir, REG_ESTADO, bytes([estado & ~BIT_OSF & 0xFF]))

    def perdio_hora(self):
        """True si el oscilador se detuvo desde el último ajuste (pila agotada o primer uso)."""
        return bool(self.i2c.readfrom_mem(self.dir, REG_ESTADO, 1)[0] & BIT_OSF)

    def temperatura(self):
        """Temperatura interna del DS3231 (°C); la usa para compensar el oscilador."""
        msb, lsb = self.i2c.readfrom_mem(self.dir, REG_TEMP, 2)
        return temperatura_c(msb, lsb)
