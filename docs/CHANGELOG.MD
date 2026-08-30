# CHANGELOG

## v0.8.1-beta-pre-IA — Beta pública para la flota

- Repositorio depurado y documentación reorganizada para colaboradores.
- Nombres públicos normalizados: NJÖRÐR para navegación, HEIMDALL para
  tecnología Guardian y VÖLUNDR para ingeniería.
- Eliminados prototipos sin consumidores, pruebas manuales reemplazadas y
  artefactos generados accidentalmente.
- Distribución pública basada en las capacidades estables anteriores al cierre
  de la inteligencia coordinadora.
- Suite completa validada con 581 pruebas automáticas.

## En desarrollo — cierre hacia 1.0

- La cabecera de la interfaz incorpora «Comandos de voz» junto a Configuración.
  Abre una guía desplazable y con búsqueda, agrupada por ODIN, MÍMIR, HEIMDALL,
  FREYJA y BROKK, con ejemplos localizados para los cinco idiomas disponibles.
  La guía es informativa y no activa el micrófono ni ejecuta controles.
- Se reconstruyó la beta instalable de ODIN 0.8.0 el 26 de agosto de 2026
  desde el código actual. El proceso de entrega ahora ejecuta PyInstaller antes
  de Inno Setup, evitando reutilizar accidentalmente un `dist/ODIN` antiguo, y
  verifica la existencia del instalador final.
- Se actualizó la guía para terceros con el estado real de HEIMDALL, BROKK,
  idiomas, calibración acústica, Inara y las limitaciones vigentes de síntesis
  FSD y méritos Powerplay.
- Se corrigió el registro de rutas exactas de HEIMDALL: `ExactRoutePlan` ya no
  provoca una excepción al carecer de los campos exclusivos del planificador
  de neutrones. La regresión quedó cubierta por la suite automatizada.

- POWERPLAY incorpora el núcleo persistente de asignaciones semanales, con
  clasificación de nueve familias, cantidades, destinos y estados.
- La detección interna usa eventos de misión únicamente cuando Elite los expone;
  la interfaz no intenta leer la lista semanal mostrada por el juego.
- Las asignaciones seleccionadas generan pasos específicos para nueve familias;
  cuando Elite aporta un destino, ODIN lo prepara en HEIMDALL sin trazar ni
  ejecutar la ruta automáticamente.
- Si una asignación seleccionada no incluye destino, ODIN inicia la búsqueda
  territorial apropiada para su familia. Comercio y minería se detienen cuando
  falta el producto exacto, evitando sugerir ubicaciones basadas en inferencias.
- El Journal conserva el ciclo de vida de las asignaciones aceptadas, completadas,
  fallidas o abandonadas y restaura esos estados después de reiniciar ODIN.
- ODIN escucha también `PowerplayMerits`, recupera el último valor al iniciar y
  calcula los méritos confirmados desde que se seleccionó la operación semanal.
- Las asignaciones de megabuques consultan la caché POI Canonn, ordenan los
  candidatos por distancia y muestran categoría, instrucciones y advertencia
  de validación; nunca presentan el candidato comunitario como objetivo seguro.
- Las asignaciones se identifican por el ciclo semanal iniciado el jueves a las
  07:00 UTC; el nuevo ciclo oculta las anteriores y una descripción repetida
  nunca hereda estado ni progreso de la semana previa.
- La lista semanal presenta familias y estados traducidos, incluyendo
  megabuques, delitos, activa, completada, fallida y abandonada.
- Se retiró por decisión de diseño la lectura OCR de asignaciones Powerplay,
  junto con sus dependencias y componentes de captura. La pestaña ofrece ahora
  una guía semanal independiente y no interpreta la pantalla del juego.
- Las búsquedas Powerplay de Exploración, operaciones a pie y Salvamento cruzan
  los territorios con Universal Cartographics, asentamientos Odyssey y Search
  and Rescue almacenados en la caché; cada resultado exige confirmación en Elite.

- Configuración admite una fuente POI Canonn HTTPS o local y la actualiza sólo
  por acción explícita, en segundo plano, con caché segura y límites de tamaño.

- POWERPLAY dispone de una pestaña independiente con siete familias de
  actividades y conteo de méritos confirmado por el Journal.
- Las siete modalidades pueden consultar bajo demanda territorios candidatos
  en Spansh; ODIN no transmite la posición sin una selección explícita.
