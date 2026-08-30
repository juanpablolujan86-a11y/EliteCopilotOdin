# ODIN - Roadmap

## Sprint 1 - Núcleo

- [x] Config
- [x] DatabaseManager
- [x] JournalReader
- [x] JournalWatcher
- [x] EventBus
- [x] Logger

---

## Sprint 2 - Exploración

- [x] Detectar FSDJump
- [x] Detectar Scan
- [x] Detectar FSSComplete
- [x] Consultar EDSM
- [x] Auditar integración Canonn y descartar la API CAPIv2 retirada
- [x] Admitir catálogos POI Canonn pequeños o cachés locales mediante una
  fuente configurable; no descargar automáticamente el volcado Codex masivo

---

## Sprint 3 - Oficial Científico

- [x] Exobiología
- [x] Valor de exploración
- [x] Recomendaciones
- [x] Predicción científica cerrada mediante DSS
- [x] Registro persistente para pruebas beta
- [x] Mostrar junto a cada especie probable su recompensa individual estimada:
  valor base y, cuando corresponda, potencial con bonificación First Logged

---

## Sprint 3.1 - Navegación exobiológica de superficie

- [x] Definir el alcance operativo
- [x] Registrar ubicaciones de muestras durante la sesión activa
- [x] Ayudar a respetar la distancia mínima entre muestras
- [x] Detectar la primera pisada y preparar para voz la frase:
  «Felicidades, sos el primer descendiente de un mono pulgoso en pisar este
  planeta. Darwin estaría orgulloso de vos.»
- [x] Presentación por voz de distancia, siguiente muestra y finalización

---

## Sprint 3.2 - Balance de expedición

- [x] Contar sistemas, cuerpos, DSS y especies completadas
- [x] Estimar cartografía pendiente
- [x] Separar exobiología base y potencial First Logged
- [x] Registrar ventas confirmadas por el Journal
- [x] Evitar recompensas duplicadas
- [x] Reiniciar a cero los acumulados pendientes después de confirmar una venta
  de cartografía o exobiología, conservando por separado el historial cobrado

---

## Sprint 4 - Oficial Comercial

- [x] FREYJA: libro comercial local y carga actual
- [x] Mercado comunitario con oferta, demanda y antigüedad verificables
- [x] Perfil automático de nave, capital, permisos y preferencias
- [x] Ruta rápida optimizada por beneficio por minuto
- [x] Cadena de tres estaciones y hasta tres productos
- [x] Expedición comercial de hasta 30 saltos
- [x] Replanificación y progreso persistente
- [x] Consultas e informes por voz

### Integraciones comunitarias

- [x] Transmisión pública y anónima a EDDN con consentimiento explícito
- [x] Sincronización privada y opcional con EDSM
- [x] Preparar sincronización privada y opcional con Inara
- [x] Recibir la autorización de Inara para el nombre de aplicación `ODIN`
- [x] Ejecutar una prueba controlada de Inara antes de habilitar su transmisión

---

## Sprint 5 - Primer Oficial

- [x] Voz base y asignación independiente por oficial
- [x] Comandos operativos locales
- [x] Automatización mínima y no intrusiva mediante bindings

### Bloqueante para ODIN 1.0

- [x] Adaptación acústica local por comandante: aprender pronunciación y ritmo
  a partir de muestras confirmadas, con consentimiento, opción de borrar el
  perfil y aislamiento completo entre comandantes.
  - [x] Asistente local con consentimiento explícito
  - [x] Captura temporal y eliminación inmediata del audio
  - [x] Confirmación visual de la transcripción antes de aprender
  - [x] Asociación segura de pronunciaciones con órdenes predefinidas
  - [x] Aislamiento y borrado completo por comandante
  - [x] Evaluar adaptación de ritmo y parámetros acústicos sin reentrenar el modelo
- [x] Memoria semántica local de órdenes, alias y correcciones por comandante.

---

## HEIMDALL - Navegación y asistencia mínima

