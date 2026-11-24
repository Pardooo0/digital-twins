# CLAUDE.md — Caja negra y gemelo digital (RPAS, inspección de Nivel 2)

Este archivo guía a Claude Code dentro de VS Code. Léelo completo antes de escribir código.

## 1. Contexto

Proyecto de residencia profesional (ITSUR, agosto–diciembre 2026): «Inspecciones de Nivel 2 y gemelos digitales mediante RPAS».
El Nivel 2 se define como una inspección **cuantitativa y georreferenciada**: cada lectura de un sensor se asocia a una posición y a una hora y alimenta un gemelo digital del activo.

El proyecto tiene dos partes que corren en máquinas distintas:

| Parte | Dónde corre | Qué hace |
|---|---|---|
| `caja-negra/` | Raspberry Pi 3 Model B (1 GB), Raspberry Pi OS ya instalado | Lee GPS y DHT22, asocia cada lectura a posición y hora, la marca con banderas de calidad y la graba en CSV en la microSD (cómputo en el borde). |
| `gemelo/` | PC con Windows | Procesa 50–100 fotos de una estructura con OpenDroneMap (modelo 3D y ortomosaico) y les superpone las lecturas de la caja negra; calcula indicadores (tiempo de humectación, velocidad de corrosión y vida remanente con espesores sintéticos). |

**Captura de fotos:** las pruebas usan un DJI Mini 4K (249 g). Ese dron **no puede cargar la caja negra**, así que la caja se lleva **en mano** mientras el dron fotografía la estructura (validación en tierra). El código no debe depender del modelo de dron: solo necesita fotos con GPS en el EXIF.

## 2. Hardware de la caja negra

| Componente | Modelo | Conexión a la Pi | Notas |
|---|---|---|---|
| Computadora | Raspberry Pi 3 Model B, 1 GB | — | Sin reloj de tiempo real: la hora confiable sale del GPS. |
| GPS | GPS Shield Duinopeak (para Arduino) | UART: TX del GPS → pin 10 (GPIO15 RXD); RX del GPS ← pin 8 (GPIO14 TXD, opcional); 5V pin 4; GND pin 6 | Si el TX mide 5 V, usar divisor 1 kΩ / 2 kΩ. 9600 baudios, NMEA. |
| Temperatura y humedad | AM2302 / DHT22 (módulo de 3 pines) | DATA → pin 7 (GPIO4); VCC pin 1 (3.3 V); GND pin 20 | Leer cada ≥ 2 s. Se lee con el driver del kernel (overlay `dht11`, que también soporta DHT22). |
| LED de estado | LED RGB KY-016 (cátodo común) | R pin 11 (GPIO17), G pin 13 (GPIO27), B pin 15 (GPIO22), − pin 14 | 220 Ω en serie si la placa no trae resistencias. |
| Botón | KY-004 | S pin 5 (GPIO3), − pin 9 | Lo maneja el overlay `gpio-shutdown`: apaga y también enciende la Pi. No requiere código. |
| Energía | Power bank USB 5 V / 2.4 A (pruebas en mano) | micro-USB | Más adelante: LiPo 2S + regulador 5 V / 3 A si se monta en un dron con capacidad de carga. |

El mapa de pines está en `docs/pines_caja_negra.svg`. **Nunca** conectar a un GPIO una señal de 5 V.

## 3. Estructura del repositorio

