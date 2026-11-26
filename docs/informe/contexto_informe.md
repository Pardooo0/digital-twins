# Parte práctica para el informe — «Inspecciones de Nivel 2 y gemelos digitales mediante RPAS»

Residencia profesional · ITSUR · agosto–diciembre de 2026 · Autor: Rafael Castro Tinoco
Corte de este documento: 2026-11-24 (pruebas de campo terminadas; pendiente: migración a ESP32-C3).

## 0. Cómo usar este documento (instrucciones para el asistente que ayuda a redactar)

- **El informe ya tiene escrita toda la parte teórica** (marco teórico, conceptos, normas, estado del arte).
  Tu tarea es **agregar solo la parte práctica**: desarrollo e implementación, pruebas, resultados, discusión,
  conclusiones de las pruebas y trabajo futuro. **No reescribas ni dupliques la teoría**; cuando haga falta un
  concepto (Nivel 2, gemelo digital, ISO 9223, fotogrametría, LOD1…), refiérete a la sección teórica del informe
  en lugar de volver a explicarlo. Las explicaciones breves de este documento son solo para que entiendas el
  contexto.
- Antes de redactar, pide al autor el índice actual del informe para acomodar la parte práctica en sus capítulos
  y respetar su numeración, formato de figuras y tablas, y estilo de citas.
- Todo lo que sigue ocurrió y fue medido. **Usa solo estas cifras; no inventes datos, fechas ni resultados.**
  Si algo no está aquí, pregunta al autor.
- Los **espesores son sintéticos** (simulados): todavía no hay medidor de espesores. Preséntalos siempre así.
- El **tiempo de humectación** es un indicador de la sesión medida (31 min), **no** una clasificación anual de
  corrosividad ISO 9223.
- El **volumen LOD1** del edificio es una aproximación (±5 m en planta), no un levantamiento.
- Hora local = UTC−6. Coordenadas en WGS84; proyección UTM zona 14N (EPSG:32614).
- Las figuras vienen en la carpeta `figuras/` con el nombre indicado en la sección 11.
- Tono sugerido: técnico, en primera persona del plural o impersonal, en español de México.

### Estructura sugerida para la parte práctica (ajústala al índice del informe)

| Sección práctica sugerida | Contenido | De dónde sale (este documento) |
|---|---|---|
| Desarrollo de la caja negra | Hardware, conexiones, configuración de arranque y software (contrato de datos, integridad con `fsync`, banderas, hora GPS) | Secciones 2 y 3 · Figuras 1–3 |
| Pruebas de laboratorio (mesa) | Puesta en marcha del GPS y su falla de cableado, primer fix, pruebas de continuidad y cortes de energía | Fases 1 a 3 (sección 4) |
| Prueba de campo | Plan y ejecución de la captura con el dron, sesión de la caja negra, precisión del GPS | Fases 4 y 5 · Figuras 4, 5 y 10 |
| Procesamiento fotogramétrico | OpenDroneMap: dos corridas, problemas y ajustes, calidad obtenida | Fase 6 · Figuras 6–9 y 12 |
| Gemelo digital | Fusión de datos, humectación, espesores sintéticos (VC, VR), volumen LOD1, mapa y visor 3D | Fase 7 · Figuras 10, 11 y 13 |
| Resultados y discusión | Tabla de métricas, problemas y soluciones, limitaciones | Secciones 5, 6 y 7 |
| Conclusiones de las pruebas y trabajo futuro | Lecciones aprendidas y migración a ESP32-C3 | Secciones 8 y 9 · Figura 14 |

## 1. Resumen del proyecto (contexto; ya cubierto en la parte teórica del informe)

Una inspección de **Nivel 2** es **cuantitativa y georreferenciada**: cada lectura de un sensor queda asociada a
una posición y a una hora, y alimenta un **gemelo digital** del activo.

El proyecto tiene dos partes:

| Parte | Dónde corre | Qué hace |
|---|---|---|
| **Caja negra** | Raspberry Pi 3 Model B (1 GB, Debian 13 «Trixie») | Lee GPS y temperatura/humedad (DHT22), asocia cada lectura a posición y hora, la marca con banderas de calidad y la graba en CSV en la microSD (cómputo en el borde). |
| **Gemelo digital** | PC con Windows 11 (i5-8365U, 32 GB RAM) | Procesa las fotos del dron con OpenDroneMap (modelo 3D, nube de puntos, ortomosaico) y les superpone las lecturas de la caja negra; calcula indicadores (tiempo de humectación, velocidad de corrosión y vida remanente con espesores sintéticos). |

