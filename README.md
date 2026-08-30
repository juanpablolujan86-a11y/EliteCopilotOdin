# ODIN

**Orbital Data Intelligence Nexus** es un copiloto modular para
Elite Dangerous. Observa el Journal del juego, conserva el estado del
comandante y coordina oficiales especializados mediante un EventBus.

## Estado actual

Versión actual: **v0.8.0-beta — MÍMIR, HEIMDALL, FREYJA y BROKK beta**.

## Instalación para comandantes de prueba

El instalador de Windows copia ODIN en el perfil del usuario, crea accesos
directos y deja configuradas por defecto voces Edge en español para ODIN,
MÍMIR, HEIMDALL y FREYJA. Durante la instalación ofrece, como opción marcada
pero no obligatoria, instalar Ollama desde su distribución oficial y descargar
`gemma3:4b`.

La preparación opcional de Ollama utiliza una ventana gráfica propia de ODIN,
sin abrir PowerShell. La descarga muestra porcentaje, velocidad, tamaño
transferido y cantidad restante; la instalación y `ollama pull` se ejecutan en
segundo plano sin consola visible.

Sin Ollama, la lectura del Journal, la interfaz, las voces, las predicciones de
MÍMIR, las rutas de HEIMDALL, el comercio de FREYJA y las órdenes programadas
siguen funcionando. Solamente queda indisponible la respuesta conversacional
libre. El modelo requiere conexión durante la instalación y varios gigabytes de
espacio. Si el equipo ya tiene Ollama, el asistente reutiliza esa instalación.

HEIMDALL conserva el contexto de navegación de la nave, audita los controles,
evalúa combustible y autonomía, reconoce cargas de cono y saltos potenciados,
y sigue rutas convencionales o de neutrones. Puede solicitar rutas a Spansh,
copiar el siguiente waypoint al portapapeles y avanzar al confirmarse cada
`FSDJump`. Si el comandante recalcula la ruta en el juego, archiva el plan
anterior para no mantener instrucciones obsoletas.
Durante una autopista muestra saltos realizados, restantes y total real,
incluidos los saltos convencionales entre puntos principales de Spansh.

HEIMDALL analiza el evento `StoredShips` más reciente y registra como base el
sistema con más naves guardadas; en un empate prefiere la estación donde se
consultó el inventario. La base persiste en `%LOCALAPPDATA%\ODIN\heimdall`.
Las frases “vamos a la base”, “creá una ruta a la base” y “vamos a casa” calculan
automáticamente una ruta de neutrones hacia ella.

MÍMIR, el oficial científico, recibe eventos `Scan` planetarios,
normaliza sus datos, predice especies biológicas y publica una
recomendación de descenso. Su conocimiento incluye 116 especies de 19
géneros importadas desde EDMC BioScan mediante HUGINN. El análisis usa
el contexto galáctico de ExploData, los géneros confirmados por DSS,
las condiciones planetarias y el estado de descubrimiento y primera
pisada informado por el Journal.

Al completarse el FSS, si el total confirmado de cuerpos coincide exactamente
con el número de estrellas y no existen planetas ni lunas, MÍMIR anuncia por voz
que el sistema no contiene planetas para escanear. El aviso se emite una sola
vez por sistema, no pronuncia el nombre del sistema y no se muestra como informe
científico en pantalla.

Cuando el DSS confirma los géneros presentes, ODIN actualiza el informe y
conserva las especies y variantes compatibles. Durante el trabajo de campo,
MÍMIR cuenta las muestras 1/3, 2/3 y 3/3 y usa `Status.json` para calcular
la distancia superficial necesaria antes de la siguiente recolección.
Después de las muestras 1/3 y 2/3 anuncia por voz la separación mínima de la
especie. Al alcanzar el umbral vuelve a avisar, una sola vez por etapa, que la
siguiente muestra ya puede recolectarse.
Al completar la muestra 3/3, MÍMIR confirma la especie terminada y compara el
número de señales biológicas del planeta con las especies ya analizadas para
informar cuántas quedan, o que el planeta fue completado.
Los candidatos científicos visibles incluyen su recompensa base individual y,
cuando corresponde, el potencial First Logged. Un desembarco sobre un planeta
que el último escaneo marcó sin pisada prepara además el aviso de voz de primera
pisada, sin repetirlo ni mostrarlo en la consola. MÍMIR elige entre varias frases
de humor evolutivo de forma estable por planeta, incluyendo el clásico del mono
pulgoso.

