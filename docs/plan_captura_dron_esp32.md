# Plan: nueva captura fotográfica con la caja negra ESP32-C3 a bordo del dron

Proyecto «Inspecciones de Nivel 2 y gemelos digitales mediante RPAS» · etapa M5 de la migración a ESP32-C3.
Estructura: `estructura1` (edificio de 2 pisos, ~38 × 30 m en planta y 5.8 m de altura). Dron: DJI Mini 4K.

## 1. Objetivo

1. Repetir la captura de `estructura1` corrigiendo la lección de la Fase 5: además de las fotos casi
   horizontales, tomar una **órbita a −45°** y una **pasada cenital (−90°)**. Así ODM puede generar un
   ortomosaico y un DSM útiles, y reconstruir la azotea.
2. Llevar la caja negra **a bordo del dron**, para que las lecturas de temperatura y humedad queden asociadas a la
   posición y la altura de vuelo, y no al recorrido a pie.

## 2. Antes de volar: ¿puede el Mini 4K cargar la caja?

**Esta es la decisión que define el plan.** El DJI Mini 4K está diseñado para despegar con menos de 249 g, y DJI
no publica una carga útil admisible. Toda masa agregada reduce el tiempo de vuelo y la resistencia al viento, y
puede afectar la estabilidad. Hay tres consecuencias que revisar:

- **Regulación:** con la caja, el peso de despegue supera los 250 g. Según la NOM-107-SCT3-2019, a partir de ese
  peso el RPAS debe registrarse ante la AFAC. **Confírmalo en el texto vigente de la norma o con la AFAC antes de
  volar.** Sigue siendo categoría *micro* (≤ 2 kg).
- **Garantía y seguridad:** DJI no contempla accesorios de terceros en el Mini 4K. Vuela solo en zona despejada,
  sin personas debajo y con autorización del responsable del edificio.
- **Masa:** hay que pesarla, no suponerla (sección 2.1).

### 2.1 Presupuesto de masa (pesar con báscula de 0.1 g)

| Pieza | Estimación previa (a confirmar) | Masa medida |
|---|---|---|
| ESP32-C3 Super Mini + placa de expansión | 6–8 g | |
| DS3231 (ZS-042) con pila CR2032 | 8–10 g | |
| Adaptador microSD con tarjeta | 3–4 g | |
| DHT22 en su módulo | 4–6 g | |
| Shield GPS Duinopeak (+ antena, si es externa) | 25–40 g | |
| Batería LiPo 1S (300–500 mAh) | 8–12 g | |
| Elevador a 5 V (sección 3) | 2–3 g | |
| Cables, cinchos y soporte | 10–15 g | |
| **Total** | **≈ 70–100 g** | |

El **shield GPS es la pieza más pesada**: es del tamaño de una placa Arduino. Si la prueba de carga falla, la
primera opción es sustituirlo por un módulo NEO-6M pequeño (mismo receptor y mismas frases NMEA, sin cambiar el
firmware ni el contrato de datos). Con eso, la caja quedaría en unos 45–60 g.

### 2.2 Prueba de carga (en tierra, antes del día de captura)

1. Pesa el dron con batería y hélices, y la caja completa.
2. Fija la caja (o un lastre de la misma masa) y haz un **vuelo estacionario de 2 min a 2–3 m** sobre pasto, sin
   viento.
3. Sube a 10 m a velocidad normal, desplázate 20 m en cada dirección y aterriza.
4. Anota el porcentaje de batería que consumió por minuto y compáralo con un vuelo igual sin la caja.

**Se vuela con la caja si se cumplen todos estos criterios:**
- La app no muestra advertencias (sobrecarga, motores, brújula, IMU).
- El dron se mantiene quieto sin corregirlo con los mandos.
- Consume como máximo **1.5 veces** la batería por minuto que sin la caja.
- El dron sigue recibiendo los mismos satélites con la caja encendida (sin interferencia).

