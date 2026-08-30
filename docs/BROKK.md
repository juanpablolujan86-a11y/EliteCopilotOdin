# BROKK — Oficial de Minería e Ingeniería de Recursos

## Misión

BROKK asiste al comandante durante una operación minera completa: prepara la
nave, registra la prospección, controla la bodega y los limpets, sigue el
refinado y calcula el valor aproximado de la carga. No pilota, dispara,
recolecta ni vende automáticamente.

Su objetivo es maximizar el rendimiento real por tiempo de operación sin
confundir una estimación de mercado con una recompensa garantizada.

## Modos de minería

1. Láser de superficie.
2. Depósitos subsuperficiales.
3. Abrasión de superficie.
4. Núcleo profundo.

El comandante podrá pedir un material concreto o permitir que BROKK priorice
valor, disponibilidad o una prueba de Powerplay.

## Búsqueda de zonas mineras

Ante una orden como `quiero minar platino`, BROKK buscará zonas compatibles
desde la ubicación actual. La selección debe considerar:

- compatibilidad real entre el mineral, el tipo de anillo y la técnica;
- hotspot conocido y nivel de reservas del sistema;
- distancia en años luz y distancia interna hasta el cuerpo;
- autonomía y rango de salto de la nave actual;
- antigüedad y procedencia de los datos comunitarios.

BROKK presentará varias alternativas ordenadas, indicará la fuente y la fecha
de los datos y entregará el destino elegido a NJÖRÐR mediante un evento. No
afirmará que un mineral está garantizado: los hotspots comunitarios son datos
conocidos y pueden estar incompletos o desactualizados.

## Flujo operativo

```text
Orden del comandante
        |
        v
Preparación de nave y objetivo
        |
        v
Entrada al anillo o cinturón
        |
        v
Prospección -> selección de asteroide -> extracción
        |                                      |
        +----------------> recolección --------+
                                               |
                                               v
                                  refinado y control de bodega
                                               |
                                               v
                                  resumen y destino de venta
                                               |
                                               v
                               venta normal o prueba Powerplay
```

## Datos de entrada

- `Loadout`: nave y módulos instalados.
- `Cargo`: capacidad ocupada y mercancías transportadas.
- `ProspectedAsteroid`: composición y materiales del asteroide.
- `MiningRefined`: unidad refinada que entra en la bodega.
- `AsteroidCracked`: apertura de un núcleo profundo.
- `CollectCargo` y `EjectCargo`: recolección y descarte.
- `MaterialCollected`: materias primas de ingeniería obtenidas.
- `MarketSell`: venta real, precio, cantidad y beneficio observable.
- Eventos de ubicación y `Status.json`: contexto operativo.

El Journal confirma de forma inequívoca el núcleo profundo mediante
`AsteroidCracked`, pero no identifica por separado si cada tonelada refinada
provino de abrasión o de un depósito subsuperficial. Por eso esas técnicas se
seleccionan en la pestaña de BROKK y se muestran como declaradas por el
comandante; nunca se presentan como confirmadas automáticamente.

Los precios externos se usarán con fecha, demanda y compatibilidad de
plataforma. BROKK entregará la carga terminada a la planificación comercial
mediante eventos; no consultará directamente a FREYJA.

## Estado persistente

- sistema, cuerpo, anillo y zona minera;
- hora de inicio y duración;
- técnica activa;
- asteroides prospectados y descartados;
- composición del asteroide seleccionado;
- toneladas refinadas por mineral;
- materias primas de ingeniería recogidas;
- espacio libre, ocupación y limpets conocidos;
- valor estimado y valor finalmente vendido;
- toneladas por hora y créditos por hora;
- procedencia continua de cada lote para auditar Powerplay.

Al vender o descargar una parte, BROKK descontará solamente esa cantidad. La
operación no vuelve a cero hasta agotar la carga minera registrada o hasta que
el comandante la cierre expresamente.

## Informes y avisos

- configuración incompleta para la técnica solicitada;
- asteroide que supera el umbral configurado de concentración;
- detección de núcleo y confirmación de fractura;
- bodega al 75%, 90% y 100%;
- falta probable de limpets o espacio de refinería;
- objetivo de toneladas alcanzado;
- operación terminada y resumen de rendimiento;
- venta confirmada y resultado observado de Powerplay.

No leerá cada fragmento, cada limpet ni cada tonelada refinada.

## Interfaz

La pestaña `BROKK`, con desplazamiento vertical, mostrará:

- estado y ubicación minera;
- objetivo seleccionado y técnica;
- composición del último asteroide prospectado;
- bodega usada/libre y limpets conocidos;
- listado vertical de minerales y toneladas refinadas;
- materias primas de ingeniería recogidas;
- valor aproximado, toneladas/hora y créditos/hora;
- controles para iniciar, pausar o cerrar la operación;
- búsqueda de destino de venta;
- opción separada `PRUEBA POWERPLAY`.

## Prueba Powerplay

Estado: aplazada. Las pruebas comerciales controladas realizadas durante el
desarrollo no produjeron méritos observables. La capacidad conserva su
trazabilidad, pero no bloqueará la versión 1.0 y BROKK nunca prometerá méritos.

Usará exclusivamente minerales extraídos por la nave durante la sesión y
transportados directamente al destino. Registrará potencia, estado territorial,
actividad local mostrada por el mapa, mineral, toneladas, precio, lotes de una
o varias toneladas, paso por carrier y eventos de méritos antes y después.

BROKK nunca afirmará que una venta generará méritos antes de observar el
evento correspondiente en el Journal.

## Límites de seguridad

- No controla la nave ni acciona herramientas mineras.
- No expulsa carga ni abandona limpets.
- No vende ni transfiere mercancía.
- No inventa reservas, concentraciones, demanda ni precios.
- No mezcla mercancía comprada con mineral extraído al evaluar Powerplay.
- No bloquea el Journal durante consultas externas.

## Criterio de cierre beta

BROKK está listo para beta porque completa, persiste y reconstruye una sesión
de minería por láser, muestra correctamente bodega y refinado y calcula su
rendimiento. Núcleo, subsuperficie y abrasión se validarán como capacidades
posteriores; Powerplay queda aplazado.
