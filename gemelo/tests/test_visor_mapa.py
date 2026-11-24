import numpy as np
import pandas as pd

from gemelo import mapa, visor3d


def test_suelo_local_ignora_muros_y_azoteas():
    rng = np.random.default_rng(0)
    suelo = np.column_stack([rng.uniform(-10, 10, 2000), rng.uniform(-10, 10, 2000), rng.normal(100, 0.02, 2000)])
    muro = np.column_stack([rng.uniform(-1, 1, 500), rng.uniform(-1, 1, 500), rng.uniform(100, 108, 500)])
    z = visor3d.suelo_local(np.vstack([suelo, muro]), np.array([[0.0, 0.0], [5.0, 5.0]]))
    assert np.allclose(z, 100.0, atol=0.2)


def test_suelo_local_sin_vecinos_usa_el_global():
    nube = np.array([[0, 0, 10.0]] * 10 + [[1, 1, 12.0]] * 10)
    z = visor3d.suelo_local(nube, np.array([[500.0, 500.0]]))
    assert z[0] == np.percentile(nube[:, 2], 5)


def test_mapa_usa_solo_lecturas_validas_y_marca_humedo(tmp_path):
    ruta = tmp_path / "f.csv"
    pd.DataFrame({"valida_posicion": [True, True, False, True], "valida_ambiente": [True, False, True, True],
                  "hr_pct": [85.0, 90.0, 90.0, 50.0], "temp_c": [20.0] * 4, "lat": [20.1] * 4,
                  "lon": [-101.1] * 4}).to_csv(ruta, index=False)
    df = mapa.lecturas_para_mapa(ruta, cada_s=1)
    assert list(df.index) == [0, 3]
    assert list(df["humedo"]) == [True, False]
