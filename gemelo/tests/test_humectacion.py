import numpy as np
import pandas as pd
import pytest

from gemelo import humectacion

H = {"hr_min_pct": 80.0, "temp_min_c": 0.0, "tam_zona_m": 5.0, "max_dt_s": 5.0}


def lecturas(hr, t_mono=None, temp=20.0, x=None, y=None, sesion="sesion_0001", valida=True):
    n = len(hr)
    t_mono = list(range(n)) if t_mono is None else t_mono
    return pd.DataFrame({
        "sesion": sesion, "t_mono_s": [float(t) for t in t_mono], "hr_pct": hr,
        "temp_c": temp if np.ndim(temp) else [temp] * n,
        "utc": pd.date_range("2026-11-23T01:00:00Z", periods=n, freq="s"),
        "x_m": x if x is not None else [np.nan] * n, "y_m": y if y is not None else [np.nan] * n,
        "valida_ambiente": valida if np.ndim(valida) else [valida] * n,
    })


def test_criterio_iso_9223_es_estricto():
    df = lecturas([80.0, 80.1, 90.0, 90.0], temp=[5.0, 5.0, 0.0, 0.1])
    assert list(humectacion.marcar_humedo(df, 80.0, 0.0)["humedo"]) == [False, True, False, True]


def test_fraccion_ponderada_por_tiempo_y_huecos_limitados():
    # Dos lecturas húmedas de 1 s; luego una seca seguida de un hueco de 60 s (cuenta máx. 5 s).
    df = lecturas([90, 90, 50, 50], t_mono=[0, 1, 2, 62])
    _, por_sesion, _ = humectacion.calcular(df, H)
    r = por_sesion.iloc[0]
    assert r["tiempo_s"] == pytest.approx(1 + 1 + 5 + 1)  # la última toma la mediana (1 s)
    assert r["tiempo_humedo_s"] == pytest.approx(2)
    assert r["fraccion_humeda"] == pytest.approx(2 / 8)


def test_lecturas_invalidas_no_cuentan():
    df = lecturas([90, 90, 50, 50], valida=[True, False, True, True])
    _, por_sesion, _ = humectacion.calcular(df, H)
    assert por_sesion.iloc[0]["lecturas"] == 3
    assert por_sesion.iloc[0]["tiempo_humedo_s"] == pytest.approx(1)


def test_zonas_por_celda_y_sin_posicion():
    df = lecturas([90, 90, 50, 50], x=[1.0, 2.0, 12.0, np.nan], y=[1.0, 3.0, 1.0, np.nan])
    _, _, por_zona = humectacion.calcular(df, H)
    zonas = por_zona.set_index("zona")
    assert set(zonas.index) == {"0_0", "2_0", humectacion.SIN_POSICION}
    assert zonas.loc["0_0", "fraccion_humeda"] == 1.0
    assert zonas.loc["2_0", "fraccion_humeda"] == 0.0
    assert (zonas.loc["0_0", "zona_x_m"], zonas.loc["0_0", "zona_y_m"]) == (2.5, 2.5)
    assert np.isnan(zonas.loc[humectacion.SIN_POSICION, "zona_x_m"])


def test_resumen_por_sesion_separa_sesiones():
    df = pd.concat([lecturas([90, 90]), lecturas([50, 50], sesion="sesion_0002")], ignore_index=True)
    _, por_sesion, _ = humectacion.calcular(df, H)
    assert list(por_sesion["fraccion_humeda"]) == [1.0, 0.0]