**Si no se cumplen:** se aligera la caja (sección 2.1) o se vuela como en la Fase 5, con la caja **en mano**. En
ese caso se conserva el objetivo 1 (las nuevas órbitas y la pasada cenital).

## 3. Alimentación a bordo (validar en mesa antes)

Un power bank es demasiado pesado para el dron. La placa de expansión trae conector y cargador para una LiPo de una
celda (3.7 V), **pero la microSD y el GPS necesitan 5 V**. Con 3.7 V, el regulador del adaptador microSD le deja a
la tarjeta menos de 3 V. Propuesta:

- LiPo 1S de 300–500 mAh → **módulo elevador a 5 V** → pin 5V de la Super Mini, microSD y GPS. El reloj y el
  DHT22 siguen tomando 3.3 V de las tiras rojas.
- **No conectar el USB mientras la batería está conectada.**
- **Validación en mesa:** 1 h de registro solo con la batería y `verificar_sesion.py` con 0 errores. Mide la
  corriente con el multímetro para calcular la autonomía: con un consumo de 100–150 mA a 5 V (estimado),
  500 mAh alcanzan para unas 2 h.

## 4. Montaje en el dron

- **Arriba del cuerpo y centrada**, cerca del centro de gravedad. Nunca abajo: ahí están los sensores de visión
  inferiores y el tren de aterrizaje.
- Fijación ligera (soporte impreso en 3D o cinta de doble cara con cincho) y un **cordón de seguridad**. Nada debe
  poder alcanzar las hélices.
- **Antena GPS de la caja hacia el cielo**, sin metal encima.
- **DHT22 hacia el frente o un costado**, lejos de la batería y del calor de la electrónica, con aire libre
  alrededor. El aire que entra a las hélices por arriba es aire ambiente.
- Tras montar la caja, revisa en la app que no haya advertencias de brújula; calíbrala si la app lo pide.
- Etiqueta la caja con el nombre del proyecto y un teléfono de contacto.

## 5. Preparación de la caja (en la PC, el día anterior)

- [ ] M4 terminada: 1 h continua y 5 cortes de energía con 0 errores.
- [ ] Prueba de alimentación con batería (sección 3) superada.
- [ ] Reloj en hora: `.\caja-negra-esp32\scripts\ajustar_rtc.ps1 -Puerto COM3`.
- [ ] Pila del DS3231: tras varias horas sin USB, el reloj conserva la hora (`prueba_rtc.py` sin OSF).
- [ ] Firmware cargado **sin** modo mantenimiento: `.\caja-negra-esp32\scripts\cargar.ps1 -Puerto COM3`.
- [ ] microSD con espacio libre; batería LiPo cargada.
- [ ] Baterías del dron cargadas (mínimo 3: una por vuelo).

## 6. Plan de vuelo

Día nublado o con sol alto, viento débil, sin lluvia. Cámara: fotos en 4:3 y JPEG, sin zoom. Lleva el celular con
la ubicación de la cámara activada, como respaldo.

| Vuelo | Qué | Altura sobre el despegue | Cámara | Fotos |
|---|---|---|---|---|
| A | **Pasada cenital**: cuadrícula de 4 líneas paralelas sobre el edificio y 15 m alrededor (~70 × 60 m), separadas ~17 m, con una foto cada ~8 m (traslape ~80 % / 70 %) | 40 m | −90° | ~36 |
| B | **Órbita a −45°**: radio ~30 m desde el centro del edificio, una foto cada 10° | 20–25 m | −45° | ~36 |
| C | **Órbita baja** para los muros: radio 30–35 m, una foto cada 10° | 6–10 m | −10° a −20° | ~36 |

- Total esperado: **~110 fotos** (ODM las procesa sin problema en esta PC de 32 GB).
- Vuela a velocidad baja y constante. Usa disparo por intervalos si la app lo permite (cada 2–3 s); si no,
  dispara a mano en cada posición.