- [x] Contexto de nave, FSD, combustible y destino
- [x] Descubrir y respaldar perfiles `.binds`
- [x] Detectar perfil activo, errores y dispositivos ausentes
- [x] Resolver teclas por acción sin modificar originales
- [x] Restaurar bindings solamente con autorización explícita
- [x] Planificador de rutas exactas con Galaxy Plotter
- [x] Autonomía y estrellas scoopables
- [x] Autopistas de neutrones
  - [x] Detectar waypoints de neutrones y enanas blancas
  - [x] Registrar carga de cono y salto potenciado sin duplicados
  - [x] Conservar salud real conocida del FSD y exposiciones de sesión
  - [x] Comparar ruta convencional y ruta de neutrones
    - [x] Integrar planificador comunitario Spansh y persistir resultados
    - [x] Usar automáticamente sistema actual y alcance real de la nave
    - [x] Comparar contra un límite inferior convencional conservador
    - [x] Comparar contra la ruta convencional exacta leída de `NavRoute.json`
    - [x] Incorporar parámetros físicos completos para Galaxy Plotter exacto
      - [x] Validar y construir la solicitud sin aproximar constantes ausentes
      - [x] Integrar el trabajo asíncrono de `/api/generic/route` y decodificar combustible
      - [x] Exponer cálculo independiente en la pestaña HEIMDALL con carga real
      - [x] Persistir, reanudar y avanzar rutas exactas tras reiniciar ODIN
      - [x] Mostrar distancia, consumo, combustible restante y repostaje del
        próximo tramo exacto
  - [x] Guiar la secuencia segura de sobrecarga por telemetría disponible
    - [x] Copiar el primer waypoint al crear la ruta
    - [x] Avanzar y copiar el siguiente solamente tras `FSDJump` confirmado
    - [x] Persistir el índice y evitar avances duplicados
    - [x] Mostrar durante la autopista el progreso de la expedición: saltos
      realizados, saltos restantes y total de saltos previsto hasta el destino
    - [x] Validar virtualmente una ruta larga, reinicio intermedio e idempotencia
      frente a eventos `FSDJump` duplicados
    - [x] Confirmar una ruta larga completa dentro del juego
    - [x] Advertir aproximación, confirmar carga y ordenar salida segura sin
      inventar posición ni geometría que el Journal no proporciona
    - [x] Validar los avisos durante una sobrecarga real dentro del juego
- [ ] Síntesis de salto autorizada
  - [x] Reconstruir y mantener el inventario de materias primas
  - [x] Calcular inyecciones básicas, estándar y premium disponibles
  - [x] Responder consultas por voz sin consumir materiales
  - [x] Proponer el grado mínimo sólo cuando resuelva un salto inaccesible
  - [x] Revisar los tramos futuros de `NavRoute.json`
  - [x] Excluir de la síntesis los segmentos potenciados por cono
  - [x] Exigir una autorización temporal, explícita y de un solo uso
  - [ ] Ejecutar síntesis desde la interfaz sólo tras validación real en juego
- [x] Replanificación opcional por desvío sin bloquear el Journal
- [x] Luces y visión nocturna opcionales para nave y SRV
- [x] Solicitud contextual de atraque mediante bindings y acceso F7
- [x] Modo informativo sin pulsaciones
- [x] Registro persistente `heimdall.log`
## Idiomas y voces para 1.0

- [x] Preferencia persistente y catálogo central por locale.
- [x] Selector para `es-419`, `es-ES`, `en-US`, `en-GB` y `pt-BR`.
- [x] Perfiles Edge por idioma para todos los oficiales.
- [x] Selección inicial desde el instalador.
- [x] Traducir completamente la interfaz gráfica.
  - [x] Ventana principal, panel del comandante, MÍMIR y HEIMDALL.
  - [x] FREYJA: controles, modalidades, resultados y estados vacíos.
  - [x] BROKK: controles, técnicas, resultados y estados operativos principales.
  - [x] Guardian: inventario, búsqueda, recolección y agente tecnológico.
  - [x] Configuración: red, credenciales, IA, idioma, escucha y calibración.
  - [x] Asistente de calibración, consentimiento y órdenes de muestra.
- [x] Traducir mensajes programados y reconocimiento de órdenes.
  - [x] Siete órdenes operativas de calibración en español, inglés y portugués.
  - [x] Whisper y Faster Whisper usan el idioma configurado.
  - [x] Órdenes conversacionales de comercio, minería y EDDN en inglés y portugués.
  - [x] Consultas/autorizaciones FSD y memoria de órdenes en inglés y portugués.
  - [x] Contexto científico y prompt compartido de OpenAI/Ollama por locale.
  - [x] Respuestas programadas de ODIN, MÍMIR, HEIMDALL, FREYJA y BROKK.
    - [x] Activación, procesamiento, reintentos y menú comercial ODIN/FREYJA.
    - [x] Recomendaciones y alertas prioritarias de MÍMIR.
    - [x] Primera pisada, navegación entre muestras y cierre exobiológico de MÍMIR.
    - [x] Memoria de órdenes, estado EDDN y respuestas comerciales principales de ODIN/FREYJA.
    - [x] Resúmenes de los cuatro modelos comerciales y venta por tonelaje de FREYJA.
    - [x] Respuestas contextuales de cockpit, atraque y controles de nave/SRV.
    - [x] Seguimiento persistente, progreso y recuperación de rutas de FREYJA.
    - [x] Navegación de HEIMDALL y minería de BROKK.
      - [x] Inicio, espera, ausencia de contexto y errores operativos principales.
      - [x] Resultado de rutas y resúmenes de sesiones/ventas mineras.
      - [x] Síntesis e inyecciones FSD.