- Cada modalidad explica qué debe confirmarse en Actividades locales y evita
  considerar los sistemas candidatos como garantía de méritos.
- POWERPLAY cruza Minería con el buscador de hotspots de BROKK y muestra sólo
  anillos ubicados dentro de territorios candidatos, conservando reservas y
  trazabilidad del punto de extracción.
- POWERPLAY cruza Comercio con la caché existente de FREYJA y filtra por
  mercancía, demanda, territorio y plataforma grande. Si faltan mercados
  compatibles, lo informa sin actualizar datos ni inventar destinos.
- Suministros cruza los territorios con estaciones locales compatibles y marca
  cada resultado como contacto Powerplay pendiente de confirmar en el juego.
- Comercio y Suministros actualizan bajo demanda hasta tres páginas de Spansh;
  si la consulta falla conservan y utilizan la última caché válida.
- La opción Combate consulta sistemas cercanos, clasifica operaciones de
  adquisición, socavación o refuerzo y permite preparar el destino en HEIMDALL.
- La búsqueda y selección de destinos de combate Powerplay quedó validada por
  el comandante dentro de Elite Dangerous.
- El diagnóstico Inara informa ahora el estado del evento individual y su texto
  de error cuando una cabecera HTTP/API aceptada contiene rechazos parciales;
  evita registrar engañosamente esos casos como «código 200».
- La entrega Inara procesa cada respuesta del lote por separado: conserva los
  eventos aceptados y rechaza sólo el inválido. Las actualizaciones de méritos
  Powerplay esperan a disponer también del rango obligatorio para la API.
- La cola local confirma entregas reales aceptadas de viajes, carga, créditos,
  misiones, reputaciones, rangos y naves; la prueba controlada queda cerrada.
- Se registró como validada por el comandante la operación real de las rutas de
  neutrones y sus avisos de sobrecarga de HEIMDALL.

- Auditoría Canonn actualizada: ODIN no integrará la API CAPIv2 retirada ni
  descargará automáticamente el volcado Codex de aproximadamente 286 MB.
- La futura integración Canonn queda limitada a POI configurables y caché
  local explícita, sin bloquear el Journal ni ampliar el instalador.

- HEIMDALL incorpora en su pestaña un cálculo separado de ruta exacta con
  Galaxy Plotter, usando la carga y los parámetros físicos reales de la nave.
- Las rutas exactas se guardan, sobreviven al reinicio, avanzan sólo con
  `FSDJump` y conservan combustible, scoop y necesidad de repostaje.
- La pestaña HEIMDALL muestra para el próximo tramo exacto la distancia,
  combustible previsto, consumo y si requiere repostaje o permite scoop.
- HEIMDALL guía la sobrecarga sin tomar el control del vuelo: reconoce el
  objetivo, diferencia neutrones y enanas blancas, confirma `JetConeBoost`,
  indica salir del cono y confirma el salto potenciado.
- La pestaña muestra el estado de sobrecarga y los avisos incluyen la salud
  conocida del FSD, con deduplicación de eventos repetidos.
- Suite de regresión ampliada a 530 pruebas automáticas superadas.

- Selector de técnica minera para láser, abrasión, subsuperficie y núcleo profundo.
- Confirmación auditable de núcleo profundo mediante `AsteroidCracked`.
- Abrasión y subsuperficie identificadas como selección del comandante, sin inferencias falsas.
- Corrección de textos dañados en distancia, estados vacíos y datos Powerplay.
- Roadmap actualizado: Inara en whitelist y pruebas Powerplay aplazadas.
- HEIMDALL ignora de forma persistente eventos `FSDJump` duplicados sin sumar
  saltos falsos ni adelantar el portapapeles.
- Simulación de ruta larga con reinicio intermedio y progreso exacto.
- Asistente de calibración local con consentimiento, confirmación por muestra,
  aislamiento por comandante y borrado completo del perfil.
- Las grabaciones de calibración son temporales y nunca se conservan ni envían.
- La configuración de voz utiliza su propia conexión SQLite para no cruzar el
  hilo gráfico con el motor de ODIN.
- Las excepciones de botones de Tkinter ahora quedan registradas con traceback
  en `odin.log` aunque ODIN se ejecute sin consola.
- Base multilingüe con cinco locales, preferencia persistente y catálogo con
  fallback seguro a español latinoamericano.
