# HEIMDALL — Oficial de Navegación y Asistencia de Cabina

## Misión

HEIMDALL ayuda al comandante a planificar, ejecutar y revisar rutas de salto.
Su especialidad es la navegación interestelar, incluidas las autopistas de
neutrones, la autonomía de combustible y la replanificación durante el viaje.

HEIMDALL también puede realizar un conjunto reducido de acciones de cabina
no intrusivas. Estas acciones nunca sustituyen el pilotaje del comandante.

## Capacidades de navegación

- Conocer el sistema actual y el destino.
- Mantener un plan de ruta persistente.
- Calcular saltos restantes y distancia restante.
- Comparar rutas convencionales y rutas mediante estrellas de neutrones.
- Considerar alcance FSD, combustible disponible y estrellas scoopables.
- Advertir tramos con riesgo de quedar sin combustible.
- Considerar saltos asistidos por síntesis cuando el comandante los autorice.
- Detectar desvíos y proponer una replanificación.
- Presentar y copiar el siguiente sistema de la ruta.
- Registrar la ruta planificada y la ruta realmente recorrida.

## Asistencia mínima de cabina

Acciones previstas:

- Encender o apagar luces.
- Encender o apagar visión nocturna.
- Ayudar a solicitar permiso de aterrizaje.

La solicitud de aterrizaje exige una validación especial porque Elite
Dangerous no ofrece una orden directa en el Journal: normalmente requiere
interactuar con el panel de contactos. HEIMDALL deberá comprobar el contexto,
ejecutar una secuencia configurable y verificar el resultado mediante los
eventos posteriores del juego.

La primera etapa segura ya está operativa en modo informativo. HEIMDALL
reconoce solicitudes naturales de aterrizaje o atraque, consulta `Status.json`,
comprueba que el comandante esté en la nave principal y bloquea la orden si la
nave ya está atracada, está en superficie o continúa en supercrucero. También
resuelve `OrderRequestDock` desde el perfil de controles activo. Esta etapa no
envía pulsaciones; la ejecución real seguirá desactivada hasta incorporar
confirmación posterior, intervalo contra repeticiones y una prueba dentro del
juego.

## Custodia de configuraciones de controles

HEIMDALL será responsable de conocer y preservar los perfiles de controles
de Elite Dangerous. Esta capacidad protege la configuración del comandante y
permite resolver qué binding corresponde a cada asistencia autorizada.

Funciones previstas:

- Descubrir la carpeta de bindings de la instalación activa.
- Detectar los selectores `StartPreset*.start` y sus perfiles activos.
- Importar los archivos `.binds` XML sin modificarlos.
- Resolver bindings primarios y secundarios por acción y dispositivo.
- Conservar idioma y distribución de teclado de cada perfil.
- Crear snapshots versionados con fecha, versión del juego y hash.
- Detectar cambios realizados por el juego o por el comandante.
- Validar XML, acciones duplicadas y dispositivos ausentes.
- Informar errores presentes en `BindingLoadingErrors.log`.
- Restaurar una copia solamente con autorización explícita.

Los respaldos se guardarán dentro de los datos de ODIN, nunca mezclados con
los archivos originales del juego. La lectura y el respaldo podrán ser
automáticos; cualquier restauración, sobrescritura o modificación requerirá
confirmación del comandante.

HEIMDALL soportará varios perfiles simultáneos y no asumirá que todos usan
el mismo teclado o los mismos periféricos. En la instalación de prueba se
observaron perfiles `Custom` (`es-AR`) y `GameGlass` (`en-US`).

## Límites de seguridad

HEIMDALL no podrá:

- Controlar rumbo, cabeceo, alabeo o aceleración.
- Activar supercrucero o iniciar un salto sin una orden explícita.
- Disparar armas o desplegar puntos de anclaje.
- Operar en menús sin conocer el contexto de interfaz.
- Repetir una acción si no puede determinar su estado.
- Ejecutar acciones de cabina durante combate o una situación incompatible.

Todas las automatizaciones serán:

- opcionales;
- configurables por el comandante;
- breves y reversibles;
- registradas en `heimdall.log`;
- protegidas por intervalos contra repeticiones;
- desactivables mediante un modo exclusivamente informativo.

## Arquitectura prevista

```text
Journal + Status.json + configuración de nave
                    |
                    v
             HEIMDALL Context
                    |
        +-----------+-----------+
        |                       |
        v                       v
 Route Planner           Cabin Assistant
        |                       |
        v                       v
 Plan de navegación      Acción segura opcional
        |                       |
        +-----------+-----------+
                    v
            Informe de HEIMDALL
```

HEIMDALL se comunicará mediante el EventBus y no accederá directamente a
MÍMIR ni a otros oficiales.

## Etapas hasta el 80–90 % operativo

### Fase 1 — Contexto de navegación

- Leer nave, FSD, combustible y alcance disponibles.
- Detectar destino, ruta activa y cada salto completado.
- Crear modelos tipados y memoria persistente de ruta.

### Fase 1.1 — Custodia de bindings

- Descubrir perfiles y selectores activos por versión del juego.
- Parsear acciones, teclas, modificadores y dispositivos.
- Crear respaldos con hash y detectar cambios.
- Validar errores de carga y dispositivos faltantes.
- Exponer bindings resueltos al asistente de cabina.

