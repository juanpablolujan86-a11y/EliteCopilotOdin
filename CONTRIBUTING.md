# Contribuir a ODIN

Gracias por colaborar con ODIN. El objetivo es mantener un copiloto seguro,
explicable y no intrusivo para Elite Dangerous.

## Antes de comenzar

1. Abra primero un issue describiendo el problema o la mejora.
2. No incluya API keys, Journal personales, nombres reales ni bases de datos del
   comandante.
3. Mantenga las acciones de cabina detrás de autorización explícita y de los
   bindings reales del juego.
4. No afirme como confirmado un dato que provenga únicamente de una predicción
   o de una fuente comunitaria incompleta.

## Entorno de desarrollo

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -q
```

ODIN se distribuye actualmente para Windows. El núcleo debe evitar dependencias
directas del sistema operativo; teclado, portapapeles, audio, secretos, procesos
y controles de cabina se acceden mediante `platform_adapters/`.

## Pull requests

- Parta de `develop` y limite cada cambio a un objetivo concreto.
- Añada o actualice pruebas.
- Ejecute toda la suite antes de enviar el cambio.
- Explique cualquier cambio visible, migración o riesgo de compatibilidad.
- No cambie identificadores internos de oficiales sin una migración. Los nombres
  públicos pueden diferir mediante `core/officer_names.py`.
- No agregue telemetría ni transmisión de datos sin consentimiento explícito.
- Al contribuir, declara que puede aportar el cambio bajo `GPL-3.0-only`.

## Credenciales

Las preferencias no sensibles pueden almacenarse en JSON o SQLite. Los secretos
deben usar `security.SecretStore`; nunca se permite un fallback a texto plano.
Los archivos `*_API_KEY.example.txt` contienen únicamente marcadores de ejemplo.
