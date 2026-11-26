# Migración de la caja negra a ESP32-C3 (avance al 26 de noviembre de 2026)

> **Para insertar en el informe.** Va dentro de la parte práctica, después de la validación con la Raspberry Pi
> (o como el inicio del trabajo futuro, si el informe se entrega antes de las pruebas M4 y M5). Las figuras están en
> `figuras/`: Fig15 (mapa de pines) y Fig16 (fotografía de los módulos). Las cifras salen de la bitácora
> `migracion_esp32.md` y de las evidencias en `docs/evidencias/2026-11-24`, `2026-11-25` y `2026-11-26`.
> Ajusta la numeración de secciones, figuras y tablas a la del informe.

## Motivación

La caja negra con Raspberry Pi 3 cumplió las pruebas de mesa y de campo, pero mostró tres limitaciones para
llevarla a bordo de un RPAS. La primera es que no tiene reloj de tiempo real: al arrancar sin señal GPS retoma
la última hora guardada, por lo que las primeras filas de una sesión deben corregirse después (bandera
`HORA_NO_SINC`). La segunda es que tarda alrededor de 30 s en arrancar el sistema operativo y el servicio de
registro. La tercera es su tamaño (85 × 56 mm) y su consumo (~2.5 W en reposo), que obligan a usar un power
bank. Por ello se decidió sustituir solo la computadora por un microcontrolador **ESP32-C3 Super Mini**, con
un **reloj de tiempo real DS3231** de pila de respaldo y un **adaptador microSD**. Se conservan el shield GPS
(u-blox NEO-6M) y el sensor DHT22, así como el formato de los datos.

## Hardware

| Componente | Modelo | Función |
|---|---|---|
| Microcontrolador | ESP32-C3 Super Mini (RISC-V a 160 MHz, 400 KB de RAM, 4 MB de flash, 22 × 18 mm) | Ejecuta el programa de registro |
| Placa de expansión | *ESP32-C3 SuperMini Expansion Board* | Da a cada GPIO una tira señal · VCC · GND; trae conector y cargador para batería LiPo |
| Reloj de tiempo real | DS3231 en placa ZS-042 (con EEPROM AT24C32) | Conserva la hora UTC con su pila cuando no hay GPS |
| Almacenamiento | Adaptador microSD por SPI, tarjeta de 8 GB en FAT32 | Guarda los CSV de cada sesión |
| GPS | Shield Duinopeak con u-blox NEO-6M (sin cambio) | Posición y hora UTC, 9600 baudios, NMEA |
| Temperatura y humedad | AM2302 / DHT22 (sin cambio) | Lectura cada 3 s |

Las conexiones se muestran en la **Figura 15** y los módulos en la **Figura 16**. El GPS entrega sus datos al
GPIO20 (UART1). La microSD usa el bus SPI (GPIO4 a GPIO7). El reloj usa el bus I²C (GPIO0 y GPIO1) y el DHT22,
el GPIO3. Se evitaron los pines de arranque del ESP32-C3 (GPIO2, GPIO8 y GPIO9); el LED azul (GPIO8) y el botón
BOOT (GPIO9), que ya trae la placa, sirven como indicador de estado y para cerrar la sesión.

La alimentación se dividió según lo que necesita cada módulo. El reloj y el DHT22 trabajan a **3.3 V**, que
entregan las tiras rojas de la placa de expansión; en el caso del reloj, además, a 5 V el circuito de la ZS-042
intentaría recargar la pila CR2032, que no es recargable. La microSD y el GPS se alimentan con **5 V** desde el
pin 5V de la Super Mini, porque el regulador AMS1117 del adaptador microSD necesita más de 3.3 V a la entrada.

*Figura 15. Mapa de pines de la caja negra con ESP32-C3 Super Mini sobre la placa de expansión.*
*Figura 16. Módulos de la caja negra: ESP32-C3 en la placa de expansión, DS3231, adaptador microSD, DHT22 y shield GPS.*

## Software

El programa se escribió en **MicroPython 1.29.0**. Se eligió en lugar de C++ con Arduino porque es el mismo
lenguaje de la versión con Raspberry Pi y del gemelo digital, lo que permitió reutilizar el parser NMEA, las
banderas de calidad y el formato del registro. Además, la lógica que no usa hardware corre igual en la PC y puede
probarse con pytest.

El programa separa el acceso al hardware (`hardware.py`) de la lógica: el bucle principal, el parser NMEA, la
elección de la hora, el armado de las filas y el registro. Las decisiones principales fueron:

- **Bucle sin hilos** cada 20 ms: lee lo que llega del GPS, lee el DHT22 cada 3 s y graba una fila por segundo.
- **Hora de cada fila:** la del GPS si tiene menos de 3 s de antigüedad (`fuente_hora = gps`); si no, la del
  DS3231 (`rtc`). El reloj se ajusta con el GPS en el primer fix y después cada hora. Si el DS3231 perdió la hora
  (bandera interna OSF), la fila lleva `HORA_NO_SINC`.
