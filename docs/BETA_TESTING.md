# ODIN v0.8.1-beta-pre-IA — Guía para comandantes de prueba

Esta beta incorpora BROKK. Para una prueba minera por láser:

1. Indique el mineral objetivo o pida por voz `ODIN, quiero minar platino`.
2. Confirme las alternativas corta, media y larga para llegar a un hotspot conocido.
3. Verifique que la operación comience al entrar la primera tonelada refinada.
4. Compruebe bodega, limpets, composición, materiales y toneladas por hora.
5. Abandone la zona y confirme el cierre y el resumen de rendimiento.
6. Use `BUSCAR DÓNDE VENDER` únicamente cuando quiera consultar precios comunitarios.

Las técnicas de abrasión, subsuperficie y núcleo profundo pueden seleccionarse
en BROKK y permanecen pendientes de validación real. El Journal confirma el
núcleo mediante `AsteroidCracked`; abrasión y subsuperficie se muestran como
seleccionadas por el comandante porque el juego no identifica su procedencia.
La prueba minera Powerplay está aplazada y no bloquea el cierre de esta beta.

Las secuencias virtuales de las tres técnicas avanzadas cubren selección,
prospección, primera tonelada, persistencia y cierre al abandonar la zona. La
prueba dentro de Elite sigue siendo necesaria para validar los eventos reales.

## Instalación

1. Cierre cualquier copia anterior de ODIN.
2. Ejecute `ODIN-v0.8.1-beta-pre-IA-Setup-win64.exe`.
3. Mantenga marcada la opción de Ollama si desea conversación libre local.
   La descarga de `gemma3:4b` requiere Internet y varios gigabytes.
   Si Ollama ya está instalado, ODIN reutiliza la instalación existente.
4. Elija el idioma inicial: español latinoamericano, español de España,
   inglés de Estados Unidos, inglés del Reino Unido o portugués de Brasil.
5. Inicie Elite Dangerous y después ODIN.

Sin Ollama continúan funcionando el Journal, las voces, MÍMIR, NJÖRÐR,
FREYJA y todas las órdenes operativas programadas.

## Pruebas prioritarias

- MÍMIR: salto, detección biológica, predicción, DSS, filtrado por planeta y
  recolección 1/3–3/3 con distancia.
- NJÖRÐR: síntesis FSD básica con autorización explícita. Compruebe que
  proponga el grado mínimo, no consuma materiales por sí solo y detecte el
  evento de síntesis del Journal. Las rutas de neutrones, el portapapeles, el
  progreso y el recálculo ya superaron pruebas reales prolongadas.
- FREYJA: cuatro modalidades comerciales dentro de la Burbuja.
- BROKK: abrasión, subsuperficie y núcleo profundo con inicio, persistencia y
  cierre de la operación al abandonar la zona minera.
- Voz: activación con ODIN, pulsar para hablar, silenciamiento y registro
  operativo de todas las respuestas. Pruebe el idioma elegido y el asistente
  de calibración acústica con consentimiento explícito.
- Red: si configura credenciales propias, confirme EDSM, EDDN e Inara sin
  incluir nunca las claves en el informe de prueba.

## Cómo informar un problema

Incluya:

- Qué orden o acción realizó.
- Qué esperaba que ocurriera.
- Qué mostró o dijo ODIN.
- Sistema, planeta o estación implicados, si corresponde.
- Hora aproximada del fallo.

Adjunte los archivos recientes de `%LOCALAPPDATA%\ODIN\logs`. No comparta
archivos con API keys ni capturas que muestren credenciales.

## Limitaciones conocidas

- El instalador todavía no está firmado y Windows SmartScreen puede advertirlo.
- Las rutas comerciales reales dependen de datos comunitarios recientes.
- La fabricación de inyecciones FSD sigue siendo manual: NJÖRÐR propone y
  registra la autorización, pero no envía pulsaciones al panel de inventario.
- Las pruebas controladas de comercio Powerplay no produjeron méritos; ODIN no
  promete méritos y muestra únicamente los confirmados por el Journal.
- Las voces y el instalador están simulados en los cinco idiomas, pero todavía
  requieren validación auditiva en equipos reales de terceros.