```
rpas-nivel2/
├── CLAUDE.md
├── docs/
│   ├── pines_caja_negra.svg
│   ├── cableado_gps.svg        # shield GPS → Pi (jumpers, pin 2, divisor)
│   └── evidencias/<fecha>/     # capturas y registros de cada prueba (para el informe)
├── caja-negra/                 # corre en la Raspberry Pi
│   ├── cajanegra/
│   │   ├── __init__.py         # __version__
│   │   ├── __main__.py         # punto de entrada: python -m cajanegra
│   │   ├── config.py           # carga config.yaml con valores por defecto
│   │   ├── nmea.py             # parser NMEA propio (GGA, RMC) con checksum
│   │   ├── gps.py              # hilo lector del puerto serie
│   │   ├── dht.py              # lectura del DHT22 vía /sys/bus/iio
│   │   ├── led.py              # estados del LED RGB (gpiozero)
│   │   ├── registro.py         # CSV por sesión + metadatos JSON, fsync por fila
│   │   └── simulado.py         # fuentes falsas de GPS y DHT22 para probar en Windows
│   ├── config.yaml
│   ├── requirements.txt        # pyserial, pyyaml (gpiozero viene del sistema)
│   ├── systemd/cajanegra.service
│   ├── scripts/
│   │   ├── instalar.sh         # se ejecuta en la Pi
│   │   ├── deploy.ps1          # se ejecuta en Windows: copia el código y reinicia el servicio
│   │   └── descargar.ps1       # se ejecuta en Windows: baja los CSV a gemelo/datos/cajanegra
│   └── tests/
│       ├── datos/ejemplo.nmea
│       ├── test_nmea.py
│       └── test_registro.py
└── gemelo/                     # corre en Windows
    ├── requirements.txt
    ├── config.yaml
    ├── datos/
    │   ├── fotos/<proyecto>/images/      # fotos del dron o del celular
    │   ├── odm/<proyecto>/               # salida de OpenDroneMap
    │   └── cajanegra/                    # CSV descargados de la Pi
    ├── gemelo/
    │   ├── odm.py              # lanza ODM con Docker y valida salidas
    │   ├── fusion.py           # CSV → puntos UTM con altura del DSM
    │   ├── humectacion.py      # tiempo de humectación (ISO 9223)
    │   ├── nube.py             # lee la nube de ODM, mide el suelo y la recorta a la estructura
    │   ├── espesores.py        # espesores sintéticos, VC y VR
    │   ├── mapa.py             # mapa web (folium) sobre el ortomosaico
    │   └── visor3d.py          # visor 3D en HTML (plotly) con el modelo y las capas
    ├── salidas/
    └── tests/
```

## 4. Reglas para Claude

1. **Trabaja fase por fase** (sección 6). Al terminar una fase, di qué probar y espera a que el usuario confirme el resultado en el hardware antes de pasar a la siguiente.
2. **Nada de lo que corre en la Pi puede usar pandas, numpy, geopandas ni librerías pesadas.** Solo la biblioteca estándar, `pyserial`, `pyyaml` y `gpiozero`. La Pi tiene 1 GB de RAM.
3. Todo el código de la caja negra debe poder ejecutarse en Windows con `python -m cajanegra --simular` (sin GPIO ni puerto serie) para probar la lógica sin la Pi.
4. **No edites `config.txt` ni `cmdline.txt` de la Pi sin mostrar antes el cambio exacto** y explicar cómo revertirlo. Un error ahí puede impedir que arranque.
5. Antes de usar una ruta de arranque, comprueba la versión del sistema: en Bookworm es `/boot/firmware/config.txt`; en versiones anteriores, `/boot/config.txt`. Revisa con `cat /etc/os-release`.
6. Cada fila del CSV se escribe con `flush()` y `os.fsync()`: un corte de energía debe perder como máximo la última fila.
7. Usa la hora del GPS (UTC) como hora oficial. Si no hay fix, registra la hora del sistema y márcalo en la columna `fuente_hora`.
8. Escribe pruebas con `pytest` para el parser NMEA, el registro CSV y los cálculos del gemelo.
9. Comentarios y mensajes al usuario en español. Nombres de variables en español sin acentos.
10. El contrato de datos (sección 7) no cambia sin avisar, porque el gemelo depende de él.

## 5. Cómo trabajar con la Raspberry desde VS Code (opciones)

La Pi y la PC deben estar en la misma red Wi-Fi (o la PC conectada al hotspot de la Pi, ver opción E). Primero, en la Pi: `sudo raspi-config` → *Interface Options* → *SSH* → habilitar; y opcionalmente cambiar el hostname a `cajanegra`. Desde Windows (PowerShell ya trae `ssh` y `scp`): `ssh pi@cajanegra.local` (cambia `pi` por tu usuario).

**A. Recomendada — programar en Windows y desplegar con un script.**
Claude Code y VS Code corren en la PC; el código se prueba con `--simular`; `scripts/deploy.ps1` copia `caja-negra/` a la Pi con `scp` y reinicia el servicio por `ssh`. Es la opción más rápida, porque la Pi no carga el editor. Configura una llave SSH (`ssh-keygen` y luego copiar la llave pública a `~/.ssh/authorized_keys` en la Pi) para no escribir la contraseña cada vez.

