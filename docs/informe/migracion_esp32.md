# Migración de la caja negra: de Raspberry Pi 3 a ESP32-C3

Bitácora técnica para el informe de residencia («Inspecciones de Nivel 2 y gemelos digitales mediante RPAS»).
Se actualiza en cada etapa: decisiones y su justificación, conexiones, pruebas, problemas y resultados.
Las cifras de la versión con Raspberry Pi están en `contexto_informe.md`.

**Estado (2026-11-25):** M1 ✅ · M2 parcial (microSD ✅, GPS ✅, DHT22 y DS3231 pendientes de soldar la placa y de la pila) · M3 ✅ programa completo funcionando en el ESP32 · siguen M4 (pruebas de mesa) y M5 (campo). Inicio: 2026-11-24.

## 1. Motivo de la migración

El 2026-11-24 se indicó migrar la caja negra de la Raspberry Pi 3 a un microcontrolador **ESP32-C3 Super Mini**
con un **reloj de tiempo real (RTC) DS3231** con pila de respaldo y un **adaptador microSD**. Se conservan el
shield GPS y el sensor DHT22. Ventajas técnicas esperadas frente a la Pi:

| Aspecto | Raspberry Pi 3 | ESP32-C3 + RTC + microSD |
|---|---|---|
| Hora sin GPS | La Pi no tiene RTC: al arrancar retoma la última hora guardada (bandera `HORA_NO_SINC`) | El DS3231 conserva la hora con su pila aunque se apague; se ajusta con el GPS |
| Arranque | ~30 s (sistema operativo Linux y servicio) | ~1 s: el programa corre al conectar la energía |
| Consumo | ~2.5 W en reposo | Del orden de 0.5 W con GPS (por medir) |
| Tamaño y masa | Placa de 85 × 56 mm | Placa de 22 × 18 mm |
| Riesgo de corrupción | Sistema de archivos de Linux + datos en la misma microSD | La microSD solo guarda datos; el programa vive en la memoria flash del ESP32 |
| Costo | Mayor | Menor |

## 2. Componentes

| Componente | Modelo | Notas |
|---|---|---|
| Microcontrolador | ESP32-C3 Super Mini | RISC-V de 160 MHz, 400 KB de RAM, 4 MB de flash, Wi-Fi y Bluetooth LE, USB-C nativo; LED azul en GPIO8 y botón BOOT en GPIO9 |
| Reloj de tiempo real | DS3231 en placa ZS-042 (con EEPROM AT24C32) | Oscilador compensado en temperatura (±2 ppm); bus I²C; pila de botón de respaldo |
| Almacenamiento | Adaptador microSD por SPI | Trae regulador AMS1117 a 3.3 V y adaptador de niveles; se alimenta con 5 V |
| GPS | Shield Duinopeak, u-blox NEO-6M (sin cambio) | Salida serie a 3.3 V por el pin 2 del shield, 9600 baudios, NMEA |
| Temperatura y humedad | AM2302 / DHT22 (sin cambio) | Lectura cada ≥ 2 s |

## 3. Decisiones y justificación

### 3.1 Lenguaje: MicroPython

No había restricción de lenguaje. Se eligió **MicroPython 1.29.0** (firmware `ESP32_GENERIC_C3`) frente a C++ con
el framework de Arduino:

| Criterio | MicroPython | Arduino (C++) |
|---|---|---|
| Continuidad con el proyecto | Mismo lenguaje que la caja negra en la Pi y el gemelo digital; se reutiliza la lógica del parser NMEA, de las banderas y del registro | Hay que reescribir todo |
| Pruebas automáticas | Los módulos sin hardware (parser NMEA, armado de filas y banderas) corren igual en la PC y se prueban con pytest, como exige el proyecto | Probar en la PC requiere un compilador y un entorno de pruebas aparte |
| Mantenimiento por el autor | Código legible y modificable sin compilar; consola interactiva (REPL) para depurar | Ciclo compilar-cargar más lento |
| Desempeño necesario | Suficiente: una fila por segundo y un DHT22 cada 3 s | Sobrado |
| Controladores disponibles | Incluidos: UART, I²C, SPI, `dht`; microSD con el controlador oficial `sdcard.py` de micropython-lib; DS3231 con un controlador propio de pocas líneas | Bibliotecas abundantes |