**Dron:** DJI Mini 4K (249 g, cámara de 12 MP, fotos 4000 × 3000 con GPS en el EXIF). No puede cargar la caja
negra, así que la caja se llevó **en mano** mientras el dron fotografiaba la estructura (validación en tierra).
El software no depende del modelo de dron: solo necesita fotos con GPS.

## 2. Hardware de la caja negra (Figuras 1 y 2)

| Componente | Modelo | Conexión a la Pi |
|---|---|---|
| Computadora | Raspberry Pi 3 Model B, 1 GB | Sin reloj de tiempo real: la hora confiable sale del GPS |
| GPS | GPS Shield Duinopeak (u-blox NEO-6M, antena externa SMA) | TX del GPS → pin 10 (GPIO15 RXD); 5 V pin 4; GND pin 6. 9600 baudios, NMEA |
| Temperatura y humedad | AM2302 / DHT22 | DATA → pin 7 (GPIO4); 3.3 V pin 1; GND pin 20. Leído con el driver del kernel (overlay `dht11`) cada 3 s |
| LED de estado | RGB KY-016 (previsto) | pines 11, 13, 15 y 14 — **no se instaló** (no se contó con la pieza) |
| Botón de apagado | KY-004 (previsto) | pin 5 (GPIO3) con overlay `gpio-shutdown` — **no se instaló** |
| Energía | Power bank USB 5 V | micro-USB |

Configuración de arranque aplicada (2026-11-21): `enable_uart=1`, `dtoverlay=disable-bt` (deja el UART completo
en GPIO14/15), `dtoverlay=dht11,gpiopin=4`, `dtoverlay=gpio-shutdown,...`; se quitó la consola serie de
`cmdline.txt`. Respaldos en `/boot/firmware/*.antes-cajanegra`.

## 3. Software de la caja negra (v0.2.1)

- Python, solo biblioteca estándar + `pyserial`, `pyyaml`, `gpiozero` (la Pi tiene 1 GB de RAM).
- Módulos: parser NMEA propio (GGA y RMC, con checksum), hilo lector del GPS, lector del DHT22, registro CSV,
  LED, modo simulado para probar en Windows (`python -m cajanegra --simular`).
- Bucle a 1 Hz: arma la fila con el último estado de cada sensor y la graba **con `flush()` y `fsync()` por fila**:
  un corte de energía pierde como máximo la última fila.
- Un archivo por encendido (`sesion_NNNN.csv`) + metadatos JSON.
- Hora oficial = **UTC del GPS**; sin fix, hora del sistema marcada en la columna `fuente_hora`.
- Servicio `systemd` con reinicio automático: la caja arranca y graba sola al conectar la energía.
- **38 pruebas automáticas** (pytest) pasan.

**Contrato de datos (CSV, una fila por segundo):** `sesion, seq, t_mono_s, utc, fuente_hora, lat, lon, alt_m,
fix, sats, hdop, temp_c, hr_pct, dht_edad_s, espesor_mm (reservado), banderas, version`.
Banderas: `SIN_FIX`, `DHT_ERROR`, `DHT_VIEJO`, `HORA_SISTEMA`, `HORA_NO_SINC` (reloj del sistema sin
sincronizar: la Pi retoma al arrancar la última hora guardada; el gemelo corrige esas filas con el reloj
monotónico).

## 4. Resultados por fase

### Fase 0 — Entorno ✅
Windows con VS Code, Git, Python, Docker Desktop + WSL2; Raspberry con SSH. Acceso remoto por SSH con llave
desde la PC (la Pi se conecta al hotspot de Windows).

### Fase 1 — Hardware en mesa ✅ (GPS y DHT22)
- **DHT22** funcionando desde el inicio.
- **GPS — problema y solución:** al conectarlo no llegaba ningún dato al puerto serie (`/dev/serial0`).
  Se descartó el software (UART bien configurado, permisos, servicio) y se verificó con los contadores de
  interrupciones del UART que no llegaba ninguna señal al pin 10. Con una foto del shield se identificó que el
  bloque de jumpers (`RX · DIGITAL · TX`, una fila por pin 7…0) manda, de fábrica, el **TX del GPS al pin 2** y
  el RX al pin 3; el cable estaba en el **pin 3** (la entrada del GPS). Al moverlo al pin 2 llegaron las tramas
  NMEA de inmediato (Figuras 2 y 3).