- [ ] Validar voces e instalación real en cada idioma.
  - [x] Simulación integral de voces, siete intents seguros, MÍMIR y síntesis FSD
    para los cinco locales.
  - [ ] Validación auditiva y del instalador en equipos reales de cada idioma.

# BROKK - Minería e ingeniería de recursos

- [x] Definir misión, límites y flujo operativo.
- [x] Crear modelos de operación minera y estado persistente.
- [x] Procesar prospección, refinado, carga, materiales y ventas del Journal.
- [x] Auditar equipamiento y compatibilidad con cada técnica minera.
- [x] Implementar sesión inicial de minería por láser.
- [x] Buscar zonas mineras por material, tipo de anillo, reservas y distancia.
- [x] Entregar a HEIMDALL el destino minero elegido sin acoplamiento directo.
- [x] Agregar la pestaña BROKK y su estado operativo a la interfaz.
- [x] Incorporar consultas y avisos de voz sin saturar al comandante.
- [x] Calcular toneladas/hora, créditos/hora y valor aproximado de la carga.
- [x] Integrar la búsqueda de venta mediante eventos, sin acoplar BROKK a FREYJA.
- [ ] Validar abrasión, subsuperficie y núcleo profundo.
- [ ] Ejecutar una prueba minera Powerplay con trazabilidad completa.
  Aplazada: las ventas controladas no otorgaron méritos y no bloquearán ODIN 1.0.

# POWERPLAY - Méritos y operaciones

- [x] Guía de tareas semanales Powerplay.
  - [x] Retirar OCR, captura de pantalla, previsualización y dependencias asociadas.
  - [x] Abrir una ventana independiente con procedimientos para megabuques,
    combate, comercio, minería, suministros, exploración, operaciones terrestres,
    salvamento y delitos.
  - [x] Mantener méritos confirmados mediante `Powerplay` y `PowerplayMerits`.
- [x] Crear una pestaña independiente de los oficiales.
- [x] Permitir elegir combate, comercio, minería, suministros, exploración,
  operaciones a pie o salvamento.
- [x] Mostrar potencia, rango, méritos actuales y méritos ganados confirmados
  exclusivamente por el Journal.
- [x] Para combate, buscar sistemas candidatos cercanos por potencia, estado
  territorial y conflictos comunitarios, con acceso directo a HEIMDALL.
- [x] Validar dentro del juego que los destinos de combate propuestos coincidan
  con la actividad mostrada en el panel Powerplay actual.
- [x] Implementar buscadores específicos para comercio, minería, suministros,
  exploración, operaciones a pie y salvamento.
  - [x] Consultar bajo demanda territorios candidatos de adquisición, refuerzo
    y socavación para las siete modalidades.
  - [x] Mostrar instrucciones y advertencias específicas sin prometer méritos.
  - [x] Cruzar Minería con hotspots de BROKK y mostrar cuerpo, anillo, reservas
    y cantidad de hotspots dentro del territorio candidato.
  - [x] Cruzar Comercio con la caché de FREYJA por mercancía, territorio,
    demanda y compatibilidad con plataforma grande, sin actualización implícita.
  - [x] Cruzar Suministros con estaciones conocidas compatibles con la nave y
    exigir confirmación manual del contacto Powerplay.
  - [x] Actualizar bajo demanda hasta 300 mercados o estaciones desde Spansh
    antes del cruce de Comercio y Suministros, con fallback a caché.
  - [x] Cruzar cada modalidad con instalaciones, mercados, anillos,
    asentamientos o contactos adecuados dentro del sistema candidato.
    Exploración usa Universal Cartographics, operaciones a pie asentamientos
    Odyssey y Salvamento Search and Rescue desde la caché comunitaria.
- [ ] Confirmar en el juego qué actividades están otorgando méritos actualmente.

# FREYJA / Powerplay heredado

- [x] Leer afiliación, rango y méritos del comandante desde el Journal.
- [x] Filtrar comercio por potencia, estado territorial y margen mínimo elegible.
- [x] Mantener separados el beneficio exacto en créditos y los méritos por confirmar.
- [ ] Validar en el juego los méritos reales otorgados por cada venta y calibrar la estimación.
  Aplazada hasta confirmar que la actividad vuelve a otorgar méritos observables.