Riesgos de MicroPython y cómo se mitigan: pausas del recolector de basura (se llama `gc.collect()` en cada ciclo
y se evitan objetos grandes); bloqueos (se usa el *watchdog* del ESP32 para reiniciar si el programa se traba,
equivalente al `Restart=always` de systemd en la Pi); cortes de energía (cada fila se escribe con `flush()` y
`os.sync()`, como el `fsync` de la Pi).

### 3.2 Tarjeta microSD

Cada fila del CSV ocupa unos 120 bytes y se graba una por segundo: unos **0.43 MB por hora** (≈ 10 MB por día de
registro continuo). Por eso **cualquier tamaño sirve**: con 1 GB alcanza para unas 2 300 horas, y con 8 GB para
unas 19 000 horas (más de 2 años continuos).

El límite está en el **máximo y el formato**: MicroPython lee **FAT32**, no exFAT. Las tarjetas de hasta 32 GB (SDHC)
vienen en FAT32; las de más de 32 GB (SDXC) vienen en exFAT y habría que reformatearlas. Se usará una tarjeta de
≤ 32 GB en FAT32.

### 3.3 Sensores

Se conservan el shield GPS Duinopeak (NEO-6M) y el DHT22, con la misma configuración: el GPS entrega datos por el
pin 2 del shield (jumper TX–DIGITAL de fábrica). Solo cambia la computadora.

### 3.4 Hora oficial y contrato de datos

- Con fix, la hora oficial sigue siendo la **UTC del GPS**; además se **ajusta el RTC** con ella.
- Sin fix, se usa la hora del **RTC** (`fuente_hora = rtc`, valor nuevo en el contrato de datos). Si el RTC perdió
  la hora (pila agotada o primer uso), el DS3231 lo indica con su bandera interna `OSF` y la fila se marca
  `HORA_NO_SINC`, igual que en la Pi, para que el gemelo la corrija.
- El resto del CSV se conserva **igual** (mismas columnas y banderas), para que el gemelo digital lea los datos
  nuevos sin cambios. El único ajuste en el gemelo es aceptar `rtc` como hora confiable.

## 4. Conexiones

Mapa de pines: `docs/pines_esp32c3.svg` (en el informe: `figuras/Fig15_mapa_pines_esp32c3.png`). El ESP32-C3 se
monta en una protoboard; el pin 5V y el 3.3V alimentan rieles separados (5 V y 3.3 V) con GND común.

| Función | ESP32-C3 Super Mini | Módulo |
|---|---|---|
| GPS: datos (TX del GPS) | GPIO20 (RX de UART1) | Pin 2 del shield |
| GPS: alimentación | 5V y GND | 5V y GND del shield |
| microSD: reloj | GPIO4 (SCK) | SCK |
| microSD: datos de la tarjeta | GPIO5 (MISO) | MISO |
| microSD: datos a la tarjeta | GPIO6 (MOSI) | MOSI |
| microSD: selección | GPIO7 (CS) | CS |
| microSD: alimentación | 5V y GND | VCC y GND (el adaptador regula a 3.3 V) |
| RTC: datos I²C | GPIO1 (SDA) | SDA |
| RTC: reloj I²C | GPIO0 (SCL) | SCL |
| RTC: alimentación | **3.3V** y GND | VCC y GND |
| DHT22: datos | GPIO3 | OUT (DATA) |
| DHT22: alimentación | 3.3V y GND | + y − |
| LED de estado | GPIO8 | LED azul de la placa |
| Botón (cerrar sesión) | GPIO9 | Botón BOOT de la placa |

Notas de diseño:
- Se evitan los pines de arranque del ESP32-C3 (GPIO2, GPIO8 y GPIO9) para los módulos externos; GPIO8 y GPIO9
  solo se usan con el LED y el botón que ya trae la placa.
- El RTC se alimenta con **3.3 V**: la placa ZS-042 tiene un circuito que intenta recargar la pila; a 5 V una pila
  CR2032 (no recargable) se puede dañar, mientras que a 3.3 V la corriente de carga es prácticamente nula.
- El adaptador microSD se alimenta con **5 V** porque su regulador AMS1117 necesita más de 3.3 V a la entrada.
- La alimentación general sigue siendo un power bank por el USB-C del ESP32.

## 5. Plan por etapas

