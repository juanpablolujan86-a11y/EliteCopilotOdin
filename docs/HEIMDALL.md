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

La segunda etapa integrará Galaxy Plotter (`generic/route`) cuando ODIN pueda
extraer de forma fiable masa, constantes completas del FSD, depósitos y
bonificaciones. No se enviarán parámetros estimados a ese calculador.

### Fase 5 — Asistencia de cabina

- Descubrir y respetar los bindings del comandante.
- Controlar luces y visión nocturna con estado verificable.
- Implementar solicitud de aterrizaje como macro contextual y opcional.
- Incorporar modo simulación que informa sin pulsar teclas.

### Fase 6 — Pruebas reales

- Rutas cortas convencionales.
- Rutas con repostaje.
- Ruta de neutrones.
- Desvío y replanificación.
- Acciones de cabina en condiciones seguras.
- Pruebas de recuperación ante interfaz inesperada.

No se generará una nueva distribución de ODIN hasta que HEIMDALL alcance
como mínimo un 80 % de estas capacidades operativas y verificadas.