- **Coordenadas con enteros:** MicroPython en el ESP32-C3 usa flotantes de precisión simple, que introducían
  errores de hasta ~0.5 m en la longitud. Las coordenadas se calculan en diezmillonésimas de grado.
- **Integridad:** cada fila se escribe con `flush()` y `os.sync()`. Un *watchdog* reinicia la placa si el programa
  se traba 30 s, y ante una falla se anota el error y se abre una sesión nueva.
- **Compatibilidad:** el CSV conserva las mismas columnas y banderas que la versión con Pi; solo se agregó el
  valor `rtc` en `fuente_hora`. Las sesiones se numeran desde `sesion_1001` para no repetir las de la Pi.

## Pruebas y resultados

| Etapa | Prueba | Resultado |
|---|---|---|
| M1. Herramientas | Carga de MicroPython 1.29.0 en el ESP32-C3 | Chip ESP32-C3 rev. 0.4, 4 MB de flash; 171 KB de RAM libres y 2 MB de flash para archivos |
| M2. microSD | 200 filas del tamaño real del CSV con `flush()` + `os.sync()` | 33.5 ms por fila en promedio (p95 43.2 ms, máx. 125.1 ms), ~3 % del ciclo de 1 s; sin pérdidas |
| M2. GPS | Lectura de la UART durante 15 s (bajo techo) | 82 frases NMEA válidas, 0 con checksum incorrecto |
| M2. Los cuatro módulos | Diagnóstico con la placa soldada y montada en la placa de expansión | DS3231 en 0x68 (EEPROM en 0x57); DHT22: 24.9 °C y 56.6 %; GPS: 15 frases en 3 s; microSD: 7.78 GB |
| M2. Reloj | Ajuste con la hora UTC de la PC | Sin bandera OSF; avanza 5 s en 5 s |
| M3. Pruebas en la PC | 153 pruebas con pytest, incluida una simulación del bucle completo | Todas pasan; el CSV simulado tiene 0 errores en el verificador |
| M3. Programa completo | Sesión 1003 con los cuatro módulos (bajo techo, sin fix) | 60 filas en 59.7 s; 142 KB de RAM libres; 119 frases GPS válidas y 0 incorrectas; 0 fallas del DHT22; 0 errores del reloj |
| M3. Compatibilidad | Verificador de sesiones de la caja con Pi sobre el CSV copiado de la microSD | 60 filas válidas, 0 errores, 0 avisos |

Con estos resultados, el ESP32-C3 genera el mismo CSV que la Raspberry Pi y el gemelo digital puede leerlo sin
cambios. Sin fix, todas las filas quedaron con la hora del reloj (`fuente_hora = rtc`) y solo la bandera
`SIN_FIX`. En la versión con Pi, en cambio, esa situación producía horas no confiables.

## Problemas encontrados y soluciones

| Problema | Causa | Solución |
|---|---|---|
| La microSD fallaba de forma intermitente | Placa sin pines soldados apoyada en la protoboard: contacto débil | Soldar tiras de pines y montar la placa en la placa de expansión |
| El reloj y el DHT22 no respondían, y sus líneas de datos parecían unidas entre sí | El VCC común de ambos quedó sin conexión: sus resistencias de pull-up unían las líneas y las llevaban a 0 | Asegurar la alimentación de 3.3 V; después el reloj respondió en sus direcciones correctas |
| El DHT22 no respondía | Causa probable: el mapa de pines mostraba el módulo como + · OUT · −, pero su serigrafía es GND · VCC · DAT | Conectarlo según la serigrafía; mapa corregido |
| La microSD no respondía con la placa de expansión | Causa probable: las tiras VCC de la placa dan 3.3 V, insuficientes para el regulador del adaptador | Alimentar la microSD y el GPS desde el pin 5V |
| Error de hasta ~0.5 m en las coordenadas | Flotantes de precisión simple en MicroPython | Conversión con enteros |
| El DS3231 marcaba el año 2000 | Reloj nunca puesto en hora (bandera OSF) | Ajuste con la hora UTC de la PC; con fix, el programa lo ajusta con el GPS |

## Trabajo pendiente

- **M4, pruebas de mesa:** 1 h de registro continuo y 5 cortes de energía, verificados con `verificar_sesion.py`.
- Comprobar que el DS3231 conserva la hora sin alimentación externa (pila de respaldo).
- Medir el consumo y la masa de la caja con ESP32-C3 y compararlos con la versión con Raspberry Pi.
- **M5, campo:** nueva captura fotográfica con la caja a bordo del dron (plan en `docs/plan_captura_dron_esp32.md`)
  y procesamiento de la sesión en el gemelo digital.