| Etapa | Qué se hace | Hecho cuando |
|---|---|---|
| M1. Herramientas | Instalar `esptool`, `mpremote` y MicroPython en el ESP32 | El LED de la placa parpadea desde MicroPython |
| M2. Módulos por separado | microSD, RTC, DHT22 y GPS, uno a la vez | Cada módulo responde por separado |
| M3. Programa completo | Registro a 1 Hz con el mismo CSV, banderas, sesiones, LED y botón | Genera un CSV válido y pasan las pruebas en la PC |
| M4. Pruebas de mesa | 1 h continua y 5 cortes de energía | `verificar_sesion.py` reporta 0 errores |
| M5. Campo y gemelo | Recorrido con GPS y lectura de los CSV en el gemelo digital | El gemelo procesa la sesión sin cambios |

## 6. Diseño del programa (etapa M3)

El programa está en `caja-negra-esp32/firmware/` y se copia a la flash del ESP32 con `scripts/cargar.ps1`.
Se separó lo que depende del hardware de la lógica, para poder probar la lógica en la PC:

| Archivo | Función | ¿Usa hardware? |
|---|---|---|
| `main.py` | Arranque al conectar la energía; modo mantenimiento; ante una falla, anota el error y reinicia la placa | Sí |
| `hardware.py` | Monta la microSD, abre la UART del GPS, el DHT22, el bus I²C del DS3231, el LED, el botón y el *watchdog* | Sí |
| `bucle.py` | Bucle principal: lee los sensores, arma una fila por segundo y la graba | No (recibe el hardware) |
| `nmea.py` | Parser NMEA (GGA, RMC) con checksum, adaptado del de la Pi | No |
| `gps.py` | Lector del GPS sin hilos: acumula los bytes de la UART y separa las frases | No |
| `dht_lector.py` | Lectura del DHT22 cada 3 s; conserva la última lectura válida | No |
| `reloj.py` | Decide la hora de cada fila (GPS, DS3231 o reloj interno) y ajusta el DS3231 con el GPS | No |
| `fila.py` | Arma la fila del CSV según el contrato de datos, con sus banderas | No |
| `registro.py` | Sesión por encendido en `/sd/datos/`; cada fila con `flush()` + `os.sync()` | Solo archivos |
| `tiempo.py` | Fechas y horas como milisegundos desde 1970 (MicroPython no trae `datetime`) | No |
| `led.py` | Patrones de parpadeo del LED azul | No |
| `ds3231.py`, `sdcard.py` | Controladores del reloj (propio) y de la microSD (micropython-lib) | Sí |
| `config.py` | Pines y tiempos | No |

Decisiones de diseño:

- **Sin hilos:** el bucle corre cada 20 ms. Lee lo que llegó del GPS a la UART (búfer de 2 KB), lee el DHT22 cada
  3 s, actualiza el LED y, cada segundo, arma y graba una fila. Es más simple y predecible que los hilos de la
  versión con Pi.
- **Coordenadas como enteros:** MicroPython en el ESP32-C3 usa flotantes de precisión simple. La longitud
  −101.1875398 se guardaba como −101.1875400, un error de hasta medio metro. Las coordenadas se convierten con
  enteros en diezmillonésimas de grado y se escriben con los mismos 7 decimales que la Pi.
- **Hora de cada fila:** si hay hora del GPS de hace ≤ 3 s, se usa (`gps`); si no, la del DS3231 (`rtc`); sin
  DS3231, el reloj interno (`sistema`). El DS3231 se ajusta con el GPS en el primer fix y luego cada hora. Se
  relee cada 10 min para corregir la deriva del reloj del ESP32. Si la hora no es confiable, la fila lleva
  `HORA_NO_SINC`.
- **Sesiones:** `/sd/datos/sesion_NNNN.csv` + `.json`, numeradas desde **1001** para no repetir los nombres de
  las sesiones de la Pi (llegaron a la 0028) en el gemelo. Al cerrar, el JSON guarda también cuántas frases del
  GPS llegaron, cuántas fallaron y cuántas lecturas del DHT22 fallaron.
- **LED azul** (un solo color, en lugar del LED RGB de la versión con Pi):

  | Patrón | Significado |
  |---|---|
  | Parpadeo muy rápido los primeros 2 s | Ventana para entrar a modo mantenimiento con el botón BOOT |
  | Parpadeo rápido | Arrancando (montando la microSD) |
  | Lento (0.5 s / 0.5 s) | Grabando, aún sin el primer fix |
  | Encendido fijo | Grabando con posición |
  | Destello corto cada 2 s | Grabando; se perdió el fix |
  | Doble destello | Error: un sensor no responde o falla la microSD |
  | Apagado | Sesión cerrada con el botón |

