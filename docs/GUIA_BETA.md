# ODIN v0.6.0 — Guía para pruebas beta

## Inicio

1. Descomprimir toda la carpeta recibida.
2. Iniciar Elite Dangerous.
3. Ejecutar `ODIN.exe`.
4. Mantener abierta la ventana de ODIN durante la sesión de juego.

Es necesario conservar juntos `ODIN.exe` y la carpeta `_internal`. Windows
puede mostrar una advertencia porque esta beta todavía no posee firma digital;
el ejecutable debe obtenerse únicamente del archivo compartido por el autor.

ODIN detecta automáticamente el Journal del usuario. No necesita Python ni
Elite Dangerous Market Connector.

## Información visible durante el vuelo

La pantalla se mantiene deliberadamente silenciosa. Sólo muestra:

- si el sistema figura previamente en EDSM o no posee un registro disponible;
- el nombre del planeta cuando se detecta biología;
- los géneros confirmados por DSS y las especies probables calculadas por MÍMIR.

Los resúmenes FSS, valores, reglas, progreso orgánico y explicaciones extensas
se guardan en los registros para diagnóstico y futura comunicación por voz.

## Qué conviene probar

- Escaneo FSS completo de un sistema.
- Escaneo detallado de planetas con DSS.
- Planetas con una o varias señales biológicas.
- Predicciones de especies y variantes de MÍMIR.
- Progreso de muestras orgánicas 1/3, 2/3 y 3/3.
- Avisos de primera pisada y valor potencial First Logged.

## Cómo enviar un informe

Los registros se guardan en:

`%LOCALAPPDATA%\ODIN\logs`

Enviar los archivos `odin.log` y `mimir.log`, junto con una descripción breve
de lo que ocurrió y lo que se esperaba. Los archivos rotan automáticamente y
no crecen indefinidamente.

La memoria local se guarda en `%LOCALAPPDATA%\ODIN\database\odin.db`.

## Privacidad

`mimir.log` incluye los cuerpos evaluados, incluso cuando no hubo interés
biológico, además de recomendaciones, muestreos y fallos del oficial.

Los registros de ODIN resumen decisiones y errores. No es necesario enviar
el Journal completo salvo que el desarrollador lo solicite expresamente para
reproducir un caso concreto.