ODIN conserva por sistema los nombres de las especies probables informadas por
MÍMIR. Ante una consulta hablada puede enumerarlas agrupadas por planeta sin
decir precios ni recompensas. Si un planeta con señal biológica resulta compatible
con Stratum Tectonicas, MÍMIR lo anuncia automáticamente una sola vez.
La interfaz combina esas predicciones con las señales reales persistidas del
Journal y lista todos los planetas biológicos del sistema, incluyendo cantidad
de señales, géneros confirmados y especies identificadas cuando están disponibles.
Las especies que requieren una variante de color se descartan cuando ninguna
estrella o material disponible puede producirla, replicando el filtro de BioScan.

## Flujo científico

```text
Journal Scan
    -> ExplorationProcessor
    -> PLANET_SCAN_READY
    -> MÍMIR
    -> SCIENTIFIC_ANALYSIS_READY
    -> ConsolePresenter
```

## Ejecutar ODIN

```powershell
python main.py
```

El arranque normal abre el **Centro de Mando de ODIN**, una interfaz gráfica
de escritorio con estética naranja inspirada en Elite Dangerous. La columna
izquierda conserva el registro operativo completo; la derecha muestra
comandante, nave, créditos, balance de expedición, biología, conexiones y la
ruta activa de HEIMDALL. El siguiente sistema permanece visible y puede
copiarse manualmente si falla la actualización automática del portapapeles.
El lateral de oficiales utiliza pestañas amplias para MÍMIR, HEIMDALL, FREYJA
y RED. Freyja muestra la modalidad, el tramo comercial, producto, toneladas,
destino, beneficio estimado y ganancia realizada.
Sus cuatro botones permiten iniciar desde la interfaz una ruta rápida, un
circuito de tres estaciones, una expedición comercial o comercio Powerplay.
Toda frase pronunciada por cualquier oficial también se conserva en el
Registro Operativo antes de intentar reproducirla, por lo que permanece visible
cuando las voces están silenciadas o el sintetizador no está disponible.
La pestaña MÍMIR agrupa las señales por planeta y muestra, junto a cada especie
probable, su recompensa aproximada e indica si corresponde al valor normal o al
bonificador ×5 disponible por primera pisada.
También presenta el seguimiento de recolección por especie: progreso de 1/3 a
3/3, distancia recorrida y restante, disponibilidad de la siguiente muestra y
colecciones completadas.
La vista se vacía al saltar a otro sistema, muestra únicamente el planeta activo
al aproximarse o aterrizar y reemplaza las posibilidades por los géneros reales
cuando el DSS completa el análisis de sus señales.

El modo de consola anterior continúa disponible como respaldo:

```powershell
python main.py --console
```

