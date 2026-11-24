import csv

import numpy as np
import pandas as pd
import pytest

from gemelo import fusion
from gemelo.fusion import COLUMNAS


def fila(seq, sesion="sesion_0001", **cambios):
    base = {"sesion": sesion, "seq": seq, "t_mono_s": float(seq - 1),
            "utc": f"2026-11-23T01:00:{seq - 1:02d}.000Z", "fuente_hora": "sistema",
            "lat": "", "lon": "", "alt_m": "", "fix": 0, "sats": "", "hdop": "",
            "temp_c": 23.8, "hr_pct": 74.1, "dht_edad_s": 1.0, "espesor_mm": "",
            "banderas": "SIN_FIX;HORA_SISTEMA", "version": "0.2.1"}
    return {**base, **cambios}


def escribir(ruta, filas, cortar=0):
    with open(ruta, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNAS)
        w.writeheader()
        w.writerows(filas)
    if cortar:
        datos = ruta.read_bytes()
        ruta.write_bytes(datos[:-cortar])


def test_lee_y_une_sesiones_y_descarta_la_fila_cortada(tmp_path):
    escribir(tmp_path / "sesion_0001.csv", [fila(1), fila(2), fila(3)], cortar=20)
    escribir(tmp_path / "sesion_0002.csv", [fila(1, "sesion_0002")])
    df = fusion.leer_sesiones(tmp_path)
    assert list(df["sesion"]) == ["sesion_0001", "sesion_0001", "sesion_0002"]
    assert str(df["utc"].dt.tz) == "UTC"


def test_lee_solo_las_sesiones_pedidas(tmp_path):
    escribir(tmp_path / "sesion_0001.csv", [fila(1)])
    escribir(tmp_path / "sesion_0002.csv", [fila(1, "sesion_0002"), fila(2, "sesion_0002")])
    df = fusion.leer_sesiones(tmp_path, ["sesion_0002"])
    assert set(df["sesion"]) == {"sesion_0002"} and len(df) == 2
    assert len(fusion.leer_sesiones(tmp_path, [])) == 3  # vacío = todas
    with pytest.raises(FileNotFoundError, match="sesion_0009"):
        fusion.leer_sesiones(tmp_path, ["sesion_0009"])


def test_falla_si_falta_una_columna_del_contrato(tmp_path):
    (tmp_path / "sesion_0001.csv").write_text("sesion,seq\nsesion_0001,1\n", encoding="utf-8")
    with pytest.raises(ValueError, match="faltan columnas"):
        fusion.leer_sesiones(tmp_path)


def test_corrige_filas_hora_no_sinc_con_t_mono(tmp_path):
    # Arranque con la hora de anoche; en la fila 3 NTP sincroniza el reloj.
    filas = [fila(1, utc="2026-11-22T07:47:46.000Z", banderas="SIN_FIX;HORA_SISTEMA;HORA_NO_SINC"),
             fila(2, utc="2026-11-22T07:47:47.000Z", banderas="SIN_FIX;HORA_SISTEMA;HORA_NO_SINC"),
             fila(3, utc="2026-11-23T00:54:15.000Z"), fila(4, utc="2026-11-23T00:54:16.000Z")]
    escribir(tmp_path / "sesion_0001.csv", filas)
    df = fusion.corregir_hora(fusion.leer_sesiones(tmp_path))
    assert list(df["hora_corregida"]) == [True, True, False, False]
    assert df["utc"].iloc[0] == pd.Timestamp("2026-11-23T00:54:13Z")
    assert df["hora_valida"].all()


def test_corrige_sesiones_viejas_sin_bandera_por_el_salto(tmp_path):
    filas = [fila(1, utc="2026-11-22T07:47:46.000Z"), fila(2, utc="2026-11-22T07:47:47.000Z"),
             fila(3, utc="2026-11-23T00:54:15.000Z")]
    escribir(tmp_path / "sesion_0001.csv", filas)
    df = fusion.corregir_hora(fusion.leer_sesiones(tmp_path))
    assert list(df["hora_corregida"]) == [True, True, False]
    assert df["utc"].iloc[1] == pd.Timestamp("2026-11-23T00:54:14Z")


def test_sesion_sin_ninguna_hora_confiable_queda_invalida(tmp_path):
    escribir(tmp_path / "sesion_0001.csv", [fila(1, banderas="SIN_FIX;HORA_SISTEMA;HORA_NO_SINC")])
    df = fusion.corregir_hora(fusion.leer_sesiones(tmp_path))
    assert not df["hora_valida"].any()


def preparar(tmp_path, filas, hdop_max=5.0):
    escribir(tmp_path / "sesion_0001.csv", filas)
    return fusion.clasificar(fusion.corregir_hora(fusion.leer_sesiones(tmp_path)), hdop_max)


def con_fix(seq, **cambios):
    gps = {"fuente_hora": "gps", "lat": 20.1426, "lon": -101.1756, "alt_m": 1915.3, "fix": 1, "sats": 7,
           "hdop": 1.2, "banderas": ""}
    return fila(seq, **{**gps, **cambios})


def test_clasifica_validez_y_motivos(tmp_path):
    df = preparar(tmp_path, [con_fix(1), con_fix(2, hdop=6.0), fila(3),
                             fila(4, temp_c="", hr_pct="", banderas="SIN_FIX;DHT_ERROR;HORA_SISTEMA")])
    assert list(df["valida_posicion"]) == [True, False, False, False]
    assert list(df["valida_ambiente"]) == [True, True, True, False]
    assert list(df["motivo_descarte"]) == ["", "hdop_alto", "sin_fix", "dht_error;sin_fix"]


def test_convierte_a_utm_14n(tmp_path):
    # Sobre el meridiano central de la zona 14 (−99°) y el ecuador: x = 500 000 m, y = 0 m.
    df = preparar(tmp_path, [con_fix(1, lat=0.0, lon=-99.0), fila(2)])
    df = fusion.a_utm(df, "EPSG:32614")
    assert df["x_m"].iloc[0] == pytest.approx(500000.0, abs=0.01)
    assert df["y_m"].iloc[0] == pytest.approx(0.0, abs=0.01)
    assert np.isnan(df["x_m"].iloc[1])


def test_toma_la_altura_del_dsm(tmp_path):
    rasterio = pytest.importorskip("rasterio")
    from rasterio.transform import from_origin

    ruta = tmp_path / "dsm.tif"
    datos = np.array([[1900.0, 1901.0], [1902.0, -9999.0]], dtype="float32")  # celdas de 10 m
    with rasterio.open(ruta, "w", driver="GTiff", height=2, width=2, count=1, dtype="float32",
                       crs="EPSG:32614", transform=from_origin(300000, 2230020, 10, 10), nodata=-9999) as r:
        r.write(datos, 1)
    df = pd.DataFrame({"x_m": [300005.0, 300015.0, 300015.0, 400000.0, np.nan],
                       "y_m": [2230015.0, 2230015.0, 2230005.0, 2230015.0, np.nan]})
    z = fusion.altura_dsm(df, ruta)["z_dsm_m"]
    assert z.iloc[0] == 1900.0 and z.iloc[1] == 1901.0
    assert z.iloc[2:].isna().all()  # sin dato, fuera del ráster y sin posición
