# ODIN 0.8.3-beta — mantenimiento de instalación de voz

Basada en la publicación 0.8.2-beta, no en la rama experimental de desarrollo.
No incorpora los cambios posteriores de IA, Rhino, perfiles de combate ni
alarma de interdicción. Conserva las limitaciones funcionales de la 0.8.2.

## Reparación para comandantes

1. Cerrar ODIN e instalar esta actualización con el mismo usuario de Windows.
2. Marcar la instalación de voz local y permitir terminar las descargas.
3. Si se omitió: Inicio → ODIN → Reparar reconocimiento de voz.
4. Esperar la verificación de carga del motor y pulsar Finalizar.
5. Reiniciar ODIN y probar una orden con push-to-talk.

El asistente activa selección automática de reconocimiento después de verificar
Parakeet. No cambia claves API ni borra datos del comandante. Conserva las
carpetas incompletas reemplazadas con sufijo .incomplete- como respaldo.
Ollama no es el motor del micrófono. El instalador de voz necesita Internet;
no se incluyen modelos ni datos personales del desarrollador en el ejecutable.

Al iniciar sin modelos se ofrece instalar; se puede declinar y usar la GUI.
El diagnóstico --check-local-speech RUTA_JSON comprueba que el motor cargue
sin grabar audio, enviar datos ni iniciar ODIN o el juego.

Sigue siendo una beta sin firma digital. La prueba del micrófono, permisos de
Windows y pronunciación debe realizarse en el equipo del comandante.

## Verificación de esta entrega

- 621 pruebas automáticas aprobadas.
- Motor Parakeet cargado desde el ejecutable congelado usando un perfil de
  datos aislado, sin claves API ni Journal personal.
- Transcripción del audio público español del paquete Parakeet verificada
  desde Python. No equivale a una prueba del micrófono ni a instalar en una
  máquina Windows recién creada.
- Instalador compilado con Inno Setup; descarga de modelos requiere conexión.
