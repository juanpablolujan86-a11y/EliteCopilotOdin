ARCHIVOS DE CREDENCIALES PERSONALES DE ODIN
===========================================

Cada usuario debe completar solamente los servicios que quiera conectar.
Nunca comparta estos archivos ni los agregue a Git.

1. ELEVENLABS_API_KEY.txt
   Clave personal para las voces ElevenLabs. Es opcional porque ODIN puede
   utilizar Edge TTS y voces locales sin clave.

2. EDSM_API_KEY.txt
   COMMANDER: nombre exacto registrado en EDSM.
   API_KEY: clave personal generada en la configuracion de EDSM.

3. INARA_API_KEY.txt
   COMMANDER: nombre exacto del comandante.
   FRONTIER_ID: identificador FID opcional del Journal.
   API_KEY: clave personal generada en Commander Settings de Inara.

Servicios sin clave personal:

- EDDN: ODIN usa un identificador anonimo local; no requiere API key.
- Spansh: las consultas publicas utilizadas por ODIN no requieren API key.
- Ollama: se ejecuta localmente y no requiere API key.
- Edge TTS: no requiere API key personal.

Seguridad:

- Las claves importadas deben migrarse al Administrador de credenciales de
  Windows y luego eliminarse del texto visible.
- Use una clave distinta por comandante cuando el servicio lo permita.
- Si sospecha que una clave fue expuesta, revoquela en el sitio correspondiente
  y genere una nueva.
