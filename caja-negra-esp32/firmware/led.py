"""Estado de la caja negra con el LED azul de la placa (GPIO8, se enciende con 0).

Con un solo LED (sin el RGB de la versión con Pi), cada estado es un patrón de parpadeo:
    arrancando  parpadeo rápido (montando la microSD, buscando el reloj)
    buscando    lento, 0.5 s / 0.5 s — grabando, aún sin el primer fix
    fix         encendido fijo — grabando con posición
    sin_fix     destello corto cada 2 s — grabando, se perdió el fix
    error       doble destello — microSD o sensor sin responder
    apagado     detenido con el botón (sesión cerrada)
"""

PATRONES = {  # duraciones en ms alternando encendido, apagado, encendido…
    "arrancando": (100, 100),
    "buscando": (500, 500),
    "fix": (1000,),
    "sin_fix": (100, 1900),
    "error": (100, 150, 100, 650),
    "apagado": (),
}


def elegir_estado(con_fix, hubo_fix, falla):
    if falla:
        return "error"
    if con_fix:
        return "fix"
    return "sin_fix" if hubo_fix else "buscando"


class Led:
    def __init__(self, pin=None, activo_en_bajo=True):
        self.pin, self.bajo = pin, activo_en_bajo
        self.estado, self.inicio = "apagado", 0
        self._poner(False)

    def _poner(self, encendido):
        if self.pin is not None:
            self.pin.value(0 if encendido == self.bajo else 1)

    def poner(self, estado, ahora_ms=0):
        if estado != self.estado:
            self.estado, self.inicio = estado, ahora_ms

    def encendido(self, ahora_ms):
        """True si en este instante el patrón del estado tiene el LED encendido."""
        patron = PATRONES[self.estado]
        if not patron:
            return False
        if len(patron) == 1:
            return True
        t = (ahora_ms - self.inicio) % sum(patron)
        for i, dur in enumerate(patron):
            if t < dur:
                return i % 2 == 0
            t -= dur
        return False

    def actualizar(self, ahora_ms):
        self._poner(self.encendido(ahora_ms))
