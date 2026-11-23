import json

from cajanegra.registro import Registro
from verificar_sesion import main, verificar_csv


def fila(seq, **cambios):
    base = {"seq": seq, "t_mono_s": seq - 1.0, "utc": f"2026-11-22T07:35:{seq:02d}.000Z",
            "fuente_hora": "sistema", "lat": None, "lon": None, "alt_m": None, "fix": 0,
            "sats": None, "hdop": None, "temp_c": 23.8, "hr_pct": 74.1, "dht_edad_s": 1.0,
            "espesor_mm": None, "banderas": "SIN_FIX;HORA_SISTEMA", "version": "0.1.0"}
    return {**base, **cambios}


def sesion(tmp_path, filas, cerrar=True):
    r = Registro(tmp_path, {"version": "0.1.0"})
    for f in filas:
        r.escribir(f)
    if cerrar:
        r.cerrar(hora_cierre="2026-11-22T08:00:00.000Z", filas=len(filas))
    return r.ruta_csv


def test_sesion_valida_sin_errores(tmp_path):
    con_fix = fila(3, fuente_hora="gps", lat=20.1426, lon=-101.1756, alt_m=1915.3, fix=1, sats=7,
                   hdop=1.2, banderas="")
    ruta = sesion(tmp_path, [fila(1), fila(2), con_fix])
    errores, avisos, filas = verificar_csv(ruta)
    assert (errores, avisos, filas) == ([], [], 3)


def test_detecta_salto_en_seq(tmp_path):
    ruta = sesion(tmp_path, [fila(1), fila(2), fila(4, t_mono_s=3.0)])
    errores, _, _ = verificar_csv(ruta)
    assert any("se esperaba 3" in e for e in errores)


def test_detecta_banderas_incoherentes(tmp_path):
    ruta = sesion(tmp_path, [fila(1, banderas="HORA_SISTEMA")])  # sin fix pero sin SIN_FIX
    errores, _, _ = verificar_csv(ruta)
    assert any("SIN_FIX" in e for e in errores)


def test_avisa_salto_de_reloj(tmp_path):
    # el reloj de la Pi arranca con la hora de anoche y NTP lo adelanta horas en la fila 3
    ruta = sesion(tmp_path, [fila(1, banderas="SIN_FIX;HORA_SISTEMA;HORA_NO_SINC"),
                             fila(2, banderas="SIN_FIX;HORA_SISTEMA;HORA_NO_SINC"),
                             fila(3, utc="2026-11-23T00:54:15.000Z")])
    errores, avisos, _ = verificar_csv(ruta)
    assert errores == []
    assert any("línea 4: salto de reloj" in a for a in avisos)


def test_hora_no_sinc_exige_hora_sistema(tmp_path):
    ruta = sesion(tmp_path, [fila(1, fuente_hora="gps", banderas="SIN_FIX;HORA_NO_SINC")])
    errores, _, _ = verificar_csv(ruta)
    assert any("HORA_NO_SINC" in e for e in errores)


def test_fila_corrupta_a_mitad_es_error(tmp_path):
    ruta = sesion(tmp_path, [fila(1), fila(2), fila(3)])
    lineas = ruta.read_text(encoding="utf-8").splitlines(keepends=True)
    lineas[2] = "sesion_0001,2,basura\r\n"
    ruta.write_bytes("".join(lineas).encode("utf-8"))
    errores, _, _ = verificar_csv(ruta)
    assert any("línea 3" in e for e in errores)


def test_corte_de_energia_pierde_solo_la_ultima_fila(tmp_path):
    ruta = sesion(tmp_path, [fila(1), fila(2), fila(3)], cerrar=False)
    datos = ruta.read_bytes()
    ruta.write_bytes(datos[:-25])  # la última fila quedó a medias
    errores, avisos, filas = verificar_csv(ruta)
    assert errores == []
    assert filas == 2
    assert any("incompleta" in a for a in avisos)
    assert any("sin cerrar" in a for a in avisos)


def test_metadatos_con_otro_numero_de_filas(tmp_path):
    ruta = sesion(tmp_path, [fila(1), fila(2)])
    meta = json.loads(ruta.with_suffix(".json").read_text(encoding="utf-8"))
    meta["filas"] = 5
    ruta.with_suffix(".json").write_text(json.dumps(meta), encoding="utf-8")
    errores, _, _ = verificar_csv(ruta)
    assert any("5 filas" in e for e in errores)


def test_main_codigo_de_salida(tmp_path, capsys):
    sesion(tmp_path, [fila(1), fila(2)])
    assert main([str(tmp_path)]) == 0
    sesion(tmp_path, [fila(1), fila(3, t_mono_s=1.0)])
    assert main([str(tmp_path)]) == 1
    assert "Total: 2 sesiones" in capsys.readouterr().out