- Con la caja a bordo, cada vuelo dura **como máximo 10–12 min**. Aterriza con 30 % de batería o más.
- **Lecturas fijas:** al terminar el vuelo B, mantén el dron quieto **30 s** sobre cada esquina del edificio, a
  la altura de la azotea + 3 m. El DHT22 tarda varios segundos en estabilizarse. Anota la hora de cada punto.

## 7. Secuencia el día de la captura

1. Conecta la batería de la caja **5 min antes** del primer vuelo, en un lugar despejado. Espera al **LED azul
   fijo** (fix del GPS; en arranque en frío tarda de 1 a 5 min).
2. **Foto de sincronización:** con la cámara del dron, fotografía la pantalla de un celular que muestre la hora
   exacta. Así se mide el desfase entre la hora del EXIF (hora local del celular, UTC−6) y la UTC de la caja.
3. Monta la caja en el dron sin desconectarla y revisa la app (sin advertencias, satélites).
4. Haz los vuelos A, B y C. Al cambiar la batería del dron, **no desconectes la caja**: debe ser una sola sesión.
5. Al final, presiona **BOOT 1 s** para cerrar la sesión (el LED se apaga) y desconecta la batería de la caja.
6. Anota en una bitácora: hora de cada vuelo, viento, nubosidad, masa de la caja y los incidentes.

## 8. Después del vuelo (en la PC)

1. **Caja:** saca la microSD y copia `datos/sesion_10NN.csv` y `.json` a `gemelo/datos/cajanegra/`. Verifica
   con `python caja-negra/tests/verificar_sesion.py gemelo/datos/cajanegra/sesion_10NN.csv` (0 errores).
2. **Fotos:** revisa que todas traen GPS (Propiedades → Detalles). Cópialas a
   `gemelo/datos/fotos/estructura1_v3/images/` y a `C:\odm\estructura1_v3\images\` (fuera de OneDrive).
3. **ODM** (Docker Desktop abierto):
   ```
   docker run -d --name odm_estructura1_v3 -v C:/odm:/datasets opendronemap/odm --project-path /datasets estructura1_v3 --dsm --orthophoto-resolution 2 --auto-boundary --feature-quality ultra --min-num-features 20000 --pc-quality high --mesh-size 400000 --mesh-octree-depth 12 --gltf
   ```
   Al terminar, copia a `gemelo/datos/odm/estructura1_v3/` las mismas salidas que en la Fase 6.
4. **Gemelo:** en `gemelo/config.yaml`, cambia `odm_proyecto: estructura1_v3` y `sesiones: [sesion_10NN]`.
   Después corre `fusion` → `humectacion` → `nube` → `espesores` → `mapa` → `visor3d`.

## 9. Cambio necesario en el gemelo (antes de procesar)

`fusion.py` asume que la caja va **en mano**: a cada lectura le asigna la altura del DSM bajo ese punto
(`z_dsm_m`). Con la caja a bordo, la altura de la lectura es la **altura de vuelo**. Hay que agregar en
`config.yaml` una opción para sesiones aéreas que use `alt_m` del GPS de la caja, referida a la altitud del
punto de despegue (las primeras filas con fix, antes de despegar). El error vertical del GPS es mayor que el
horizontal, así que conviene reportarlo. **El contrato de datos no cambia:** es un ajuste solo del gemelo, con
sus pruebas en pytest.

## 10. Hecho cuando

- Las ~110 fotos están en `gemelo/datos/fotos/estructura1_v3/images/` y la sesión de la caja en
  `gemelo/datos/cajanegra/`, con 0 errores en el verificador.
- ODM produce un ortomosaico y un DSM **sin deformaciones** y el modelo incluye la azotea.
- El mapa y el visor 3D muestran las lecturas de la caja a la altura de vuelo.
- Están registradas para el informe: la masa de la caja, el resultado de la prueba de carga, el consumo de
  batería del dron con y sin la caja, y la autonomía de la caja con batería.
