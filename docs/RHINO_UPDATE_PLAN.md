# Rhino: preparación de ODIN

Revisión: 4 de septiembre de 2026. Estado: planificación, no integración validada.

## Hechos confirmados

Frontier publicó Rhino el 2 de septiembre. Incluye escáner de depósitos,
refinería, módulo de despliegue de equipos mineros y tres plazas. El DSS detecta
ubicaciones de minería planetaria. Las notas identifican ajustes de densidad,
temperatura, recarga, capacidad y tiempos; no fijar rendimientos universales.

Mercancías anunciadas: Bastnäsite, Deuterium, Diamond, Helium, Helium-3,
Iridium, Magnesite, Olivine, Periclase dunite, Quartz pyroxenite, Ruby,
Sapphire y Thortveitite. Son nombres visibles, no identificadores Journal
verificados. Las notas de lanzamiento señalan un problema de recogida de
9 fragmentos y una corrección prevista a 12; confirmar el hotfix antes de
usar esa cifra como capacidad.

Fuente primaria: [anuncios oficiales de Frontier en Steam](https://steamcommunity.com/app/359320/announcements/),
entrada «Elite Dangerous | Rhino SRV Update», 2 de septiembre de 2026.

## Trabajo propuesto en ODIN

1. Capturar una sesión real: equipamiento, despliegue, DSS, escáner, depósito,
   colocación/recuperación de equipo, refinado, transferencia, regreso y venta.
2. Confirmar los identificadores de vehículo, hangar, mercancías y eventos.
   Crear fixtures anonimizados; no inventar eventos a partir de la pantalla.
3. Revisar `brokk/processor.py`: existe reconocimiento preliminar de Rhino por
   nombre en LaunchSRV y cambio a entorno surface. DockSRV cierra actualmente
   la sesión: comprobar si volver a descargar carga debe mantenerla activa.
4. Separar señales mineras DSS de señales geológicas. Conservar planeta,
   ubicación y fuente sin asumir que toda geología tiene un depósito minero.
5. Separar fragmentos, toneladas refinadas, carga del vehículo y carga de nave.
   La transferencia no constituye nueva producción ni venta; probar duplicados
   del Journal, reinicios y dos vehículos sin sumar dos veces.
6. Adaptar búsqueda de BROKK a superficies y catálogo de mercados de FREYJA
   con identificadores comprobados. Mostrar fecha, demanda, distancia y
   limitaciones cuando falten precios comunitarios.
7. Validar bindings del Rhino antes de habilitar órdenes: no asumir que son
   idénticos al Scarab. Mostrar vehículo/contexto confirmado en GUI.
8. Probar sesión completa y Powerplay por separado. Sólo confirmar méritos
   mediante eventos reales; una venta rentable no demuestra méritos.

La beta 0.8.2 corrige estabilidad e incorpora avisos de actualización; este
documento prepara el siguiente trabajo y no declara soporte completo del Rhino.