- **Primer fix al aire libre** (2026-11-23): a los **~4.5 min** de encender, 4 satélites, HDOP 4.7, `fix 2`
  (corrección diferencial SBAS); un minuto después, **6 satélites y HDOP 2.6**. Con fix, la hora del CSV pasa a
  ser la del GPS y las filas quedan sin banderas.
- No se instalaron el LED RGB ni el botón (no se contó con las piezas); se da por cerrada la fase sin ellos.

### Fase 2 — Software de la caja negra ✅
Ver sección 3.

### Fase 3 — Pruebas de mesa ✅ (2026-11-23)
- **1 hora continua** (3858 filas) sin saltos en el consecutivo ni filas corruptas.
- **5 cortes de energía de golpe:** el CSV se pudo leer siempre y no se perdieron filas.
- Arranque automático al conectar la energía.
- Script de verificación (`verificar_sesion.py`): **0 errores**.
- Problema encontrado: el widget de actualizaciones del escritorio lanzaba PackageKit ~1 min después de arrancar
  y trababa la microSD (huecos de hasta 8 s entre filas). Se quitó ese widget.

### Fase 4 — Validación en tierra ✅ (parcial, cerrada así)
- Se caminó con la caja alrededor de la estructura (sesión 27; Figura 10).
- **Precisión del GPS con la caja quieta 20 min** (1196 lecturas, 6.9 satélites, HDOP medio 1.41):
  el **50 % de las posiciones a ≤ 2.2 m** de la media y el **95 % a ≤ 5.0 m** (máximo 5.7 m).
- El recorrido de la caja coincide con el contorno del edificio en la imagen satelital.
- Se detectaron automáticamente 5 paradas en la caminata (14:48, 14:49, 14:50, 14:52 y 14:54).
- **No se hizo:** la comparación contra puntos de control de coordenadas conocidas ni la carcasa impresa en 3D
  (la caja se usó con los cables al aire, en un recipiente). Se dieron por cerradas así.

### Fase 5 — Captura fotográfica ✅ (2026-11-24, «estructura1», edificio de 2 pisos)
- **94 fotos** de 4000 × 3000 px, todas con GPS en el EXIF (14:24–14:51). Se excluyeron 26 fotos de una
  panorámica automática a 82 m (un solo punto de vista, media resolución).
- **Dos vueltas completas** alrededor del edificio, a ~25 m del centro: 40 fotos a 7.5–9.6 m sobre el punto de
  despegue (14:24–14:33) y 54 a ~0–1 m (14:38–14:51). Traslape adecuado entre fotos consecutivas (Figura 5).
- **Limitación importante:** **todas las fotos se tomaron con la cámara a 0° (horizontal)**, sin la órbita a
  −45° ni la pasada cenital (−90°) del plan, y muy cerca de muros blancos lisos (Figura 4).
- **Caja negra, sesión 27** (14:26–14:58, 31.5 min): **1891 filas, 0 errores**; fix desde la fila 7 (arranque en
  caliente); **99 % de las filas con posición**; 7.6 satélites y HDOP 1.36 en promedio (todas ≤ 5);
  temperatura 23.6–25.7 °C y humedad 47.8–80.8 % en el 100 % de las filas. Cronología: la caja quedó en el suelo
  durante el vuelo (14:27–14:48) y después se caminó alrededor del edificio (14:48–14:58, ~210 m a 0.34 m/s).

### Fase 6 — Modelo 3D con OpenDroneMap ✅ (Figuras 6–9, 12, 13)
OpenDroneMap 3.6.2 en Docker (WSL2), con 15.5 GB de RAM y 8 hilos para el contenedor.

| | Corrida 1 | **Corrida 2 (ajustada para fachadas)** |
|---|---|---|
| Fotos alineadas | 76 de 94 | **86 de 94** |
| Error de reproyección | 0.96 px | **0.84 px** |
| Diferencia contra el GPS del dron | 1.15 m | 1.53 m |
| Puntos de amarre (OpenSfM) | 17 587 | 29 656 |
| Nube densa | 3.1 millones de puntos | 3.4 millones de puntos |
| Malla texturizada | 172 648 caras | **432 610 caras** (+ modelo `.glb` de 6.5 MB) |
| Tiempo | 14 min (al reanudar) | 43 min |