- **Botón BOOT:** presionado 1 s cierra la sesión (anota la hora de cierre y el número de filas) y la placa se
  duerme hasta que se reinicie o se desconecte. Sustituye al botón KY-004 de la versión con Pi.
- **Robustez:** si el programa se traba 30 s, el *watchdog* reinicia la placa. Si algo falla (p. ej. la microSD),
  se anota en `errores.txt` y la placa se reinicia a los 5 s con una sesión nueva. Equivale al `Restart=always`
  de systemd en la Pi.
- **Modo mantenimiento:** con el archivo `/mantenimiento` en la flash, o presionando BOOT en los primeros 2 s, la
  placa no graba y queda libre para cargar programas desde la PC.

Pruebas en la PC: **153 pruebas con pytest**. Incluyen una **simulación del bucle completo** (2 min con GPS sin
fix y luego con fix, DHT22 con fallas ocasionales y DS3231 sin hora al inicio) cuyo CSV se revisa con
`verificar_sesion.py` de la caja con Pi: 0 errores. Esto garantiza que el gemelo digital lee los datos del ESP32
igual que los de la Pi.

## 7. Bitácora

| Fecha | Etapa | Qué se hizo / resultado |
|---|---|---|
| 2026-11-24 | — | Se definieron el lenguaje (MicroPython), las conexiones, la tarjeta (≤ 32 GB, FAT32) y el manejo de la hora con RTC. |
| 2026-11-24 | M1 | Herramientas en la PC: esptool 5.7.0, mpremote 1.29.0 y pytest; firmware MicroPython 1.29.0 para ESP32-C3 y controlador `sdcard.py` descargados. |
| 2026-11-24 | M1 | La placa se conecta por USB-C y Windows la reconoce sin controladores (puerto serie USB nativo, COM9). Chip identificado: **ESP32-C3 (QFN32) revisión v0.4, 4 MB de flash, cristal de 40 MHz**. Se borró la flash (15 s) y se cargó MicroPython 1.29.0 (1.75 MB, 8 s, verificado). En MicroPython: 160 MHz, **171 KB de RAM libres** y **2 MB de flash para archivos**; se ejecutó la rutina de parpadeo del LED azul (GPIO8, activo en bajo), 10 veces (pendiente de confirmación visual). Evidencia: `docs/evidencias/2026-11-24/30_esp32_m1_firmware_micropython.txt`. |
| 2026-11-24 | M2 | microSD revisada en la PC: **8 GB (7.24 GB utilizables), FAT32, vacía**; no requiere formato. Se copió el controlador `sdcard.py` a la flash del ESP32. |
| 2026-11-24 | M2 | El ESP32-C3 se montó en protoboard. Se elaboró el mapa de pines (`docs/pines_esp32c3.svg`) con el orden real de la placa (5V · G · 3.3 · 4 · 3 · 2 · 1 · 0 de un lado; 5 · 6 · 7 · 8 · 9 · 10 · 20 · 21 del otro), rieles de 5 V y 3.3 V separados y el orden de conexión de los módulos. |
| 2026-11-24 | M2 | Primera prueba de la microSD (único módulo conectado), con la placa sin pines soldados apoyada en la protoboard: **la tarjeta no responde** («no SD card» a 100 kHz, 400 kHz y 1 MHz). Causa probable: falta de contacto de las orillas de la placa con la protoboard (ver sección 8). |
| 2026-11-24 | M2 | **microSD funcionando** tras reacomodar la placa y los cables: montada (7.78 GB, FAT32, clúster de 32 KB); **200 filas** del tamaño real del CSV grabadas con `flush()` + `os.sync()` en **33.5 ms de media** (mediana 30.6 ms, p95 43.2 ms, máximo 125.1 ms), es decir, ~3 % del ciclo de 1 s; releídas sin pérdidas (201 líneas). Evidencia: `docs/evidencias/2026-11-24/31_esp32_m2_microsd.txt`. Nota: una prueba previa de la línea MISO (CS = 0, esperando un 1) resultó no válida: la tarjeta no maneja esa línea hasta recibir su primer comando. |
| 2026-11-24 | M2 | Controlador propio del DS3231 (`caja-negra-esp32/firmware/ds3231.py`): lee y ajusta la hora en UTC (registros BCD), detecta la pérdida de hora (bandera OSF) y lee la temperatura interna del reloj. Las conversiones no dependen del hardware y se prueban en la PC: **111 pruebas con pytest** (incluye un DS3231 simulado). Script `scripts/ajustar_rtc.ps1` para poner el reloj en hora con la UTC de la PC. |
| 2026-11-24 | M2 | Con los cuatro módulos cableados (placa aún sin soldar): **GPS funcionando con el ESP32** — en 15 s llegaron 2358 bytes y **82 frases NMEA válidas, 0 con checksum malo** (GGA, RMC, GSA, GSV, VTG y GLL a 1 Hz), sin fix bajo techo como era de esperar. El reloj DS3231 y el DHT22 no respondieron: sus líneas (con resistencias hacia su VCC) se leían en 0, lo que indica que **no llegaban 3.3 V a su riel**; la microSD volvió a fallar. Se pospone hasta soldar pines a la placa. Evidencia: `docs/evidencias/2026-11-24/32_esp32_m2_gps.txt`. |
| 2026-11-24 | M2 | Recableado con microSD, GPS y DHT22 (reloj sin conectar: falta la pila): **microSD ✅** (tarjeta reconocida, 15 196 160 sectores = 7.78 GB) y **GPS ✅** (18 frases NMEA en 3 s). **DHT22 ❌**: su línea de datos se lee en 0 con pull-down (sin 3.3 V en el módulo o sin llegar a GPIO3) y en 1 con pull-up (sin corto a tierra). Evidencia: `docs/evidencias/2026-11-24/33_esp32_m2_sd_gps_dht.txt`. |
| 2026-11-25 | M3 | **Programa completo escrito** (13 módulos, sección 6) y **153 pruebas en la PC** que pasan, incluida la simulación del bucle completo. Contrato de datos actualizado (`fuente_hora = rtc`) y verificador de sesiones de la Pi adaptado: sus 40 pruebas siguen pasando, así que las sesiones viejas siguen siendo válidas. |
| 2026-11-25 | M3 | **Programa cargado al ESP32** y probado con la microSD y el GPS (DHT22 sin 3.3 V, DS3231 sin conectar, bajo techo): **60 filas en 59.2 s**; RAM libre de 171 KB al inicio a **142 KB** con el programa cargado y la microSD montada (141 KB al final); GPS: 118 frases válidas en 60 s; DHT22: 20 fallas de 20 (sin alimentación, como se esperaba). El **CSV generado por el ESP32 pasa el verificador de la caja con Pi: 60 filas válidas, 0 errores, 0 avisos**. Tras ajustar el inicio del ritmo de 1 s, la sesión 1002 grabó sus primeras filas en t = 0.35 s y 1.37 s. Evidencia: `docs/evidencias/2026-11-25/02_esp32_m3_programa_completo.txt` y `sesiones_esp32/sesion_1001.csv`. |