En la barra superior, `VOCES/SILENCIO` activa o silencia inmediatamente a
todos los oficiales. `CONFIGURACIÓN` permite guardar las API keys personales
en el Administrador de credenciales de Windows y autorizar por separado los
envíos a EDDN, EDSM e Inara. Las claves nunca se escriben en `config.json`;
los cambios de transmisión se aplican en el siguiente inicio de ODIN.
El Frontier ID se detecta automáticamente desde el Journal. El mismo panel
incluye un volumen general para los oficiales y botones `ACEPTAR`/`CANCELAR`;
cancelar cierra la ventana sin guardar ninguna modificación.
Cada proveedor indica `CONFIGURADA` o `NO CONFIGURADA` sin mostrar el valor de
la API key protegida.
El modo de conversación también es configurable: sólo `Push to Talk (F8)`,
sólo activación por la palabra `ODIN`, o ambos mecanismos simultáneamente.
El selector de idioma admite español latinoamericano, español de España,
inglés estadounidense, inglés británico y portugués de Brasil. Al cambiarlo,
ODIN conserva volumen y velocidad pero asigna voces Edge compatibles a cada
oficial. La traducción completa de todos los paneles se aplica progresivamente;
el cambio de interfaz requiere reiniciar ODIN.
La misma sección incluye `CALIBRAR MI VOZ`. El asistente pausa la escucha
pasiva, presenta siete órdenes operativas seguras y muestra la transcripción de
Whisper antes de permitir guardarla. El WAV temporal se elimina después de cada
muestra; sólo queda la asociación confirmada, aislada por Frontier ID o nombre
del comandante. `BORRAR PERFIL` elimina toda su memoria local de órdenes.
Al cerrar la interfaz se conserva su tamaño y posición para volver a abrirla
en el mismo monitor, incluso en escritorios con coordenadas negativas.
El panel de Heimdall permite pegar un sistema de destino y solicitar una ruta
de neutrones sin usar la voz; `Enter` y el botón `CALCULAR` ejecutan el mismo
planificador asíncrono y dejan visible el siguiente salto.
En el bloque del comandante, junto a la ubicación actual, ODIN distingue entre
`REGISTRO PREVIO` y `SIN REGISTRO` en EDSM. La segunda marca significa que la comunidad todavía
no aportó datos conocidos; no garantiza por sí sola el primer descubrimiento.

Cerrar la ventana solicita primero el cierre ordenado del observador del
Journal y de los servicios de voz y red.

ODIN impide que dos copias se ejecuten simultáneamente para evitar el
procesamiento duplicado de eventos del Journal.

## Configuración segura de voces

ODIN permite asignar una voz diferente a ODIN, MÍMIR y HEIMDALL. El
configurador detecta las voces OneCore instaladas en Windows y también deja
preparados identificadores de voz independientes para ElevenLabs:

```powershell
python main.py --configure-voice
```

El proveedor predeterminado es Edge TTS, sin API key ni consumo de créditos:
ODIN utiliza Alonso latino de Estados Unidos, MÍMIR utiliza Dalia de México y HEIMDALL
utiliza Jorge de México. No se seleccionan voces de España. Edge TTS
necesita conexión a Internet; si no está disponible, ODIN utiliza las voces
locales de Windows como respaldo.

La clave de ElevenLabs se introduce de forma oculta, se valida antes de
guardarla y se almacena en el Administrador de credenciales de Windows para el
usuario actual. Nunca se escribe en `config.json`, en el archivo de preferencias
ni en los registros de ODIN. Las asignaciones no secretas quedan en
`%LOCALAPPDATA%\ODIN\voice\settings.json`.

Cada comandante utiliza su propia cuenta de ElevenLabs. El archivo
`ELEVENLABS_API_KEY.txt` sirve únicamente para el alta inicial: ODIN valida el
acceso a las voces, migra la clave al Administrador de credenciales del usuario
de Windows y elimina el secreto del TXT. El configurador muestra las voces
disponibles en esa cuenta y permite asignar un `voice_id` diferente por oficial.
La selección interactiva de ElevenLabs muestra solamente voces verificadas en
español latino. Si el servicio falla o no tiene cuota, ODIN recurre
automáticamente a la síntesis local de Windows.

```powershell
python main.py --test-voice ODIN "Sistemas operativos, comandante."
```

## Inteligencia local sin créditos

ODIN puede conversar mediante Ollama y `gemma3:4b`, ejecutados íntegramente en
la computadora del comandante. Una prueba directa puede realizarse con:

```powershell
python main.py --test-ai "¿Cuál es tu función?"
```

## Conversación por voz

El modo inicial de pulsar para hablar graba una ventana breve desde el
micrófono predeterminado, transcribe localmente en español con whisper.cpp,
consulta a Ollama y reproduce la respuesta con la voz configurada para ODIN:

```powershell
python main.py --talk 7
```

El número indica los segundos de escucha. El audio y la transcripción no se
envían a servicios externos; Edge TTS sólo recibe el texto final que ODIN debe
pronunciar. Los fragmentos demasiado breves se descartan para evitar respuestas
activadas por ruido ambiente.

