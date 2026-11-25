"""Bucle principal de la caja negra: lee GPS y DHT22, arma una fila por segundo y la graba en la microSD.

No importa nada de `machine`: recibe el hardware en `hw`, así el mismo bucle corre en el ESP32 (hardware.py)
y en la PC con hardware simulado (tests/test_simulacion.py).

`hw` debe tener: ms() (milisegundos monotónicos), dormir(ms), uart (read()), medir_dht() → (temp, hr),
ds3231 (o None), led_pin (o None), boton (value() == 0 si está presionado; o None), carpeta_datos,
alimentar_watchdog(), recolectar(), simulado (bool).
"""

import config
import tiempo
from dht_lector import LectorDHT
from fila import armar_fila
from gps import LectorGPS
from led import Led, elegir_estado
from registro import Registro
from reloj import Reloj


def ejecutar(hw, cfg=config, max_filas=None):
    """Graba hasta que se presiona el botón 1 s (o hasta max_filas, en pruebas). Devuelve el Registro cerrado.

    Si la microSD falla, la excepción OSError sale de aquí: main.py la anota y reinicia la placa.
    """
    t0 = hw.ms()
    led = Led(hw.led_pin)
    led.poner("arrancando", t0)
    gps = LectorGPS(hw.uart)
    dht = LectorDHT(hw.medir_dht, cfg.PERIODO_DHT_MS)
    reloj = Reloj(hw.ds3231, t0, cfg.SINC_RTC_CADA_S * 1000, cfg.RELEER_RTC_CADA_S * 1000)
    utc0, fuente0, confiable0 = reloj.hora(t0, gps.estado, cfg.GPS_MAX_EDAD_MS)
    reg = Registro(hw.carpeta_datos, cfg.PRIMERA_SESION, {
        "version": cfg.VERSION, "dispositivo": cfg.DISPOSITIVO, "simulado": hw.simulado,
        "reloj": "DS3231" if hw.ds3231 is not None else "interno del ESP32",
        "rtc_perdio_hora": reloj.rtc_perdio_hora,
        "inicio_utc": tiempo.iso(utc0), "inicio_fuente_hora": fuente0, "inicio_hora_confiable": confiable0,
        "config": cfg.como_dict(),
    })

    # el ritmo de 1 s empieza al terminar de crear la sesión (la microSD tarda ~0.8 s en crearla)
    seq, hubo_fix, siguiente, presionado = 0, False, hw.ms(), None
    try:
        while True:
            ahora = hw.ms()
            gps.actualizar(ahora)
            dht.actualizar(ahora)
            led.actualizar(ahora)
            hw.alimentar_watchdog()

            if hw.boton is not None:  # BOOT presionado 1 s: cerrar la sesión
                if hw.boton.value() == 0:
                    presionado = ahora if presionado is None else presionado
                    if ahora - presionado >= cfg.BOTON_CERRAR_MS:
                        break
                else:
                    presionado = None

            if ahora >= siguiente:
                hora = reloj.hora(ahora, gps.estado, cfg.GPS_MAX_EDAD_MS)
                f, con_fix, falla = armar_fila(gps.estado, dht.estado, hora, ahora, t0, seq + 1, reg.nombre,
                                               cfg.VERSION, cfg.GPS_MAX_EDAD_MS, cfg.DHT_MAX_EDAD_MS)
                reg.escribir(f)  # incluye flush + sync; solo cuenta si se grabó: el consecutivo no salta
                seq += 1
                if con_fix and not hubo_fix:
                    hubo_fix = True
                    reg.actualizar_metadatos(primer_fix_utc=f["utc"])
                led.poner(elegir_estado(con_fix, hubo_fix, falla), ahora)
                siguiente += cfg.PERIODO_REGISTRO_MS
                if siguiente <= ahora:  # si se atrasó, no grabar en ráfaga
                    siguiente = ahora + cfg.PERIODO_REGISTRO_MS
                hw.recolectar()
                if max_filas is not None and seq >= max_filas:
                    break
            hw.dormir(cfg.PAUSA_MS)
    except KeyboardInterrupt:  # Ctrl-C desde la PC: cerrar bien y salir
        _cerrar(reg, reloj, gps, dht, hw.ms())
        raise
    _cerrar(reg, reloj, gps, dht, hw.ms())
    led.poner("apagado", hw.ms())
    led.actualizar(hw.ms())
    return reg


def _cerrar(reg, reloj, gps, dht, ahora):
    utc, fuente, _ = reloj.hora(ahora, gps.estado)
    reg.cerrar(hora_cierre=tiempo.iso(utc), cierre_fuente_hora=fuente, gps_frases=gps.frases,
               gps_frases_malas=gps.malas, dht_fallas=dht.fallas, errores_rtc=reloj.errores_rtc)