- Perfiles Edge por idioma para ODIN, MÍMIR, HEIMDALL, FREYJA y BROKK.
- El instalador permite seleccionar idioma y configura las voces antes del
  primer inicio.
- Primer bloque visible traducido: ventana principal, panel del comandante,
  métricas de expedición, MÍMIR y HEIMDALL.
- FREYJA traduce sus controles, cuatro modalidades, campos de resultado,
  unidades y estados sin datos según el locale seleccionado.
- BROKK traduce técnicas, controles y resultados sin acoplar los identificadores
  internos de minería al texto visible elegido por cada idioma.
- Guardian traduce inventario, faltantes, destinos de recolección y agente
  tecnológico, conservando los nombres oficiales suministrados por el juego.
- Configuración traduce red, credenciales, proveedor de IA, idioma, modos de
  escucha, calibración y asistencia de atraque.
- El asistente de calibración traduce consentimiento, instrucciones y las siete
  frases de muestra sin cambiar los intents seguros que se guardan internamente.
- Las órdenes locales de comercio, regreso a casa, atraque, visión nocturna,
  colector, tren de aterrizaje e hipersalto reconocen inglés y portugués.
- Whisper y Faster Whisper reciben el idioma seleccionado y prompts operativos
  multilingües; las acciones deterministas no dependen de OpenAI ni Ollama.
- ODIN y FREYJA traducen activación, mensajes de procesamiento, cierre de una
  orden confusa, menú comercial y confirmación de las cuatro modalidades.
- MÍMIR traduce recomendaciones de descenso, valores, First Logged y alertas
  prioritarias de Stratum Tectonicas o Recepta Umbrux.
- HEIMDALL y BROKK traducen los avisos operativos principales de cálculo de
  rutas, contexto ausente, errores y búsquedas de minería o venta.
- Los resúmenes dinámicos de rutas de neutrones, ahorro de saltos, portapapeles,
  sesiones mineras y destinos de venta conservan sus datos dentro de plantillas localizadas.
- HEIMDALL traduce inventario, recomendación, revisión de tramos y autorización
  temporal de inyecciones FSD sin cambiar recetas ni consumir materiales.
- La auditoría residual corrigió valores dinámicos del tablero: ubicación vacía,
  conteo biológico, combustible, estados mineros, riesgos y búsquedas sin resultados.
- MÍMIR traduce también señales, evidencia DSS, recompensas normales o First
  Footfall y el progreso de recolección/distancia mostrado en su pestaña.
- Los diálogos de validación de HEIMDALL, FREYJA, BROKK y Configuración respetan
  el idioma seleccionado, incluidos errores de guardado y confirmaciones.
- El registro operativo localiza el avance de HEIMDALL, la toma de muestras,
  el balance de expedición y los informes biológicos visibles de MÍMIR.
- BROKK localiza el inicio y cierre automático de la operación, niveles de
  bodega, estados y errores de valoración; HEIMDALL localiza el cálculo y la
  replanificación automática por desvío.
- MÍMIR localiza primera pisada, navegación entre muestras y finalización
  biológica; ODIN y FREYJA localizan memoria de órdenes, EDDN, cancelaciones,
  balances, bloqueos, consultas de mercado y resultados Powerplay.
- Los cuatro modelos de FREYJA localizan instrucciones de compra y venta,
  circuitos, expediciones, tonelaje recomendado, penalización por volumen y
  advertencias de antigüedad sin traducir nombres oficiales del juego.
- HEIMDALL localiza las respuestas de cockpit, solicitud de atraque, bindings,
  hipersalto y controles de nave/SRV sin alterar sus validaciones de seguridad.
- FREYJA localiza el seguimiento persistente completo: compra, venta parcial,
  llegada, atraque, siguiente tramo, progreso, cancelación y recálculo bloqueado.
- Auditoría final de voz: MÍMIR localiza la distancia habilitada para la muestra,
  la unión de especies prioritarias y valores desconocidos; HEIMDALL elimina
  los últimos textos fijos de su ruta informativa de atraque.
- Reconocimiento conversacional ampliado en inglés y portugués para FREYJA,
  BROKK y EDDN: inicio, modalidad, estado, venta, cancelación y recálculo.
- La sanitización oral de la ubicación utiliza «este sistema», «this system» o
  «este sistema» según el locale y conserva el nombre si fue solicitado.
