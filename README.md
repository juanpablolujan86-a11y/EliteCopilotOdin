# ODIN

**Orbital Data Intelligence Nexus** es un copiloto modular para
Elite Dangerous. Observa el Journal del juego, conserva el estado del
comandante y coordina oficiales especializados mediante un EventBus.

## Estado actual

Versión actual: **v0.7.1 — MÍMIR y HEIMDALL consolidados**.

HEIMDALL conserva el contexto de navegación de la nave, audita los controles,
evalúa combustible y autonomía, reconoce cargas de cono y saltos potenciados,
y sigue rutas convencionales o de neutrones. Puede solicitar rutas a Spansh,
copiar el siguiente waypoint al portapapeles y avanzar al confirmarse cada
`FSDJump`. Si el comandante recalcula la ruta en el juego, archiva el plan
anterior para no mantener instrucciones obsoletas.
Durante una autopista muestra saltos realizados, restantes y total real,
incluidos los saltos convencionales entre puntos principales de Spansh.

MÍMIR, el oficial científico, recibe eventos `Scan` planetarios,
normaliza sus datos, predice especies biológicas y publica una
recomendación de descenso. Su conocimiento incluye 116 especies de 19
géneros importadas desde EDMC BioScan mediante HUGINN. El análisis usa
el contexto galáctico de ExploData, los géneros confirmados por DSS,
las condiciones planetarias y el estado de descubrimiento y primera
pisada informado por el Journal.

Cuando el DSS confirma los géneros presentes, ODIN actualiza el informe y
conserva las especies y variantes compatibles. Durante el trabajo de campo,
MÍMIR cuenta las muestras 1/3, 2/3 y 3/3 y usa `Status.json` para calcular
la distancia superficial necesaria antes de la siguiente recolección.
Los candidatos científicos visibles incluyen su recompensa base individual y,
cuando corresponde, el potencial First Logged. Un desembarco sobre un planeta
que el último escaneo marcó sin pisada prepara además el aviso de voz de primera
pisada, sin repetirlo ni mostrarlo en la consola.

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

ODIN impide que dos copias se ejecuten simultáneamente para evitar el
procesamiento duplicado de eventos del Journal.

## Configuración segura de voces

ODIN permite asignar una voz diferente a ODIN, MÍMIR y HEIMDALL. El
configurador detecta las voces OneCore instaladas en Windows y también deja
preparados identificadores de voz independientes para ElevenLabs:

```powershell
python main.py --configure-voice
```

La clave de ElevenLabs se introduce de forma oculta, se valida antes de
guardarla y se almacena en el Administrador de credenciales de Windows para el
usuario actual. Nunca se escribe en `config.json`, en el archivo de preferencias
ni en los registros de ODIN. Las asignaciones no secretas quedan en
`%LOCALAPPDATA%\ODIN\voice\settings.json`.

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

## Próximo objetivo

**Siguiente etapa:** navegación exobiológica de superficie y diseño del
próximo oficial especializado de ODIN.
