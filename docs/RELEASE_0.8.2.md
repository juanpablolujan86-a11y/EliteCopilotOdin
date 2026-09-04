# ODIN 0.8.2 beta

Incluye la interfaz ampliada, nombres actualizados de oficiales y las mejoras
recientes de mercados, Powerplay y reconocimiento de tren de aterrizaje.

## Correcciones de revisión

- SQLite recupera correctamente el contador de transacciones incluso cuando falla el guardado.
- Combate Powerplay exige participación de la potencia del comandante también en estados explícitamente disputados.
- Se retiran las activaciones ambiguas «all in» y «Aline».

## Actualizaciones

Al abrir la interfaz, ODIN consulta en segundo plano las versiones públicas de
este repositorio en GitHub. Las betas también detectan nuevas betas. Cuando hay
una versión superior, ofrece abrir su página de descarga. La instalación sigue
siendo manual. No se envían datos del comandante ni se utiliza OpenAI.

La primera actualización desde 0.8.1 debe descargarse manualmente: esa versión
no contiene el comprobador. Sin Internet, ODIN continúa funcionando.

Esta beta incluye la integración opcional de IA en desarrollo. No implica que
las funciones experimentales ni todas las técnicas mineras estén validadas en
el juego. Powerplay comercial sigue pendiente de validación de méritos.
