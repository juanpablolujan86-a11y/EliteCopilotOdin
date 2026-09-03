# Arquitectura de ODIN

Esta guía describe la estructura que un desarrollador necesita conocer antes de
modificar ODIN. Las decisiones y sus motivos se registran por separado en
[`ArchitectureDecisions.md`](ArchitectureDecisions.md).

## Flujo principal

```text
Elite Dangerous Journal
        |
        v
JournalWatcher -> EventBus -> procesadores y oficiales
                              |       |       |
                              v       v       v
                           SQLite   servicios  interfaz/voz
```

`main.py` prepara configuración, credenciales, plataforma y aplicación. El
`CommandCenter` ensambla los componentes; no debe convertirse en un lugar para
lógica de negocio. Los eventos del juego entran por `journal/`, se adaptan en
`adapters/` y se publican en `core/event_bus.py`. Los consumidores actualizan el
estado persistente, generan informes y notifican a la interfaz.

## Directorios

| Ruta | Responsabilidad |
| --- | --- |
| `adapters/` | Traducción entre eventos externos y modelos internos. |
| `brain/` | Decisiones generales y coordinación de recomendaciones. |
| `core/` | Ensamblado, EventBus, procesadores, diagnósticos y memoria de órdenes. |
| `database/` | Esquema y acceso SQLite. La base local generada no se versiona. |
| `journal/` | Lectura incremental del Journal de Elite Dangerous. |
| `knowledge/` | Datos versionados y herramientas de importación reproducible. |
| `mimir/`, `heimdall/`, `freyja/`, `brokk/` | Dominios de los oficiales especializados. |
| `models/` | Contratos y eventos tipados compartidos. |
| `platform/` | Adaptadores para audio, procesos, portapapeles, hotkeys y controles. |
| `services/` | Integraciones externas y credenciales. |
| `ui/` | Interfaz gráfica, presentación y estado visible. |
| `voice/` | Reconocimiento, síntesis, intenciones y calibración. |
| `tests/` | Pruebas automáticas; cada corrección debe agregar una regresión. |

## Oficiales y nombres públicos

Los identificadores internos históricos se conservan para evitar migraciones
incompatibles. La interfaz utiliza nombres públicos centralizados en
`core/officer_names.py`:

- MÍMIR: ciencia y exobiología.
- NJÖRÐR: navegación y asistencia mínima de cabina (internamente `heimdall`).
- FREYJA: comercio.
- BROKK: minería.
- HEIMDALL: contenido Guardián.
- VÖLUNDR: ingenieros e ingeniería.

No deben escribirse nombres de presentación directamente en módulos nuevos.

## Reglas de dependencia

1. Un oficial no importa otro oficial para pedirle trabajo. La coordinación se
   realiza mediante ODIN, eventos o servicios compartidos.
2. La capa de dominio no debe llamar APIs ni controles específicos de Windows.
3. El conocimiento importado conserva fuente y licencia; MÍMIR lo consume sin
   modificar la copia externa.
4. Las acciones de cabina requieren una orden o configuración explícita del
   comandante.
5. Los secretos se leen mediante `services/secret_store.py`; nunca se agregan
   claves reales al repositorio, logs o capturas.

## Estado, datos y red

Los archivos modificables en ejecución viven bajo `%LOCALAPPDATA%\ODIN`, no
junto al código instalado. SQLite mantiene estado del comandante, expediciones,
operaciones y colas de salida. EDSM, EDDN e Inara son integraciones opcionales;
una falla de red no debe bloquear el procesamiento del Journal.

## Cómo extender ODIN

Para incorporar una capacidad:

1. definir el contrato o evento interno;
2. implementar la lógica en el dominio correspondiente;
3. aislar red o sistema operativo tras un servicio/adaptador;
4. registrar el componente en `CommandCenter`;
5. agregar pruebas en `tests/`;
6. actualizar la guía del oficial y el roadmap si cambia el alcance público.

Antes de enviar cambios, ejecute desde la raíz:

```powershell
python -m unittest discover -s tests -v
```

Consulte [`../CONTRIBUTING.md`](../CONTRIBUTING.md) para el flujo de ramas,
seguridad y pull requests.
# Reflejos conversacionales locales

Las órdenes inequívocas se clasifican primero mediante
`intelligence.reflexes.ReflexResolver`. El motor no usa OpenAI ni Ollama, no
ejecuta acciones y no conserva el texto pronunciado: devuelve únicamente una
intención tipada, el oficial responsable y parámetros validados. `CommandCenter`
mantiene la autorización y ejecución final.

Este nivel cubre inicialmente controles de cabina, atraque, regreso a la base,
rutas de neutrones y apertura del flujo comercial de FREYJA. Las consultas que
no coinciden continúan hacia los oficiales o la conversación con IA.

## Voz local

El reconocimiento de órdenes se obtiene mediante `speech.transcriber`. En modo
`auto`, ODIN prefiere Parakeet TDT 0.6B V3 INT8 y recupera automáticamente con
Faster-Whisper/whisper.cpp cuando el paquete local no está instalado o falla.
Los modelos se mantienen residentes para evitar recargas entre órdenes.

La síntesis admite Kokoro multilingüe INT8 mediante sherpa-onnx. Cada frase se
guarda como WAV en la caché local y la reproducción acepta WAV o MP3. Edge,
Windows y ElevenLabs permanecen disponibles como proveedores alternativos.
Los modelos descargados viven en `%LOCALAPPDATA%\ODIN` y nunca se versionan.
