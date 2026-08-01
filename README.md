# ODIN

**Orbital Data Intelligence Nexus** es un copiloto modular para
Elite Dangerous. Observa el Journal del juego, conserva el estado del
comandante y coordina oficiales especializados mediante un EventBus.

## Estado actual

Versión en preparación: **v0.4 — MÍMIR Operativo**.

MÍMIR, el oficial científico, recibe eventos `Scan` planetarios,
normaliza sus datos, predice especies biológicas y publica una
recomendación de descenso. Su conocimiento actual incluye el género
Stratum importado desde EDMC BioScan mediante HUGINN.

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

**Operación Yggdrasil:** validar en el juego la biblioteca completa
generada por HUGINN: 19 géneros, 116 especies y 254 reglas procedentes
de EDMC BioScan.
