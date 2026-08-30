# Knowledge Sources

## Propósito

La Biblioteca del Conocimiento de ODIN no pretende reconstruir el trabajo realizado por la comunidad de Elite Dangerous.

Su objetivo es integrar, normalizar y mantener actualizado el conocimiento científico necesario para asistir al comandante durante una expedición.

Siempre que sea posible, ODIN utilizará información proveniente de proyectos consolidados y reconocidos por la comunidad.

---

# Principios

## Integración antes que reinvención

ODIN reutiliza conocimiento existente cuando la licencia y la arquitectura lo permiten.

El esfuerzo de desarrollo se concentra en el razonamiento, la integración y la experiencia del comandante.

---

## Separación entre conocimiento y razonamiento

Las fuentes externas contienen datos.

ODIN interpreta esos datos.

Los oficiales generan recomendaciones.

Cada responsabilidad permanece aislada.

---

## Trazabilidad

Todo dato incorporado a la Biblioteca del Conocimiento deberá poder responder las siguientes preguntas:

* ¿Cuál es su fuente?
* ¿Qué versión fue utilizada?
* ¿Cuándo fue importado?
* ¿Cuál es su licencia?
* ¿Cuándo fue verificado por última vez?

---

# Fuentes previstas

## EDMC BioScan

Estado: Integrado mediante HUGINN y catálogo científico local.

Información aportada:

* Predicción de especies.
* Compatibilidad planetaria.
* Distancias de muestreo.
* Valores biológicos.
* Reglas de aparición.

---

## Canonn Research

Estado: Arquitectura de integración revisada en agosto de 2026.

La API histórica `api.canonn.tech` no se utilizará: el propio plugin
EDMC-Canonn retiró esas llamadas. Las fuentes mantenidas son catálogos POI,
funciones específicas, Spansh y volcados comunitarios. El volcado Codex
completo ronda los 286 MB comprimidos, por lo que ODIN no lo descargará al
iniciar ni lo incorporará al instalador.

Integración disponible:

* Catálogos POI JSON/TSV pequeños configurables desde la interfaz.
* URL HTTPS o archivo local, con límites de 5 MB y 10.000 registros.
* Caché local atómica con actualización explícita, nunca durante un salto.
* Importación manual opcional de volcados grandes.
* Sin transmisión de datos del comandante sin consentimiento separado.

Información aportada:

* Investigación científica.
* Exobiología.
* Geología.
* Descubrimientos de la comunidad.

---

## ExploData

Estado: Integrado como referencia local versionada.

Información aportada:

* Información auxiliar para predicción biológica.

---

## EDSM

Estado: Integrado de forma opcional.

Información aportada:

* Sistemas estelares.
* Información de exploración.
* Estadísticas galácticas.

---

## Spansh

Estado: Integrado como proveedor de planificación bajo demanda.

Información aportada:

* Navegación.
* Rutas.
* Información galáctica.

---

# Política de actualización

Los oficiales no implementan clientes HTTP ni almacenan secretos. Las fuentes
científicas estables se importan al formato interno mediante HUGINN. Los datos
que pierden vigencia rápidamente —rutas y mercados, por ejemplo— se consultan
bajo demanda mediante servicios aislados, con caché, límites y fallos seguros.

Esto garantiza:

* degradación controlada cuando un servicio no responde;
* funcionamiento offline para el conocimiento científico importado;
* consistencia de la Biblioteca del Conocimiento;
* trazabilidad de cada dato.

---

# Objetivo

ODIN no pretende reemplazar el conocimiento de la comunidad.

Pretende convertirse en el puente que permita utilizar ese conocimiento de forma inteligente dentro del puente de mando.

---

**Director del Proyecto**

CMDR Zorro De Jade

**Arquitecto Principal**

ODIN

---

**This is the Way.**