Mientras ODIN observa el Journal, `F8` inicia la misma escucha sin detener el
procesamiento del juego. La consulta incluye el contexto vivo conocido: sistema,
cuerpo, progreso de exploración, señales biológicas, nave, combustible, destino,
ruta y estimación acumulada de la expedición. ODIN indica expresamente cuando un
dato no está disponible y no debe inventarlo.

ODIN también mantiene una escucha local de activación. Se puede decir “ODIN” y
luego formular la pregunta, o pronunciar “ODIN” y la pregunta en una sola frase.
La captura termina automáticamente un segundo después de dejar de hablar. Sólo
una frase que contiene la palabra de activación llega a Ollama; durante la
respuesta hablada el micrófono se pausa para evitar realimentación.

El reconocimiento utiliza Whisper Small cuando está instalado y conserva Base
como respaldo. La captura mantiene audio previo al umbral para no perder la
primera sílaba, adapta el umbral al ruido ambiente y reconoce variantes acústicas
observadas como “Olín”. Un vocabulario inicial favorece nombres propios de ODIN,
MÍMIR, HEIMDALL y Elite Dangerous.

Las órdenes de navegación no dependen de una interpretación creativa del modelo.
Al decir “ODIN, calculá una ruta de neutrones hasta NOMBRE DEL SISTEMA”, ODIN
extrae el destino con reglas locales, entrega el cálculo a HEIMDALL y Spansh,
reemplaza la ruta activa y copia el primer waypoint al portapapeles. Al arribar,
HEIMDALL valida el sistema y copia el siguiente hasta completar el recorrido.
Si Spansh falla, ODIN pronuncia solamente un aviso breve; el detalle técnico se
conserva en `heimdall.log` para diagnóstico.

El cliente usa solamente `127.0.0.1:11434`, evita mostrar razonamiento interno
y falla de forma segura si Ollama o el modelo todavía no están disponibles.

## Balance de expedición

ODIN conserva un libro persistente con sistemas visitados, cuerpos
escaneados, cartografías DSS y especies exobiológicas completadas. El valor
cartográfico previo a la venta es aproximado y se identifica con `≈`. Para
exobiología se separan el valor base y el potencial First Logged. Los eventos
de venta del Journal aportan el importe definitivo cobrado.

Los eventos repetidos no duplican recompensas y un DSS actualiza el valor del
cuerpo que ya había sido escaneado. El balance se reconstruye al iniciar ODIN
desde la memoria local disponible.
Al vender cartografía o exobiología, el acumulado pendiente correspondiente
vuelve a cero y el importe cobrado permanece en el historial confirmado.

## Ejecutar las pruebas

La suite utiliza `unittest`, incluido en Python:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas no modifican la biblioteca de conocimiento.

## Datos externos

Las fuentes locales y sus condiciones de uso están documentadas en
[`docs/THIRD_PARTY_DATA.md`](docs/THIRD_PARTY_DATA.md).

## Colaboración y seguridad

Antes de proponer cambios, consulte [`CONTRIBUTING.md`](CONTRIBUTING.md). Los
problemas de seguridad deben seguir [`SECURITY.md`](SECURITY.md) y nunca deben
incluir claves, Journal completos ni datos personales del comandante.

Las decisiones sobre separación de plataforma, secretos y nombres públicos se
documentan en
[`docs/ARCHITECTURE_SECURITY.md`](docs/ARCHITECTURE_SECURITY.md).

El repositorio todavía no declara una licencia pública. Hasta que se elija y
añada una, la presencia del código en un repositorio no concede por sí sola
permiso para copiarlo, redistribuirlo o crear derivados.

## Próximo objetivo

**Siguiente etapa:** beta final para terceros y cierre de ODIN 1.0. La ruta
larga de HEIMDALL, la calibración acústica local, los cinco idiomas y la
sincronización de Inara ya están implementados y validados. Quedan pruebas
reales de la síntesis FSD autorizada, los modos avanzados de BROKK y la
instalación/voz en otros equipos. Las comprobaciones de méritos Powerplay
permanecen aplazadas porque el Journal no confirmó méritos en las ventas
controladas realizadas.
