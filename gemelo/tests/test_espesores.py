import numpy as np
import pandas as pd
import pytest

from gemelo import config, espesores

P = config.DEFECTOS["espesores"]


def nube(n=500, semilla=0):
    """Suelo en z≈0 en un cuadro de 40 m y una 'estructura' de 0 a 8 m en el centro."""
    rng = np.random.default_rng(semilla)
    suelo = np.column_stack([rng.uniform(-20, 20, n), rng.uniform(-20, 20, n), rng.normal(0, 0.05, n)])
    muro = np.column_stack([rng.uniform(-5, 5, n), rng.uniform(-5, 5, n), rng.uniform(0, 8, n)])
    return np.vstack([suelo, muro])


def test_sin_ruido_recupera_vc_y_vr_conocidas():
    rng = np.random.default_rng(1)
    xyz = nube()[:30]
    df = espesores.calcular_vc_vr(espesores.generar_campanas(xyz, P, rng, ruido_mm=0.0), P["dt_anios"], P["t_req_mm"])
    assert np.allclose(df["vc_mm_anio"], df["vc_real_mm_anio"])
    assert np.allclose(df["vr_anios"], df["vr_real_anios"])
    assert df["vc_real_mm_anio"].between(P["vc_min_mm_anio"], P["vc_max_mm_anio"]).all()


def test_valores_a_mano():
    df = pd.DataFrame({"t_ant_mm": [5.0], "t_act_mm": [4.8], "t_ant_real_mm": [5.0], "t_act_real_mm": [4.8],
                       "vc_real_mm_anio": [0.1]})
    r = espesores.calcular_vc_vr(df, dt_anios=2.0, t_req_mm=3.0).iloc[0]
    assert r["vc_mm_anio"] == pytest.approx(0.1)        # (5.0 − 4.8) / 2
    assert r["vr_anios"] == pytest.approx(18.0)         # (4.8 − 3.0) / 0.1


def test_error_de_vc_acotado_por_el_ruido():
    # Con ruido uniforme ±r en cada campaña, |error VC| <= 2r / Δt.
    rng = np.random.default_rng(2)
    df = espesores.calcular_vc_vr(espesores.generar_campanas(nube()[:200], P, rng, ruido_mm=0.05),
                                  P["dt_anios"], P["t_req_mm"])
    assert (df["error_vc_mm_anio"].abs() <= 2 * 0.05 / P["dt_anios"] + 1e-12).all()
    assert df["error_vc_mm_anio"].abs().max() > 0


def test_vr_no_estimable_si_la_perdida_queda_en_el_ruido():
    df = pd.DataFrame({"t_ant_mm": [5.00, 5.00], "t_act_mm": [5.01, 5.00], "t_ant_real_mm": [5.0, 5.0],
                       "t_act_real_mm": [4.99, 4.99], "vc_real_mm_anio": [0.005, 0.005]})
    r = espesores.calcular_vc_vr(df, dt_anios=2.0, t_req_mm=3.0)
    assert r["vr_anios"].isna().all()
    assert espesores.resumen_errores(r)["vr_no_estimable"] == 2


def test_puntos_sobre_la_estructura_y_dentro_de_la_region():
    rng = np.random.default_rng(3)
    region = np.array([[-6, -6], [6, -6], [6, 6], [-6, 6]])
    xyz = espesores.puntos_de_nube(nube(), 50, rng, region, altura_min_m=1.0)
    assert len(xyz) == 50
    assert (np.abs(xyz[:, :2]) <= 6).all()
    assert (xyz[:, 2] >= 0.9).all()  # sin suelo
    with pytest.raises(ValueError, match="candidatos"):
        espesores.puntos_de_nube(nube(n=10), 50, rng, region)


def test_barrido_error_crece_con_el_ruido_y_es_reproducible():
    xyz = nube()[:30]
    b = espesores.barrido_ruido(xyz, P, [0.0, 0.01, 0.05, 0.10], repeticiones=20, semilla=7)
    assert b.loc[0, "vc_error_medio_abs"] == pytest.approx(0.0, abs=1e-12)
    assert b["vc_error_medio_abs"].is_monotonic_increasing
    pd.testing.assert_frame_equal(b, espesores.barrido_ruido(xyz, P, [0.0, 0.01, 0.05, 0.10], 20, 7))