## 8. Problemas y soluciones

| Problema | Causa | Solución |
|---|---|---|
| La microSD no respondía («no SD card») | La placa **sin pines soldados** apoyada en la protoboard: sus orillas (medias perforaciones) están hechas para soldarse y el contacto es débil | Reacomodar la placa y los cables resolvió la prueba; para la caja definitiva se recomienda soldar tiras de pines, porque el contacto a presión puede fallar con vibración o al mover la caja |
| Con todo cableado, el reloj y el DHT22 no respondían y la microSD volvió a fallar; el GPS sí | Las líneas de los dos módulos del riel de 3.3 V se leían en 0 (sin energía), mientras que la del GPS (alimentado por el pin 5V) se leía en 1. Causas probables: el pin 3.3 sin contacto en la placa sin soldar, o el riel de la protoboard partido a la mitad | Soldar pines a la placa y revisar la continuidad del riel (pendiente) |
| Coordenadas con error de hasta ~0.5 m | MicroPython en el ESP32-C3 usa flotantes de precisión simple (24 bits de mantisa) | Convertir las coordenadas NMEA con enteros, en diezmillonésimas de grado |
| Las pruebas detectaron una latitud de 21.426° en lugar de 20.1426° | Un factor 10 de más en la conversión de minutos a grados con enteros | Corregido antes de cargar al ESP32; las pruebas comparan contra los valores de la Pi |
| El verificador de la Pi no se podía importar junto con el firmware | El bucle principal se llamaba `cajanegra.py`, igual que el paquete de la Pi | Se renombró a `bucle.py` |
| Las dos primeras filas quedaban a solo 0.32 s | Crear la sesión en la microSD tarda ~0.8 s y el ritmo de 1 s contaba desde antes | El ritmo empieza al terminar de crear la sesión |

## 9. Resultados

Pendiente (etapas M4 y M5).