### Fase 2 — Ruta convencional

- Crear y seguir un plan de sistemas.
- Calcular distancia y saltos restantes.
- Detectar desvíos y rutas incompletas.

### Fase 3 — Combustible

- Estimar consumo y autonomía.
- Identificar estrellas scoopables.
- Advertir segmentos inseguros.

### Fase 4 — Autopistas de neutrones

- Incorporar datos de estrellas de neutrones.
- Comparar tiempo, distancia, seguridad y desgaste.
- Guiar la secuencia de sobrecarga y siguiente waypoint.

#### Inyecciones FSD

HEIMDALL mantiene un inventario persistente de las materias primas necesarias
para las inyecciones FSD básica (+25%), estándar (+50%) y premium (+100%). Se
reconstruye desde `Materials` y se actualiza con recolecciones, descartes,
intercambios, recompensas de misión y eventos de síntesis. Ante una consulta por
voz informa cuántas inyecciones de cada grado pueden fabricarse.

El inventario es informativo: HEIMDALL no fabrica ni consume una inyección y no
la agrega a una ruta sin autorización explícita del comandante.

También puede evaluar un salto indicado por voz, por ejemplo: «¿puedo saltar
95 años luz con una inyección?». Utiliza el alcance real de la nave, selecciona
el grado mínimo suficiente, comprueba la disponibilidad de materiales y avisa
si el salto excede incluso el alcance premium. La evaluación no consume los
materiales ni activa la síntesis.

Cuando existe una ruta en `NavRoute.json`, HEIMDALL puede revisar todos los
tramos futuros desde el sistema actual. Omite los segmentos que parten de una
estrella de neutrones o enana blanca, porque pertenecen a la supercarga por
cono, y sólo marca los saltos convencionales que exceden el alcance normal. La
consulta «¿necesito alguna inyección en esta ruta?» informa el primer tramo
problemático, su distancia, el grado mínimo y si existen materiales.

Si la inyección es factible, HEIMDALL abre una propuesta temporal de 60
segundos. La frase exacta «autorizo la inyección FSD» registra una autorización
de un solo uso vinculada a esa propuesta; una confirmación sin propuesta,
vencida o sin materiales es rechazada. En esta etapa la autorización habilita
únicamente la guía para realizar la síntesis manual desde el panel de
inventario. ODIN no envía pulsaciones y el evento `Synthesis` actualiza después
el inventario conocido.

#### Fuente comunitaria de rutas

HEIMDALL utiliza Spansh como proveedor externo de rutas rápidas. No mantiene
una lista fija de “autopistas”: solicita una ruta nueva desde el sistema real
del comandante, usando el alcance actual de la nave y el destino indicado.

- API y documentación: https://docs.spansh.co.uk/
- Planificador: https://spansh.co.uk/
- Estrategia inicial: `neutron_fastest`, eficiencia 60.
- Cada resultado se persiste con proveedor, parámetros y respuesta original.
- El campo `jumps` de cada punto de control indica los saltos convencionales
  necesarios para alcanzarlo; un waypoint lejano no se interpreta como salto
  directo.

Al recibir una ruta, HEIMDALL también calcula una referencia convencional
mínima mediante `ceil(distancia / alcance_actual)`. La presenta expresamente
como límite inferior teórico, porque no considera densidad estelar, permisos ni
la ruta concreta del mapa galáctico. Si la autopista no mejora siquiera esa
referencia, HEIMDALL lo advierte en lugar de afirmar que la ruta de neutrones es
más rápida. Galaxy Plotter seguirá siendo necesario para una comparación
convencional exacta.

La segunda etapa integrará Galaxy Plotter (`generic/route`) cuando ODIN pueda
extraer de forma fiable masa, constantes completas del FSD, depósitos y
bonificaciones. No se enviarán parámetros estimados a ese calculador.

#### Seguimiento mediante portapapeles

Al crear una ruta, HEIMDALL copia el primer punto de control como texto Unicode
en el portapapeles de Windows. No abre el mapa ni simula teclas: el comandante
decide cuándo pegar el nombre y trazar el recorrido.

Los saltos intermedios se observan sin adelantar el itinerario. Únicamente un
evento `FSDJump` cuyo `StarSystem` coincida exactamente con el punto esperado
incrementa el índice persistente y copia el siguiente sistema. Un evento
repetido no puede saltar dos waypoints. Al llegar al destino final, la ruta se
marca como completada y el portapapeles no se modifica nuevamente.

### Fase 5 — Asistencia de cabina

- Descubrir y respetar los bindings del comandante.
- Controlar luces y visión nocturna con estado verificable.
- Implementar solicitud de aterrizaje como macro contextual y opcional.
- Incorporar modo simulación que informa sin pulsar teclas. **Completado.**

### Fase 6 — Pruebas reales

- Rutas cortas convencionales.
- Rutas con repostaje.
- Ruta de neutrones.
- Desvío y replanificación.
- Acciones de cabina en condiciones seguras.
- Pruebas de recuperación ante interfaz inesperada.

No se generará una nueva distribución de ODIN hasta que HEIMDALL alcance
como mínimo un 80 % de estas capacidades operativas y verificadas.