**B. VS Code Remote-SSH directo en la Pi.**
Extensión *Remote - SSH*: abres la carpeta de la Pi como si fuera local. Útil para depurar con el hardware conectado. En una Pi 3 de 1 GB funciona, pero lento; cierra la sesión cuando no la uses. No instales Claude Code en la Pi.

**C. Git.**
Repositorio privado en GitHub: haces `push` desde Windows y `git pull` en la Pi por SSH. Deja historial de versiones, útil para documentar el avance 2.

**D. Extensión SFTP de VS Code.**
Sube automáticamente cada archivo al guardarlo. Cómoda, pero es fácil dejar la Pi con código a medias.

**E. En campo sin Wi-Fi.**
La Pi crea su propia red: `sudo nmcli device wifi hotspot ssid CajaNegra password <clave>` (Bookworm con NetworkManager). La PC o el celular se conectan a esa red para descargar los datos. Alternativa: compartir datos del celular y conectar ahí la Pi y la laptop.

Descarga de datos: `scp -r pi@cajanegra.local:~/cajanegra/datos/* .\gemelo\datos\cajanegra\` (lo automatiza `scripts/descargar.ps1`).

## 6. Fases

### Fase 0 — Entorno
- Windows: VS Code, Git, Python 3.11, Claude Code, Docker Desktop con WSL2 (para ODM).
- Pi: SSH habilitado, `sudo apt update && sudo apt full-upgrade`, `sudo apt install -y python3-venv python3-gpiozero python3-serial git`.
- Crear la estructura de carpetas de la sección 3.
- **Hecho cuando:** `ssh pi@cajanegra.local` funciona desde PowerShell y `python --version` responde en ambas máquinas.

### Fase 1 — Hardware en mesa
1. Con todo apagado, alimentar solo el shield GPS y **medir el voltaje del pin TX del GPS** respecto a GND. Si es ~5 V, armar el divisor 1 kΩ / 2 kΩ; si es ~3.3 V, conexión directa.
2. Revisar en el shield qué pines del Arduino usan TX y RX del GPS (jumpers o interruptor). Conectar desde esos pines.
   **Resultado (2026-11-23):** en el shield Duinopeak (u-blox NEO-6M) el bloque de jumpers tiene columnas `RX | DIGITAL | TX` y una fila por pin (7…0). De fábrica, TX–DIGITAL está en el **2** (el GPS habla por el pin 2) y RX–DIGITAL en el 3. El cable al pin 10 de la Pi sale del **pin 2** del conector digital; en el 3 no llega nada. Mapa: `docs/cableado_gps.svg`.
3. Cablear según `docs/pines_caja_negra.svg`.
4. Configuración de arranque (mostrar al usuario antes de aplicar). Agregar al final de `config.txt`:
   ```
   enable_uart=1
   dtoverlay=disable-bt
   dtoverlay=dht11,gpiopin=4
   dtoverlay=gpio-shutdown,gpio_pin=3,active_low=1,gpio_pull=up
   ```
   Quitar `console=serial0,115200` de `cmdline.txt` (o en `raspi-config`: *Serial Port* → login shell **No**, hardware **Sí**). Ejecutar `sudo systemctl disable hciuart` (en Trixie ese servicio ya no existe: omitirlo) y reiniciar. **Aplicado el 2026-11-21** en la Pi (Debian 13 Trixie); respaldos en `/boot/firmware/*.antes-cajanegra`.
   `disable-bt` deja el UART completo en GPIO14/15 (`/dev/serial0`) a cambio de desactivar Bluetooth, que no se usa.
5. Pruebas por separado:
   - GPS: `cat /dev/serial0` debe mostrar líneas `$GPGGA` / `$GPRMC`. Al aire libre, el fix tarda de 1 a 5 min en arranque en frío.
     **Resultado (2026-11-23):** primer fix al aire libre a los ~4.5 min de encender (sesión 23, fila 276): 4 satélites, HDOP 4.7, `fix 2` (diferencial SBAS); al minuto, 6 satélites y HDOP 2.6. Con fix, `fuente_hora` pasa a `gps` y la fila queda sin banderas.
   - DHT22: `cat /sys/bus/iio/devices/iio:device0/in_temp_input` (milésimas de °C) y `in_humidityrelative_input` (milésimas de %). Si da error de E/S, reintentar: es normal que alguna lectura falle.
   - LED: prueba con `gpiozero.RGBLED(17, 27, 22)`.
   - Botón: con la Pi encendida, presionar → se apaga; presionar de nuevo → enciende.
- **Hecho cuando:** los cuatro componentes responden por separado.

### Fase 2 — Software de la caja negra
Módulos de la sección 3, en este orden: `nmea.py` (con pruebas) → `gps.py` → `dht.py` → `registro.py` (con pruebas) → `led.py` → `__main__.py` → `simulado.py`.
- Hilo del GPS: lee continuamente y guarda el último estado (fix, lat, lon, alt, satélites, HDOP, hora UTC).
- DHT22: cada 3 s (configurable); si falla, conserva la última lectura válida con su antigüedad y marca la bandera.
- Bucle principal a 1 Hz: arma la fila con el último estado de cada sensor y la graba.
- Sesión: un archivo por encendido, `datos/sesion_NNNN.csv` (contador guardado en `datos/estado.json`) + `sesion_NNNN.json` con metadatos (versión, configuración, hora GPS del primer fix, hora de cierre).
- LED: azul parpadeando = arrancando o buscando satélites; amarillo (R+G) = grabando sin fix; verde = grabando con fix; rojo = error de sensor o de escritura; apagado = detenido.
- `systemd/cajanegra.service`: `Restart=always`, usuario normal, `WorkingDirectory` en `~/cajanegra`. `scripts/instalar.sh` crea el venv con `--system-site-packages`, instala requisitos y habilita el servicio.
- **Hecho cuando:** `python -m cajanegra --simular` genera un CSV válido en Windows y las pruebas pasan.

### Fase 3 — Pruebas de mesa
- 1 hora continua grabando: el consecutivo no salta y no hay filas corruptas.
- Desconectar la energía de golpe 5 veces: al volver, el CSV se puede leer y solo falta como máximo la última fila.
- Arranque automático al conectar la energía; apagado con el botón.
- **Hecho cuando:** un script de verificación (`tests/verificar_sesion.py`) reporta 0 errores en los CSV.
- **Resultado (2026-11-23, solo DHT22):** 1 h continua (3858 filas), 5 cortes de energía sin filas perdidas ni corruptas, arranque automático, 0 errores. Pendiente: apagado con el botón.
- **Ajuste aplicado en la Pi:** el widget `updater` del panel del escritorio lanzaba PackageKit ~1 min después de arrancar y trababa la microSD (huecos de hasta 8 s entre filas). Se quitó en `~/.config/wf-panel-pi/wf-panel-pi.ini` (sección `[panel]`, `widgets_right` del sistema sin `updater`); respaldo en `wf-panel-pi.ini.antes-cajanegra`. Revertir: borrar ese archivo y reiniciar. Actualizar a mano con `sudo apt update && sudo apt full-upgrade`.

### Fase 4 — Carcasa y validación en tierra
- Carcasa en impresora 3D con ventilación lateral para el DHT22 (lejos del calor de la Pi), antena GPS con vista al cielo, LED visible y botón accesible.
- Caminar con la caja alrededor de la estructura y pasar por 3–5 puntos de control fáciles de ubicar (esquinas, postes). Comparar con sus coordenadas en Google Earth.
- **Hecho cuando:** se tiene el error medio de posición en metros y una sesión completa alrededor de la estructura.

### Fase 5 — Captura fotográfica
- 50–100 fotos de la estructura con el dron: dos órbitas (una más alta mirando a 45° hacia abajo y otra más baja, casi horizontal), con 70–80 % de traslape entre fotos consecutivas. Evitar contraluz y reflejos; mejor día nublado.
- Revisar en Windows (Propiedades → Detalles) que las fotos traen latitud y longitud.
- La caja negra va encendida en mano, recorriendo el perímetro durante el vuelo.
- Respaldo si no hay vuelo: fotos con el celular caminando alrededor, con la ubicación de la cámara activada.
- **Hecho cuando:** las fotos están en `gemelo/datos/fotos/<proyecto>/images/` y el CSV de la sesión en `gemelo/datos/cajanegra/`.
- **Resultado (2026-11-24, `estructura1`, edificio de 2 pisos):** 94 fotos 4000×3000 con GPS (DJI_0254–0347), dos vueltas completas a ~25 m del centro, una a ~8 m y otra a ~1 m sobre el punto de despegue, pero **todas con la cámara a 0°** (sin fotos a −45° ni cenitales) y muy cerca de muros blancos lisos. Caja negra: sesión 27 (14:26–14:58, 1891 filas, 0 errores); con la caja quieta 20 min, el 50 % de las posiciones a ≤ 2.2 m y el 95 % a ≤ 5.0 m. **Lección:** sin fotos inclinadas o hacia abajo no hay ortomosaico ni DSM útiles; en la próxima captura incluir la órbita a −45° y la pasada cenital.

### Fase 6 — Modelo 3D con OpenDroneMap (Windows)
```
docker run -d --name odm_<proyecto> -v C:/odm:/datasets opendronemap/odm --project-path /datasets <proyecto> --dsm --orthophoto-resolution 2 --auto-boundary
```
Se procesa en `C:\odm\<proyecto>\images\` (copia de las fotos), **fuera de OneDrive**: ODM genera ~2.5 GB de temporales que OneDrive intentaría sincronizar. Al terminar se copian a `gemelo/datos/odm/<proyecto>/` solo las salidas usadas: `odm_orthophoto/odm_orthophoto.tif`, `odm_dem/dsm.tif`, `odm_texturing/` (`odm_textured_model_geo.obj` y texturas), `odm_georeferencing/odm_georeferenced_model.laz` y `odm_report/report.pdf`. Alternativa con interfaz gráfica: WebODM. Con 8 GB de RAM, usar `--max-concurrency 2` si se queda sin memoria.
`--auto-boundary` recorta la reconstrucción a la zona de vuelo: sin él, con fotos casi horizontales la nube trae puntos del horizonte y ODM se queda sin memoria al hacer la malla (código 137). Para retomar una corrida desde una etapa: `--rerun-from <etapa>` (p. ej. `odm_filterpoints`).
- **Hecho cuando:** existe el ortomosaico georreferenciado y el modelo texturizado abre en un visor.
- **Resultado (2026-11-24, `estructura1`):** ODM 3.6.2 alineó 76 de 94 fotos en un solo modelo (reproyección 0.96 px, diferencia con el GPS del dron 1.15 m); nube de 3.1 M puntos con las fachadas. La 1.ª corrida falló por memoria y se resolvió con `--auto-boundary --rerun-from odm_filterpoints` (14 min). Por las fotos a 0°, el ortomosaico (2 cm/px) y el DSM salen deformados y **no sirven como mapa**; el gemelo usa el satélite como fondo y la nube de puntos para la geometría.

### Fase 7 — Gemelo digital (Python en Windows)
Entorno: `python -m venv .venv` y `pip install numpy pandas geopandas shapely pyproj rasterio laspy scipy plotly folium pyyaml pytest`.
1. `fusion.py`: leer los CSV, descartar filas con bandera de error o HDOP > 5, convertir lat/lon al sistema UTM del ortomosaico (Uriangato está en la zona 14N, EPSG:32614; tomarlo del CRS del ráster) y asignar a cada punto la altura del DSM.
2. `humectacion.py`: marcar cada lectura como «húmeda» si HR > 80 % y T > 0 °C (criterio de tiempo de humectación de la ISO 9223). Reportar la fracción del tiempo húmedo por zona. Es un indicador de la sesión, **no** una clasificación anual de corrosividad.
3. `espesores.py`: generar puntos sobre el modelo con espesores sintéticos de dos campañas con una velocidad de corrosión conocida; calcular `VC = (t_ant − t_act) / Δt` y `VR = (t_act − t_req) / VC`; comprobar que se recupera el valor conocido y reportar el error al agregar ruido de medición (por ejemplo ±0.05 mm).
4. `mapa.py`: mapa web con el ortomosaico, las lecturas (temperatura, humedad, humectación) y los puntos de espesor.
5. `visor3d.py`: modelo 3D en HTML con plotly y las capas de puntos coloreadas por variable.
- **Hecho cuando:** `salidas/` contiene el mapa HTML, el visor 3D HTML y un CSV de resultados por punto.
- **Entorno:** el venv va **fuera de OneDrive** (se usa `C:\Users\<usuario>\.venvs\gemelo`) con `pip install -r gemelo/requirements.txt`; `laspy[lazrs]` es necesario para leer el `.laz` de ODM. `gemelo/config.yaml` elige las sesiones del proyecto (`sesiones: [sesion_0027]`) y los parámetros de cada módulo. `nube.py` mide el suelo junto al camino de la caja negra y recorta la nube (lo usan `espesores.py` y `visor3d.py`).
- **Resultado (2026-11-24, `estructura1`):** 26 pruebas pasan. Fusión: 1891 lecturas, 1876 con posición válida, 1884 con T/HR válidas, 9 con hora corregida. Humectación: 0.2 % del tiempo húmedo (tarde seca). Espesores sintéticos (30 puntos, Δt = 2 años, ruido ±0.05 mm): error medio de VC 14 % y de VR 17 % (2.6 años); con ±0.10 mm la VR deja de ser estimable en algunos casos. Salidas: `mapa.html`, `visor3d.html`, `lecturas_fusionadas.csv`, `humectacion_por_*.csv`, `espesores_por_punto.csv`, `espesores_ruido.csv`. Evidencias (capturas y registros) en `docs/evidencias/2026-11-24/`.

### Fase 8 — Verificación y documentación
- Métricas: lecturas totales, válidas y descartadas por bandera; continuidad; error de posición contra puntos de control; error de VC y VR contra los valores sintéticos; masa de la caja negra.
- Capturas del mapa y del visor 3D para el informe (segundo avance).

## 7. Contrato de datos (CSV de la caja negra)

Separador coma, UTF-8, una fila por segundo, encabezado en la primera línea.

| Columna | Tipo | Descripción |
|---|---|---|
| `sesion` | texto | `sesion_NNNN` |
| `seq` | entero | Consecutivo desde 1 |
| `t_mono_s` | real | Segundos desde el arranque (reloj monotónico) |
| `utc` | texto ISO 8601 | Hora UTC |
| `fuente_hora` | `gps` / `sistema` | Origen de `utc` |
| `lat`, `lon` | real (grados, WGS84) | Vacío si no hay fix |
| `alt_m` | real | Altitud GPS |
| `fix` | entero | Calidad del fix de GGA (0 = sin fix) |
| `sats` | entero | Satélites en uso |
| `hdop` | real | Dilución horizontal de precisión |
| `temp_c` | real | Temperatura del DHT22 |
| `hr_pct` | real | Humedad relativa del DHT22 |
| `dht_edad_s` | real | Antigüedad de la última lectura válida del DHT22 |
| `espesor_mm` | real | Vacío por ahora; reservado para el medidor de espesores |
| `banderas` | texto | Separadas por `;`: `SIN_FIX`, `DHT_ERROR`, `DHT_VIEJO`, `HORA_SISTEMA`, `HORA_NO_SINC` (desde v0.2.0) |
| `version` | texto | Versión del software |

`HORA_NO_SINC` (v0.2.0) solo aparece junto con `HORA_SISTEMA`: el reloj del sistema no está sincronizado por NTP y su hora puede estar muy mal. La Pi no tiene RTC y al arrancar retoma la última hora guardada (en la sesión 3 del 2026-11-23 las primeras 23 filas quedaron con la hora de la noche anterior). El gemelo debe corregir esas filas con `t_mono_s`, tomando como ancla la primera fila de la sesión con hora confiable (`gps`, o `sistema` sin `HORA_NO_SINC`): `utc = utc_ancla − (t_mono_ancla − t_mono_s)`. Si ninguna fila de la sesión es confiable, su hora no sirve.

Ejemplo de `config.yaml` de la caja negra:
```yaml
puerto_gps: /dev/serial0
baudios_gps: 9600
periodo_registro_s: 1.0
periodo_dht_s: 3.0
dht_max_edad_s: 10.0
ruta_iio_dht: /sys/bus/iio/devices/iio:device0
carpeta_datos: datos   # relativa a config.yaml: ~/cajanegra/datos en la Pi
led: {r: 17, g: 27, b: 22}
```
