# Integración de ODIN con EDDN

ODIN puede contribuir información pública de Elite Dangerous a Elite
Dangerous Data Network (EDDN). EDDN retransmite estos datos a consumidores
comunitarios como EDSM, Inara y Spansh.

## Estado predeterminado

En una instalación nueva, la captura y la transmisión están desactivadas. El
modo de pruebas está activado para impedir que una configuración incompleta
publique accidentalmente en los esquemas reales.

La configuración se controla con estas claves de `config.json`:

```json
{
  "eddn_capture_enabled": true,
  "eddn_upload_enabled": true,
  "eddn_test_mode": false
}
```

- `eddn_capture_enabled`: prepara eventos compatibles y los guarda en la cola.
- `eddn_upload_enabled`: permite al trabajador HTTP procesar la cola.
- `eddn_test_mode`: usa esquemas `/test`. Debe cambiarse expresamente a
  `false` para contribuir a los esquemas públicos.

ODIN muestra el modo efectivo durante el inicio. También se puede preguntar
por voz: **"estado de EDDN"**.

## Información compartida

ODIN puede publicar los siguientes eventos astronómicos admitidos por el
esquema `journal/1`:

- ubicaciones, saltos y saltos de portanaves;
- atraques;
- escaneos astronómicos;
- señales de superficie;
- entradas del Códice.

Al abrir el mercado de una estación, también puede publicar mediante
`commodity/3`:

- nombre del sistema y de la estación;
- identificador público del mercado;
- precios medios, de compra y de venta;
- oferta, demanda y sus niveles.

ODIN comprueba que `Market.json` coincida con el evento actual en mercado,
sistema y estación. No publica un archivo antiguo o perteneciente a otra
estación.

## Información excluida

Los mensajes no incluyen:

- nombre, FID, créditos o reputación del comandante;
- combustible, multas o estado privado de la nave;
- coordenadas de superficie;
- nombres localizados (`*_Localised`);
- mercancías ilegales o no comercializables;
- claves de ElevenLabs, EDSM, Inara u otros servicios.

El identificador de carga se genera localmente de forma aleatoria y permanece
estable en esa instalación. EDDN ofusca además el identificador recibido.

## Cola y errores

La cola SQLite evita duplicados y conserva los mensajes durante fallos de red.
Los reintentos respetan un mínimo de un minuto. Las respuestas HTTP 400 y 426
se consideran definitivas y no se reintentan.

- aceptados: se conservan 30 días;
- rechazados: se conservan 90 días;
- pendientes: no se eliminan automáticamente.

Los resultados técnicos se registran en `%LOCALAPPDATA%\ODIN\logs\odin.log`.

## Desactivación

Para detener inmediatamente nuevos envíos, establecer:

```json
{
  "eddn_capture_enabled": false,
  "eddn_upload_enabled": false
}
```

El cambio entra en vigor al reiniciar ODIN. Desactivar la captura impide que
se agreguen eventos nuevos; desactivar la transmisión conserva pendientes para
una posible reanudación posterior.