- **Problema 1 — sin memoria:** la primera corrida falló en la etapa de malla («out of memory», código 137).
  Causa: con fotos horizontales la nube trae puntos del horizonte y su extensión era de millones de metros.
  Solución: `--auto-boundary` (recorta la reconstrucción a la zona de vuelo) y reanudar desde la etapa que falló
  (`--rerun-from odm_filterpoints`) sin repetir lo ya calculado.
- **Corrida 2:** `--feature-quality ultra --min-num-features 20000 --pc-quality high --mesh-size 400000
  --mesh-octree-depth 12 --gltf`. Mejoró la cobertura de muros (de 2 esquinas a 3 esquinas y buena parte de los
  muros oeste, norte y sur).
- **Ortomosaico (2 cm/px) y modelo digital de superficie (DSM):** se generaron, pero **salen deformados y no
  sirven como mapa** (Figuras 8 y 9): sin fotos hacia abajo no hay vista cenital que reconstruir. Por eso el
  gemelo usa la imagen satelital como fondo y la nube/malla para la geometría.
- Una computadora más potente solo lo haría más rápido; el límite es la cobertura de las fotos.

### Fase 7 — Gemelo digital ✅ (Figuras 10–13)
Python en Windows (numpy, pandas, geopandas, rasterio, pyproj, laspy, scipy, trimesh, folium, plotly).
**29 pruebas automáticas** pasan. Módulos:

1. **Fusión:** lee la sesión 27, corrige la hora de las filas sin hora confiable con el reloj monotónico
   (9 filas), descarta lecturas por bandera (sin fix: 15; error del DHT: 4; DHT viejo: 3) o HDOP > 5, y convierte
   a UTM 14N. Resultado: **1891 lecturas, 1876 con posición válida, 1884 con temperatura/humedad válidas.**
2. **Tiempo de humectación (criterio ISO 9223: HR > 80 % y T > 0 °C):** **0.2 % del tiempo** (3 s de 1884 s),
   solo al encender el sensor; temperatura media 24.4 °C, humedad media 53.8 %. Tarde seca. Se reporta también
   por zonas de 5 × 5 m (48 zonas).
3. **Espesores sintéticos, velocidad de corrosión (VC) y vida remanente (VR):** 30 puntos sobre los muros del
   modelo; espesor nominal 6.0 mm, 10 años de servicio antes de la campaña 1, campañas separadas Δt = 2 años,
   espesor mínimo requerido 3.0 mm, VC real de cada punto entre 0.05 y 0.20 mm/año.
   `VC = (t_ant − t_act) / Δt` y `VR = (t_act − t_req) / VC`.
   - **Sin ruido se recuperan exactamente** la VC y la VR conocidas (validación del cálculo).
   - Con ruido del medidor de **±0.05 mm**: error medio de VC 0.017 mm/año (**14 %**) y de VR 2.6 años (**17 %**).
   - Monte Carlo (200 repeticiones × 30 puntos por nivel):

   | Ruido del medidor | Error medio VC | Error relativo VC | Error medio VR | Error relativo VR | VR no calculable |
   |---|---|---|---|---|---|
   | 0 mm | 0 | 0 % | 0 | 0 % | 0 |
   | ±0.01 mm | 0.0034 mm/año | 3.1 % | 0.67 años | 3.4 % | 0 |
   | ±0.05 mm | 0.0169 mm/año | 15.6 % | 4.0 años | 19.3 % | 0 |
   | ±0.10 mm | 0.0338 mm/año | 31.1 % | 19.3 años | 74.8 % | 75 de 6000 |

   Conclusión: con campañas separadas 2 años, la resolución del medidor domina el error de la VR; con ±0.05 mm
   conviene separar más las campañas o usar un medidor más fino.
4. **Nube y volumen LOD1:** el suelo se mide junto al camino de la caja negra (moda de alturas de la nube); la
   nube se recorta a la estructura. **Volumen simplificado LOD1:** orientación tomada del recorrido de la caja
   (40.3°), muros = picos exteriores de puntos verticales, altura = percentil 90 de la nube dentro de la planta.
   Con la corrida 2: **37.5 × 30.0 m en planta y 5.8 m de altura**, que coincide con la azotea vista en el
   satélite (~38 × 30 m). Aproximado (±5 m); en el lado noroeste influyen árboles y un pasillo.
