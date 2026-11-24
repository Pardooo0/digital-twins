import numpy as np
import pytest

from gemelo import nube


def sitio(semilla=0):
    """Suelo plano a z=1900, muro de 7 m y puntos sueltos muy abajo y muy arriba (como con fotos a 0°)."""
    rng = np.random.default_rng(semilla)
    suelo = np.column_stack([rng.uniform(-20, 20, 4000), rng.uniform(-20, 20, 4000), rng.normal(1900, 0.05, 4000)])
    muro = np.column_stack([rng.uniform(-5, 5, 2000), rng.uniform(-5, 5, 2000), rng.uniform(1900, 1907, 2000)])
    sueltos = np.column_stack([rng.uniform(-60, 60, 300), rng.uniform(-60, 60, 300), rng.uniform(1840, 1960, 300)])
    return np.vstack([suelo, muro, sueltos])


CAMINO = np.array([[x, y] for x in np.linspace(-8, 8, 40) for y in (-8.0, 8.0)])


def test_suelo_del_recorrido_ignora_puntos_sueltos():
    assert nube.suelo_del_recorrido(sitio(), CAMINO) == pytest.approx(1900.0, abs=0.15)


def test_suelo_del_recorrido_falla_sin_puntos_cerca():
    with pytest.raises(ValueError, match="camino"):
        nube.suelo_del_recorrido(sitio(), CAMINO + 1000)


def modelo_minimo(carpeta):
    """OBJ de 2 triángulos con una textura mitad roja (izquierda) y mitad azul (derecha)."""
    from PIL import Image

    img = Image.new("RGB", (8, 8), (255, 0, 0))
    img.paste((0, 0, 255), (4, 0, 8, 8))
    img.save(carpeta / "tex.png")
    (carpeta / "m.mtl").write_text("newmtl mat\nKd 1 1 1\nmap_Kd tex.png\n", encoding="utf-8")
    (carpeta / "m.obj").write_text(
        "mtllib m.mtl\nusemtl mat\n"
        "v 0 0 1900\nv 1 0 1900\nv 0 1 1900\nv 1 1 1900\n"
        "vt 0.05 0.05\nvt 0.2 0.05\nvt 0.05 0.9\nvt 0.95 0.95\nvt 0.8 0.95\nvt 0.95 0.1\n"
        "f 1/1 2/2 3/3\nf 4/4 3/5 2/6\n", encoding="utf-8")
    (carpeta / "coords.txt").write_text("WGS84 UTM 14N\n275164 2228304\n", encoding="utf-8")


def test_leer_malla_toma_el_color_de_la_textura_y_suma_el_desplazamiento(tmp_path):
    modelo_minimo(tmp_path)
    v, caras, colores = nube.leer_malla(tmp_path / "m.obj", tmp_path / "coords.txt")
    assert len(caras) == 2
    assert v[:, 0].min() == pytest.approx(275164) and v[:, 1].min() == pytest.approx(2228304)
    assert sorted(map(tuple, colores)) == [(0, 0, 255), (255, 0, 0)]  # una cara roja y una azul


def test_recortar_malla_reindexa_vertices():
    v = np.arange(15, dtype=float).reshape(5, 3)
    caras = np.array([[0, 1, 2], [2, 3, 4]])
    nv, nc, ncol = nube.recortar_malla(v, caras, np.array([[1, 1, 1], [2, 2, 2]]), np.array([False, True]))
    assert len(nv) == 3 and nc.tolist() == [[0, 1, 2]] and ncol.tolist() == [[2, 2, 2]]
    assert np.array_equal(nv[nc[0]], v[[2, 3, 4]])


def edificio_girado(angulo=30.0, largo=20.0, ancho=12.0, alto=7.0, semilla=1):
    """Muros de un edificio rectangular girado, suelo alrededor y el camino a 3 m de los muros."""
    rng = np.random.default_rng(semilla)
    t = np.radians(angulo)
    R = np.array([[np.cos(t), np.sin(t)], [-np.sin(t), np.cos(t)]])
    puntos = []
    for _ in range(4000):  # muros (en ejes locales u, v)
        lado = rng.integers(4)
        u = rng.uniform(0, largo) if lado < 2 else (0.0 if lado == 2 else largo)
        v = (0.0 if lado == 0 else ancho) if lado < 2 else rng.uniform(0, ancho)
        puntos.append([u, v, 1900 + rng.uniform(0, alto)])
    suelo = np.column_stack([rng.uniform(-8, largo + 8, 3000), rng.uniform(-8, ancho + 8, 3000),
                             rng.normal(1900, 0.03, 3000)])
    local = np.vstack([np.array(puntos), suelo])
    xyz = np.column_stack([local[:, :2] @ R + [500.0, 300.0], local[:, 2]])
    camino = [[u, -3.0] for u in np.arange(-3, largo + 3, 0.3)] + [[largo + 3, v] for v in np.arange(-3, ancho + 3, 0.3)] \
        + [[u, ancho + 3] for u in np.arange(largo + 3, -3, -0.3)] + [[-3.0, v] for v in np.arange(ancho + 3, -3, -0.3)]
    return xyz, np.array(camino) @ R + [500.0, 300.0]


def test_volumen_lod1_recupera_planta_orientacion_y_altura():
    xyz, camino = edificio_girado()
    vol = nube.volumen_lod1(xyz, camino, suelo=1900.0)
    assert vol["angulo_grados"] == pytest.approx(30.0, abs=1.5)
    assert sorted([vol["largo_m"], vol["ancho_m"]]) == pytest.approx([12.0, 20.0], abs=1.0)
    assert vol["altura_m"] == pytest.approx(0.9 * 7.0, abs=0.8)  # percentil 90 de muros uniformes de 7 m
    assert vol["esquinas"].shape == (4, 2)


def test_recortar_en_planta_con_margen_y_en_altura():
    xyz = sitio()
    ok = nube.recortar(xyz, CAMINO, margen_m=2.0, z_min=1898.5, z_max=1915.0)
    dentro = xyz[ok]
    assert np.abs(dentro[:, :2]).max() <= 8 * 1.5  # casco de ±8 m ampliado 2 m (en las esquinas, más)
    assert dentro[:, 2].min() >= 1898.5 and dentro[:, 2].max() <= 1915.0
    assert ok.sum() > 2000  # conserva el muro y el suelo cercano