- Síntesis FSD reconoce inventario, ruta, distancia y autorización en español,
  inglés y portugués; la autorización exige intención, «FSD» e «inyección» sin
  depender del orden de las palabras.
- La memoria local reconoce confirmar, olvidar y corregir órdenes en los tres
  idiomas manteniendo la asociación limitada a acciones seguras.
- OpenAI y Ollama reciben el mismo prompt de seguridad localizado; el contexto
  vivo traduce comandante, nave, ruta, balance y biología sin alterar nombres
  oficiales de Elite Dangerous.
- Auditoría final de la interfaz: estados residuales de BROKK, red, Guardian,
  pie de ventana y registros de configuración/calibración ya respetan el locale.
- La calibración confirmada aprende duración y nivel RMS por comandante, ajusta
  silencio y sensibilidad dentro de límites seguros y nunca conserva el audio.
- Configuración permite restaurar snapshots de bindings con confirmación
  explícita, validación de manifiesto/XML y respaldo previo obligatorio.
- HEIMDALL compara el plan activo de neutrones con la ruta convencional real
  de Elite cuando ambos destinos coinciden, mostrando saltos y diferencia.
- Configuración reserva un pie fijo para que Aceptar y Cancelar sigan visibles
  con baja resolución o escalado alto de Windows.
- General, Credenciales y HEIMDALL incorporan desplazamiento vertical propio
  sin mover el pie fijo de Aceptar y Cancelar.
- HEIMDALL audita la disponibilidad de los parámetros físicos exigidos por
  Galaxy Plotter y no habilita una ruta exacta con datos incompletos.
- El constructor de Galaxy Plotter valida destino y carga, y rechaza cualquier
  solicitud si falta una constante física en lugar de estimarla.
- Cliente asíncrono de Galaxy Plotter integrado con lectura por salto de
  combustible, repostaje, scoopables y neutrones; todavía no se activa desde
  la interfaz si la auditoría física no está completa.
- HEIMDALL resuelve las constantes base del FSD desde el `modules.json` local
  de EDMarketConnector y aplica encima los modificadores reales de `Loadout`;
  ODIN no redistribuye ni aproxima esa base de datos.
- Simulación integral para los cinco locales: perfiles Edge, siete órdenes
  seguras, intents invariantes, alerta científica y resumen de síntesis FSD.
- 526 pruebas automáticas superadas tras integrar BROKK, la prueba larga de
  HEIMDALL, la calibración de voz y la infraestructura multilingüe.

## v0.8.0-beta — BROKK

- Nuevo oficial de minería BROKK con pestaña desplazable propia.
- Inicio automático de la operación al refinar la primera tonelada.
- Cierre automático al abandonar la zona de minería y resumen de rendimiento.
- Persistencia de sesión, carga refinada, ventas, descartes y transferencias al carrier.
- Auditoría del equipamiento para láser, abrasión, subsuperficie y núcleo profundo.
- Registro de asteroides prospectados, composición y materias primas de ingeniería.
- Alertas no repetitivas de bodega al 75, 90 y 100 por ciento.
- Búsqueda de zonas mineras corta, media y larga mediante datos comunitarios.
- Entrega del destino elegido a HEIMDALL mediante el EventBus.
- Valoración de venta bajo demanda, con tres categorías de distancia y límite de 900 años luz.
- Manifiesto local BROKK→FREYJA sin envío automático de carga ni ubicación.
- Consultas y órdenes de minería por voz con respuestas propias de BROKK.
- Correcciones de voz para hipersalto y tren de aterrizaje mediante bindings reales.
- OpenAI configurable por comandante; Ollama continúa disponible como opción local.
- Interfaz e instalador identificados como ODIN 0.8.0-beta.
- 478 pruebas automáticas superadas antes de compilar la distribución.

## v0.4.0 — Exploration Capability

- Procesamiento de eventos Scan.
- Registro de estrellas, planetas y lunas en SQLite.
- Seguimiento del progreso del FSS.
- Detección de sistemas completamente identificados.
- Registro de cartografía DSS.
- Detección de bonificación de eficiencia DSS.
- Registro de señales biológicas.
- Registro preparado para muestras orgánicas.
- Informes contextuales de exploración.
- Recomendaciones automáticas según el estado del sistema.
- Sincronización con CommanderState.
- Publicación de informes mediante eventos internos de ODIN.
