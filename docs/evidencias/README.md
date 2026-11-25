# Evidencias de las pruebas

Capturas, fotos y registros de cada prueba, para el informe de residencia. Los datos pesados (fotos del
dron, salidas de OpenDroneMap, CSV de la caja negra y los HTML del gemelo) no se suben a Git: están en
`gemelo/datos/` y `gemelo/salidas/`, y se regeneran con los comandos de `CLAUDE.md`.

## 2026-11-23 — GPS de la caja negra (fase 1)

| Archivo | Qué muestra |
|---|---|
| `01_gps_shield_conexion_inicial.jpeg` | Shield GPS Duinopeak (u-blox NEO-6M) conectado a la Pi: LED PWR encendido, antena SMA. |
| `02_gps_jumpers_cable_en_pin3.jpeg` | Bloque de jumpers `RX · DIGITAL · TX`: el cable estaba en el pin 3 (RX del GPS); el GPS habla por el pin 2. Al moverlo, llegaron las tramas NMEA y después el primer fix (ver `CLAUDE.md`, fase 1). |

## 2026-11-24 — Prueba de campo y gemelo digital (fases 5, 6 y 7), `estructura1`

| Archivo | Qué muestra |
|---|---|
| `00_componentes_migracion_esp32.jpeg` | Componentes para la migración futura: ESP32-C3 Super Mini, RTC DS3231 (ZS-042) y adaptador microSD. |
| `01_docker_odm_corriendo.png` | Docker Desktop con OpenDroneMap procesando las 94 fotos (8 núcleos). |
| `02_verificacion_caja_negra.txt` | Sesión 27: 1891 filas, 0 errores; línea de tiempo; precisión estática del GPS (50 % ≤ 2.2 m, 95 % ≤ 5.0 m); 5 paradas detectadas. |
| `03_revision_fotos.txt` | 94 fotos con GPS; dos vueltas completas; todas con la cámara a 0°. |
| `04_muestra_fotos_vuelta_alta.jpg`, `05_muestra_fotos_vuelta_baja.jpg` | Muestras de cada vuelta del dron. |
| `06_fotos_consecutivas_traslape.jpg` | Fotos consecutivas: traslape entre una y la siguiente. |
| `07_odm_vista_superior_camaras.png` | Vista superior de OpenSfM: posiciones de cámara alrededor del edificio. |
| `08_odm_grafo_coincidencias.png` | Grafo de coincidencias entre fotos. |
| `09_odm_estadisticas.json` | Estadísticas de OpenSfM: 76/94 fotos alineadas, reproyección 0.96 px. |
| `10_odm_corrida1_error_memoria.txt` | Problema: la 1.ª corrida se quedó sin memoria (puntos del horizonte). Solución: `--auto-boundary`. |
| `11_mapa_temperatura_satelite.png` | Recorrido de la caja negra sobre el satélite, coloreado por temperatura: los lados O y S más calientes (sol de la tarde). |
| `12_odm_reporte_calidad.pdf` | Reporte de calidad que genera OpenDroneMap. |
| `13_odm_corrida2_log_completo.txt` | Registro completo de la 2.ª corrida (exitosa). |
| `14_gemelo_salida_consola.txt` | Salida de los módulos del gemelo (fusión, humectación, espesores, volumen, mapa, visor). |
| `15_ortomosaico.png`, `16_modelo_elevacion_dsm.png` | Ortomosaico y DSM: deformados porque no hubo fotos hacia abajo (lección para la próxima captura). |
| `17_mapa_gemelo_satelite_espesores.png` | Mapa del gemelo: satélite, temperatura y puntos de espesor sintéticos (VR). |
| `18_visor3d_gemelo.png` | Visor 3D con la nube de puntos recortada. |
| `19_visor3d_malla_textura_v1.png` | Visor 3D con la malla texturizada de ODM (solo dos esquinas bien reconstruidas). |
| `20_visor3d_volumen_lod1_malla.png` | Visor 3D con el volumen simplificado (LOD1, 39.5 × 35.0 × 7.9 m), la malla y los datos. |
| `21_mapa_planta_lod1.png` | Planta LOD1 sobre el satélite (aproximada, ±5 m). |
| `22_volumen_lod1.json` | Medidas del volumen LOD1 y método (con la 1.ª corrida). |
| `23_odm_v2_reporte_calidad.pdf` | Reporte de calidad del reproceso v2 (ajustes para fachadas). |
| `24_odm_v2_estadisticas.json` | Estadísticas v2: 86/94 fotos alineadas, reproyección 0.84 px. |
| `25_odm_v2_vista_superior_camaras.png` | Vista superior de cámaras del reproceso v2. |
| `26_odm_v2_log_completo.txt` | Registro completo del reproceso v2. |
| `27_gemelo_v2_salida_consola.txt` | Salida del gemelo con la v2 (volumen LOD1: 37.5 × 30.0 × 5.8 m). |
| `28_visor3d_v2_malla_lod1.png` | Visor 3D con la v2: malla de 433 mil caras (tres esquinas y muros O, N y S), volumen LOD1 y datos. |
| `29_mapa_v2_planta_lod1.png` | Planta LOD1 de la v2 sobre el satélite: coincide con la azotea. |
| `30_esp32_m1_firmware_micropython.txt` | Migración, etapa M1: chip ESP32-C3 identificado, MicroPython 1.29.0 cargado, prueba del LED. |
| `31_esp32_m2_microsd.txt` | M2: microSD en el ESP32; 200 filas con `flush` + `sync` en 33.5 ms de media. |
| `32_esp32_m2_gps.txt` | M2: GPS en el ESP32, 82 frases NMEA válidas en 15 s; reloj y DHT22 sin 3.3 V. |
| `33_esp32_m2_sd_gps_dht.txt` | M2: microSD y GPS funcionando; DHT22 sin alimentación. |

## 2026-11-25 — Migración a ESP32-C3: programa completo (etapa M3)

| Archivo | Qué muestra |
|---|---|
| `02_esp32_m3_programa_completo.txt` | 153 pruebas en la PC; 60 filas en 59.2 s en el ESP32; RAM libre 142 KB; CSV del ESP32 verificado con 0 errores. |
| `sesiones_esp32/sesion_1001.csv`, `.json` | Primera sesión grabada por el ESP32 (bajo techo, sin DHT22 ni DS3231) y sus metadatos. |
