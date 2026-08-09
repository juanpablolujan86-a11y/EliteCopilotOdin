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
- [ ] Consultar Canonn

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

- [ ] Definir el alcance operativo
- [x] Registrar ubicaciones de muestras durante la sesión activa
- [x] Ayudar a respetar la distancia mínima entre muestras
- [x] Detectar la primera pisada y preparar para voz la frase:
  «Felicidades, sos el primer descendiente de un mono pulgoso en pisar este
  planeta. Darwin estaría orgulloso de vos.»
- [ ] Diseñar la futura presentación por voz

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
- [ ] Recibir la autorización de Inara para el nombre de aplicación `ODIN`
- [ ] Ejecutar una prueba controlada de Inara antes de habilitar su transmisión

---

## Sprint 5 - Primer Oficial

- [ ] Voz
- [ ] Comandos
- [ ] Automatización

### Bloqueante para ODIN 1.0

- [ ] Adaptación acústica local por comandante: aprender pronunciación y ritmo
  a partir de muestras confirmadas, con consentimiento, opción de borrar el
  perfil y aislamiento completo entre comandantes.
- [x] Memoria semántica local de órdenes, alias y correcciones por comandante.

---

## HEIMDALL - Navegación y asistencia mínima

- [x] Contexto de nave, FSD, combustible y destino
- [x] Descubrir y respaldar perfiles `.binds`
- [x] Detectar perfil activo, errores y dispositivos ausentes
- [x] Resolver teclas por acción sin modificar originales
- [ ] Restaurar bindings solamente con autorización explícita
- [ ] Planificador de rutas convencionales
- [x] Autonomía y estrellas scoopables
- [ ] Autopistas de neutrones
  - [x] Detectar waypoints de neutrones y enanas blancas
  - [x] Registrar carga de cono y salto potenciado sin duplicados
  - [x] Conservar salud real conocida del FSD y exposiciones de sesión
  - [ ] Comparar ruta convencional y ruta de neutrones
    - [x] Integrar planificador comunitario Spansh y persistir resultados
    - [x] Usar automáticamente sistema actual y alcance real de la nave
    - [x] Comparar contra un límite inferior convencional conservador
    - [ ] Incorporar parámetros físicos completos para Galaxy Plotter exacto
  - [ ] Guiar la secuencia segura de sobrecarga
    - [x] Copiar el primer waypoint al crear la ruta
    - [x] Avanzar y copiar el siguiente solamente tras `FSDJump` confirmado
    - [x] Persistir el índice y evitar avances duplicados
    - [x] Mostrar durante la autopista el progreso de la expedición: saltos
      realizados, saltos restantes y total de saltos previsto hasta el destino
    - [ ] Guiar entrada al cono, carga y salida segura
- [ ] Síntesis de salto autorizada
  - [x] Reconstruir y mantener el inventario de materias primas
  - [x] Calcular inyecciones básicas, estándar y premium disponibles
  - [x] Responder consultas por voz sin consumir materiales
  - [ ] Proponer una inyección sólo cuando resuelva un salto inaccesible
  - [ ] Exigir autorización antes de cualquier uso
- [ ] Replanificación por desvío
- [ ] Luces y visión nocturna opcionales
- [ ] Solicitud contextual de aterrizaje
- [x] Modo informativo sin pulsaciones
- [x] Registro persistente `heimdall.log`
# FREYJA / Powerplay

- [x] Leer afiliaci\u00f3n, rango y m\u00e9ritos del comandante desde el Journal.
- [x] Filtrar comercio por potencia, estado territorial y margen m\u00ednimo elegible.
- [x] Mantener separados el beneficio exacto en cr\u00e9ditos y los m\u00e9ritos por confirmar.
- [ ] Validar en el juego los m\u00e9ritos reales otorgados por cada venta y calibrar la estimaci\u00f3n.
