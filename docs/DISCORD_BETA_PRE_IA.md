# ODIN — Beta pública pre-IA para Elite Dangerous

ODIN es un copiloto de escritorio para Elite Dangerous que lee en tiempo real
los archivos Journal del juego y organiza la información mediante oficiales
especializados. Esta edición pública contiene las funciones operativas ya
construidas, pero excluye la inteligencia artificial experimental, OpenAI y
Ollama.

## Qué incluye

- **MÍMIR — Ciencia y exobiología:** detecta señales biológicas, muestra
  predicciones y géneros confirmados tras el DSS, valores aproximados,
  bonificación por primera pisada y seguimiento de las tres muestras con sus
  distancias mínimas.
- **HEIMDALL — Navegación y cabina:** calcula rutas de neutrones, mantiene el
  siguiente salto visible y en el portapapeles, controla el progreso del viaje,
  conserva la base del comandante y ofrece órdenes configuradas de cabina y
  atraque mediante los bindings del juego.
- **FREYJA — Comercio:** calcula rutas rápidas, circuitos de tres estaciones,
  expediciones comerciales y búsquedas Powerplay usando capacidad de carga,
  plataforma, distancia, oferta, demanda y antigüedad de los mercados.
- **BROKK — Minería:** busca lugares de minería, sigue la carga refinada,
  registra el comienzo y cierre de la operación, estima rendimiento y propone
  destinos de venta por distancia.
- **Guardian e Ingeniería:** muestra materiales disponibles y faltantes,
  conserva el objetivo elegido y ayuda a localizar lugares de recolección,
  brokers e ingenieros.
- **Powerplay:** ofrece actividades de combate, comercio, minería, transporte,
  exploración y operaciones a pie. Los méritos sólo se consideran confirmados
  cuando aparecen en el Journal.
- **Interfaz y voz:** panel inspirado en Elite, registro operativo escrito,
  voces diferenciadas, control de volumen, silencio, push-to-talk o activación
  por voz, lista de comandos y memoria de posición/tamaño de ventana.
- **Servicios comunitarios opcionales:** EDDN, EDSM e Inara pueden habilitarse
  por separado con las credenciales y autorizaciones de cada comandante.

## Privacidad

Las claves personales no vienen incluidas. Cada comandante configura las suyas
desde ODIN. Los envíos a servicios comunitarios están separados y pueden
activarse o desactivarse. Esta edición no contiene acceso a OpenAI ni instala
Ollama.

## Requisitos y advertencias

- Windows de 64 bits y Elite Dangerous para PC.
- El instalador todavía no está firmado; Windows SmartScreen puede mostrar una
  advertencia.
- Los precios, rutas y ubicaciones comunitarias dependen de datos externos y
  pueden estar desactualizados.
- Es una beta: no automatiza decisiones críticas ni garantiza méritos,
  beneficios comerciales o rutas sin restricciones de permiso.

## Cómo reportar un fallo

Indicar qué acción se realizó, qué se esperaba, qué ocurrió y la hora
aproximada. Los registros están en `%LOCALAPPDATA%\ODIN\logs`. No publicar API
keys, archivos de credenciales ni capturas donde aparezcan secretos.
