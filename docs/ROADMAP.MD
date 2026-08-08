# ROADMAP

## Sprint 3.0 — Exploration Capability

**Estado: Completado**

- [x] Procesar FSDJump
- [x] Procesar Scan
- [x] Procesar FSSDiscoveryScan
- [x] Procesar FSSAllBodiesFound
- [x] Procesar SAAScanComplete
- [x] Procesar SAASignalsFound
- [x] Procesar ScanOrganic
- [x] Guardar cuerpos en SQLite
- [x] Registrar progreso FSS
- [x] Registrar cartografía DSS
- [x] Registrar señales biológicas
- [x] Generar informes de exploración
- [x] Generar recomendaciones contextuales
- [x] Completar prueba real en Elite Dangerous

## Sprint 4.0 — MÍMIR Operativo

**Estado: Completado en v0.4.0**

- [x] Implementar el oficial científico MÍMIR
- [x] Adaptar eventos `Scan` del Journal
- [x] Integrar MÍMIR con el EventBus
- [x] Publicar informes científicos en consola
- [x] Importar el género Stratum mediante HUGINN
- [x] Validar el flujo con un Journal real
- [x] Incorporar pruebas automáticas de regresión

## Operación Yggdrasil — v0.5.0

**Estado: Completado**

- [x] Importar 19 catálogos biológicos de EDMC BioScan
- [x] Generar 116 especies y 254 reglas trazables
- [x] Validar duplicados, referencias y reglas vacías
- [x] Filtrar predicciones mediante el género confirmado por DSS
- [x] Corregir el cálculo de valores por género
- [x] Excluir Belt Clusters de los conteos FSS
- [x] Evitar informes duplicados de FSSAllBodiesFound
- [x] Restaurar el sistema actual al reiniciar ODIN
- [x] Centralizar las prioridades visibles en español
- [x] Validar MÍMIR dentro de Elite Dangerous

## Cierre científico de MÍMIR — v0.6.0

**Estado: Completado**

- [x] Evaluar todas las condiciones importadas de BioScan
- [x] Incorporar región galáctica, estrellas, materiales y nebulosas
- [x] Predecir variantes biológicas cuando existen datos suficientes
- [x] Informar descubrimiento, cartografiado y primera pisada
- [x] Estimar el potencial de First Logged (×5) sin presentarlo como certeza
- [x] Seguir el progreso orgánico real de 1/3 a 3/3
- [x] Procesar `FSSBodySignals` y `SAASignalsFound` sin duplicados
- [x] Mantener silencio en planetas sin candidatos biológicos
- [x] Validar un DSS real con cinco géneros confirmados

## Próximo objetivo

Incorporar asistencia de navegación exobiológica sobre la superficie y
definir el segundo oficial especializado de ODIN.

## Requisitos previos al lanzamiento 1.0

- [ ] Incorporar adaptación acústica opcional por comandante para mejorar el
  reconocimiento de su voz, pronunciación y ritmo sin contaminar el modelo con
  transcripciones de baja confianza.
- [x] Mantener memoria semántica separada para expresiones, alias y correcciones
  propias de cada comandante.
