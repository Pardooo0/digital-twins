"""LED RGB de estado (KY-016, cátodo común) con gpiozero."""

import logging

log = logging.getLogger(__name__)

COLORES = {"sin_fix": (1, 1, 0), "fix": (0, 1, 0), "error": (1, 0, 0)}


def elegir_estado(con_fix, hubo_fix, falla):
    """Azul parpadeando hasta el primer fix; amarillo si se perdió; verde con fix; rojo si algo falla."""
    if falla:
        return "error"
    if con_fix:
        return "fix"
    return "sin_fix" if hubo_fix else "buscando"


class Led:
    def __init__(self, pines):
        """`pines` = {r, g, b} en numeración BCM, o None para no usar GPIO (modo simulado)."""
        self._rgb, self._actual = None, None
        if pines is None:
            return
        try:
            from gpiozero import RGBLED
            self._rgb = RGBLED(pines["r"], pines["g"], pines["b"])
        except Exception as e:  # el LED no es crítico: se sigue grabando sin él
            log.warning("LED no disponible: %s", e)

    def poner(self, estado):
        if estado == self._actual:
            return
        self._actual = estado
        log.info("LED: %s", estado)
        if self._rgb is None:
            return
        if estado in ("arrancando", "buscando"):
            self._rgb.blink(on_time=0.5, off_time=0.5, on_color=(0, 0, 1))
        elif estado == "apagado":
            self._rgb.off()
        else:
            self._rgb.color = COLORES[estado]
