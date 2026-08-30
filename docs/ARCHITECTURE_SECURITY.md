# Arquitectura, plataforma y seguridad

## Decisiones vigentes

- ODIN continúa siendo **Windows-first** mientras Elite Dangerous y las pruebas
  reales se concentren en Windows.
- El núcleo no debe depender directamente de APIs nativas.
- Las implementaciones específicas se seleccionan en `platform_adapters/`.
- Una plataforma sin implementación debe fallar explícitamente; no se simulan
  teclas ni se degradan secretos a texto plano.

## Adaptadores actuales

- almacén seguro de credenciales;
- portapapeles;
- teclas globales;
- protección de instancia única;
- reproducción MP3 y síntesis local;
- políticas de procesos ocultos;
- envío controlado de bindings a Elite Dangerous.

## Nombres públicos e identificadores internos

Los nombres públicos son NJÖRÐR para navegación, HEIMDALL para tecnología
Guardian y VÖLUNDR para ingeniería. Los identificadores internos históricos se
conservan hasta disponer de una migración versionada.

## Datos y credenciales

- SQLite y JSON almacenan estado y preferencias no sensibles.
- Las API keys se guardan mediante `SecretStore`.
- Windows usa Credential Manager.
- Los importadores TXT son transitorios: migran la clave y reemplazan el valor
  visible por un marcador.
- Logs, diagnósticos y solicitudes de IA no deben contener secretos.

## Publicación

Antes de hacer público el repositorio se debe:

1. ejecutar la suite completa;
2. revisar secretos en el árbol y el historial;
3. verificar que `GPL-3.0-only` y los avisos de terceros estén incluidos;
4. habilitar informes privados de vulnerabilidades;
5. publicar binarios únicamente mediante Releases verificables.
