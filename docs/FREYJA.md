# FREYJA — Oficial de Comercio

## Misión

FREYJA transforma precios de mercado verificables en rutas comerciales
factibles para la nave y la economía reales del comandante. Nunca presenta una
ganancia teórica como garantizada: conserva la hora de actualización, demanda,
oferta y restricciones de acceso de cada estación.

## Perfil operativo del comandante

Toda planificación utiliza automáticamente:

- sistema y estación actuales;
- créditos disponibles y reserva mínima configurable;
- capacidad libre de carga;
- alcance de salto con carga;
- tamaño de plataforma requerido;
- combustible, autonomía y estrellas scoopables;
- permisos conocidos y sistemas excluidos;
- capacidad de aterrizaje planetario;
- preferencia por estaciones orbitales o de superficie;
- antigüedad máxima aceptable de los precios.

Si falta un dato que afecte la factibilidad, FREYJA lo declara y calcula de
forma conservadora.

## Estrategias

### 1. Ruta rápida

Busca una operación simple de compra y venta con el mejor rendimiento estimado
por minuto, no sólo el mayor margen por tonelada.

- una compra y una venta;
- pocos saltos y poca distancia hasta las estaciones;
- demanda suficiente para la carga propuesta;
- preferencia por llenar la bodega, aceptando hasta un 8% de reducción estimada
  por venta masiva cuando permite transportar más toneladas;
- inversión limitada por los créditos disponibles;
- precios recientes;
- opción de repetir el circuito cuando siga siendo rentable.

### 2. Cadena de tres estaciones

Construye un ciclo factible `A → B → C → A`. Puede transportar hasta tres
productos diferentes, uno por tramo, evitando trayectos vacíos cuando exista
una alternativa rentable.

- exactamente tres estaciones compatibles con la nave;
- hasta tres productos independientes;
- compra, demanda y capacidad comprobadas en cada tramo;
- beneficio neto del circuito completo;
- tiempo, saltos y riesgo de datos obsoletos visibles;
- posibilidad de abandonar un producto sin invalidar toda la cadena.

El optimizador ya valida circuitos cerrados `A → B → C → A`, calcula cada
tramo con el perfil real y descarta el circuito completo si una estación o una
operación no es factible.

### 3. Expedición comercial de hasta 30 saltos

Optimiza el beneficio total bajo un presupuesto máximo de 30 saltos. Puede
encadenar más estaciones, pero no tiene obligación de utilizar los 30 saltos si
una ruta más corta ofrece mejor rendimiento o menor riesgo.

- máximo de 30 saltos reales estimados;
- múltiples compras y ventas;
- repostaje y autonomía comprobados por NJÖRÐR;
- reserva de créditos protegida;
- penalización por precios antiguos, baja demanda y estaciones lejanas;
- recálculo cuando cambian el inventario, los precios o la ruta del juego;
- progreso persistente y siguiente estación copiada sólo tras llegada
  confirmada.

El optimizador encadena operaciones mediante una búsqueda acotada, descarta
tramos desconectados o inviables y nunca supera el presupuesto configurado de
30 saltos. El seguimiento de la ruta queda guardado entre reinicios. FREYJA
confirma las llegadas mediante el Journal, copia al portapapeles el sistema de
compra o venta correspondiente y sólo avanza al siguiente tramo después de
confirmar la venta completa, incluidas las ventas parciales.

## Función objetivo

FREYJA puntúa cada plan usando:

1. beneficio neto estimado;
2. beneficio por minuto;
3. beneficio por salto;
4. capital inmovilizado;
5. antigüedad de los precios;
6. oferta y demanda disponibles;
7. distancia en segundos-luz hasta la estación;
8. cantidad de aterrizajes y saltos;
9. riesgo de permiso, plataforma o aterrizaje incompatible.

El comandante podrá priorizar beneficio total, velocidad o seguridad sin tener
que configurar manualmente todos los parámetros.

## Fuentes de datos

- Journal y archivos de mercado locales: fuente primaria para operaciones e
  inventario propios.
- Datos comunitarios con marca temporal: búsqueda de oportunidades externas.
- NJÖRÐR: factibilidad de saltos, combustible y progreso de navegación.

Inara no se usará como buscador general de mercados mediante su API. La fuente
comunitaria deberá permitir consultar o mantener datos de mercado con oferta,
demanda y fecha de actualización.

## Seguridad

- FREYJA no compra ni vende automáticamente.
- No recomienda más unidades que la demanda observada o la capacidad libre.
- Informa cuántas toneladas conviene comprar y vender en esa estación para
  conservar el precio comunitario estimado; si la demanda cambia, recalcula.
- Entre rutas con una diferencia de rendimiento de hasta el 8%, prioriza la que
  utiliza una proporción mayor de la bodega.
- No utiliza créditos reservados por el comandante.
- No oculta precios antiguos ni accesos inciertos.
- Las rutas se recalculan ante desvíos o cambios relevantes.
