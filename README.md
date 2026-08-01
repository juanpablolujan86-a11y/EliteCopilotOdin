# ODIN

**Orbital Data Intelligence Nexus** es un copiloto modular para
Elite Dangerous. Observa el Journal del juego, conserva el estado del
comandante y coordina oficiales especializados mediante un EventBus.

## Estado actual

Versión actual: **v0.6.0 — MÍMIR Científico**.

MÍMIR, el oficial científico, recibe eventos `Scan` planetarios,
normaliza sus datos, predice especies biológicas y publica una
recomendación de descenso. Su conocimiento incluye 116 especies de 19
géneros importadas desde EDMC BioScan mediante HUGINN. El análisis usa
el contexto galáctico de ExploData, los géneros confirmados por DSS,
las condiciones planetarias y el estado de descubrimiento y primera
pisada informado por el Journal.

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

## Ejecutar las pruebas

La suite utiliza `unittest`, incluido en Python:

```powershell
python -m unittest discover -s tests -v
```

Las pruebas no modifican la biblioteca de conocimiento.

## Próximo objetivo

**Siguiente etapa:** navegación exobiológica de superficie y diseño del
próximo oficial especializado de ODIN.
