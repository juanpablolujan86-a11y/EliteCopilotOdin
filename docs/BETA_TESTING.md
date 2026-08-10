# ODIN v0.7.2-beta — Guía para comandantes de prueba

## Instalación

1. Cierre cualquier copia anterior de ODIN.
2. Ejecute `ODIN-v0.7.2-beta-Setup-win64.exe`.
3. Mantenga marcada la opción de Ollama si desea conversación libre local.
   La descarga de `gemma3:4b` requiere Internet y varios gigabytes.
4. Inicie Elite Dangerous y después ODIN.

Sin Ollama continúan funcionando el Journal, las voces, MÍMIR, HEIMDALL,
FREYJA y todas las órdenes operativas programadas.

## Pruebas prioritarias

- MÍMIR: salto, detección biológica, predicción, DSS, filtrado por planeta y
  recolección 1/3–3/3 con distancia.
- HEIMDALL: ruta de neutrones, portapapeles, progreso y recálculo.
- FREYJA: cuatro modalidades comerciales dentro de la Burbuja.
- Voz: activación con ODIN, pulsar para hablar, silenciamiento y registro
  operativo de todas las respuestas.

## Cómo informar un problema

Incluya:

- Qué orden o acción realizó.
- Qué esperaba que ocurriera.
- Qué mostró o dijo ODIN.
- Sistema, planeta o estación implicados, si corresponde.
- Hora aproximada del fallo.

Adjunte los archivos recientes de `%LOCALAPPDATA%\ODIN\logs`. No comparta
archivos con API keys ni capturas que muestren credenciales.

## Limitaciones conocidas

- El instalador todavía no está firmado y Windows SmartScreen puede advertirlo.
- La selección completa de idioma de interfaz y voces está planificada para el
  siguiente sprint; esta beta utiliza español latinoamericano.
- Las rutas comerciales reales dependen de datos comunitarios recientes.