5. **Mapa web** (folium): satélite de fondo, recorrido de la caja coloreado por temperatura, humedad y
   humectación, puntos de espesor coloreados por VR y planta LOD1 (Figuras 10 y 11).
   Hallazgo: **los lados oeste y sur del edificio estaban ~1 °C más calientes** (~25.5 °C contra ~24.5 °C), lo que
   coincide con el sol de la tarde (la caminata fue de 14:48 a 14:58).
6. **Visor 3D** (plotly, HTML): malla texturizada de OpenDroneMap, volumen LOD1 semitransparente, lecturas de la
   caja negra a la altura a la que se cargó (~1.2 m) y puntos de espesor (Figura 13; comparación con la corrida 1
   en la Figura 12).

### Fase 8 — Verificación y documentación (este informe)
Métricas principales en la sección 5; evidencias en `docs/evidencias/` del repositorio.

## 5. Tabla resumen de métricas

| Métrica | Valor |
|---|---|
| Lecturas de la sesión de campo (27) | 1891 (1 Hz, 31.5 min), 0 errores de formato |
| Lecturas válidas para posición / ambiente | 1876 / 1884 |
| Lecturas descartadas por bandera | sin fix 15, error DHT 4, DHT viejo 3 (una fila puede tener varias) |
| Filas con hora corregida | 9 |
| Continuidad (prueba de mesa) | 1 h, 3858 filas sin saltos; 5 cortes de energía sin filas perdidas |
| Tiempo al primer fix (arranque en frío) | ~4.5 min al aire libre |
| Precisión del GPS (caja quieta) | 50 % ≤ 2.2 m, 95 % ≤ 5.0 m |
| Fotos del dron / alineadas | 94 / 86 (corrida 2) |
| Error de reproyección | 0.84 px |
| Malla texturizada | 432 610 caras |
| Volumen LOD1 | 37.5 × 30.0 × 5.8 m |
| Tiempo húmedo (ISO 9223, sesión) | 0.2 % |
| Error de VC / VR con ruido ±0.05 mm | 14 % / 17 % |
| Pruebas automáticas | 38 (caja negra) + 29 (gemelo), todas pasan |
| Masa de la caja negra | no medida |

## 6. Problemas encontrados y soluciones

| Problema | Causa | Solución |
|---|---|---|
| El GPS no entregaba datos | Cable en el pin 3 del shield (entrada del GPS) | Moverlo al pin 2 (salida, según los jumpers) |
| Huecos de hasta 8 s entre filas | PackageKit (actualizaciones) trababa la microSD | Quitar el widget de actualizaciones del escritorio |
| Hora mal en las primeras filas | La Pi no tiene RTC y retoma la última hora guardada | Bandera `HORA_NO_SINC` y corrección con el reloj monotónico en el gemelo |
| Docker no arrancaba («no virtualization available») | Los componentes de virtualización quedaron en cola detrás de actualizaciones de Windows | «Actualizar y reiniciar» desde Windows Update |
| OpenDroneMap sin memoria | Puntos del horizonte en la nube (fotos horizontales) | `--auto-boundary` y reanudar desde la etapa que falló |
| Ortomosaico y DSM deformados | Todas las fotos a 0° (sin vista hacia abajo) | Usar satélite de fondo y la nube/malla para la geometría; repetir la captura con −45° y −90° |
| Modelo 3D incompleto | Muros blancos lisos y fotos solo horizontales | Reproceso con más detalle (de 76 a 86 fotos) y volumen LOD1 para dar la forma |
| Nube de puntos con datos sueltos que deformaban la escala | Puntos lejanos de cielo y horizonte | Medir el suelo junto al camino de la caja y recortar la nube |

## 7. Limitaciones

- Las fotos solo horizontales impidieron obtener azotea, ortomosaico y DSM útiles.
- No se midió el error de posición contra puntos de control de coordenadas conocidas; la precisión reportada es
  la estática (caja quieta).
- Espesores sintéticos: validan el cálculo y la sensibilidad al ruido, no el estado real del edificio.
- Humectación de una sola sesión de 31 min: indicador, no clasificación de corrosividad.
- La caja negra se probó sin carcasa, sin LED de estado ni botón, y sin medir su masa.
- La caja va en mano (validación en tierra); el dron de 249 g no puede cargarla.

## 8. Lecciones aprendidas

