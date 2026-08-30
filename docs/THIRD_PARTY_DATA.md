# Datos externos utilizados en tiempo de ejecución

La licencia GPL-3.0-only de ODIN cubre únicamente el código propio del proyecto.
Los catálogos, herramientas y datos externos conservan sus licencias originales.
Incluir una referencia o permitir que ODIN lea un archivo local no cambia su
titularidad ni lo relicencia como parte de ODIN.

## Constantes FSD de EDMarketConnector

ODIN no redistribuye la base de módulos de Coriolis. HEIMDALL lee, cuando está
disponible, el archivo local `modules.json` instalado por EDMarketConnector y
utiliza exclusivamente las propiedades físicas necesarias para Galaxy Plotter.

- Fuente del generador: https://github.com/EDCD/EDMarketConnector/blob/main/coriolis-update-files.py
- Fuente original de datos: https://github.com/EDCD/coriolis-data
- Licencia y términos: https://github.com/EDCD/coriolis-data/blob/master/LICENSE.md

Si EDMarketConnector no está instalado, el archivo está dañado o el módulo no
figura en su versión local, ODIN no estima ni sustituye las constantes: mantiene
deshabilitado el cálculo exacto hasta disponer de una fuente válida.