1. En la captura, la órbita inclinada (−45°) y la pasada cenital (−90°) son indispensables para el mapa y la azotea.
2. Revisar el cableado contra el diagrama real del módulo (jumpers) antes de sospechar del software.
3. La hora y la integridad de los datos se diseñan desde el inicio: `fsync` por fila, banderas de calidad y reloj
   monotónico permitieron corregir y verificar todo después.
4. Procesar en una carpeta fuera de la sincronización de la nube (OneDrive) y conservar solo las salidas útiles.
5. Mejorar los ajustes del procesamiento ayuda (de 76 a 86 fotos alineadas), pero no sustituye una buena captura.

## 9. Trabajo futuro

- **Migración de la caja negra a ESP32-C3 Super Mini** con reloj de tiempo real DS3231 (pila de botón) y
  adaptador microSD (Figura 14), manteniendo el mismo contrato de datos para que el gemelo siga funcionando.
- Nueva captura con órbita a −45° y pasada cenital; puntos de control con coordenadas conocidas.
- Carcasa impresa en 3D, LED de estado y botón de apagado.
- Medidor de espesores real en lugar de datos sintéticos.

## 10. Repositorio

GitHub `Pardooo0/digital-twins` (rama `main`). Código de la caja negra en `caja-negra/`, gemelo en `gemelo/`,
evidencias en `docs/evidencias/` (índice en `docs/evidencias/README.md`), guía del proyecto en `CLAUDE.md`.

## 11. Figuras (carpeta `figuras/`) con pie sugerido

| Archivo | Pie sugerido |
|---|---|
| `Fig01_mapa_pines_caja_negra.png` | Mapa de pines de la caja negra sobre el conector GPIO de la Raspberry Pi 3. |
| `Fig02_cableado_gps_shield_pi.png` | Cableado del shield GPS a la Raspberry Pi: el TX del GPS sale por el pin 2 del shield (jumper TX–DIGITAL) hacia el pin 10 de la Pi. |
| `Fig03_jumpers_gps_shield.jpeg` | Bloque de jumpers del shield GPS (`RX · DIGITAL · TX`); el cable estaba en el pin 3, la entrada del GPS. |
| `Fig04_muestra_fotos_vuelta_alta.jpg` | Muestra de fotos de la vuelta alta: cámara horizontal y muy cerca de los muros. |
| `Fig05_fotos_consecutivas_traslape.jpg` | Fotos consecutivas de ambas vueltas, con traslape entre una y la siguiente. |
| `Fig06_docker_odm_procesando.png` | OpenDroneMap procesando las 94 fotos en Docker Desktop (8 núcleos). |
| `Fig07_odm_v2_posiciones_camaras.png` | Posiciones de cámara reconstruidas (corrida 2): dos vueltas alrededor del edificio. |
| `Fig08_ortomosaico_deformado.png` | Ortomosaico generado: deformado por la ausencia de fotos hacia abajo. |
| `Fig09_dsm_deformado.png` | Modelo digital de superficie: alturas incoherentes por la misma causa. |
| `Fig10_mapa_temperatura_recorrido.png` | Recorrido de la caja negra sobre la imagen satelital, coloreado por temperatura: lados oeste y sur más calientes. |
| `Fig11_mapa_gemelo_planta_lod1_espesores.png` | Mapa del gemelo: planta LOD1 (37.5 × 30 m), temperatura y puntos de espesor sintéticos coloreados por vida remanente. |
| `Fig12_visor3d_v1_malla.png` | Visor 3D con la malla de la corrida 1: solo dos esquinas reconstruidas. |
| `Fig13_visor3d_v2_gemelo.png` | Gemelo digital en 3D (corrida 2): malla texturizada, volumen LOD1, lecturas de la caja negra y espesores. |
| `Fig14_componentes_esp32_trabajo_futuro.jpeg` | Componentes para la migración: ESP32-C3 Super Mini, RTC DS3231 y adaptador microSD. |
| `Fig15_mapa_pines_esp32c3.png` | Mapa de pines de la caja negra con ESP32-C3 Super Mini sobre la placa de expansión (actualizado el 2026-11-26). |
| `Fig16_modulos_esp32_placa_expansion.jpeg` | Módulos de la caja negra con ESP32-C3: placa de expansión, DS3231, adaptador microSD, DHT22 y shield GPS. |

Avance de la migración a ESP32-C3 (texto listo para el informe): `avance_esp32_informe.md`.
