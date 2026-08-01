# Operación Yggdrasil

## Objetivo

Ampliar el conocimiento de MÍMIR desde el género Stratum hasta todos
los catálogos biológicos incluidos en la copia versionada de EDMC
BioScan.

## Resultado

- Catálogos procesados: 19
- Géneros normalizados: 19
- Especies importadas: 116
- Reglas importadas: 254
- Especies sin reglas: 1 (`Stratum Aranaemus`)
- IDs de especies duplicados: 0
- IDs de reglas duplicados: 0
- Reglas con referencias rotas: 0
- Reglas vacías: 0
- Reglas evaluables por el motor actual: 208
- Reglas que requieren contexto avanzado: 46
- Especies con al menos una regla evaluable: 86

BioScan declara explícitamente `Stratum Aranaemus` sin reglas. ODIN la
conserva como especie conocida, pero no intenta predecirla.

## Seguridad de las predicciones

Las condiciones originales de BioScan se preservan en los archivos
generados. Cuando una regla contiene una condición que MÍMIR todavía
no puede evaluar con los datos disponibles, el motor la rechaza de
forma conservadora. Esto evita recomendaciones basadas en condiciones
ignoradas.

El adaptador ya normaliza atmósfera, tipo planetario, gravedad,
temperatura, presión superficial y volcanismo. Las condiciones
avanzadas pendientes incluyen contexto estelar,
nebulosas, cuerpos cercanos, zonas Guardian y período orbital. Podrán
habilitarse progresivamente cuando el contexto planetario de ODIN las
proporcione.

## Regeneración

```powershell
python import_biology_knowledge.py
python -m unittest discover -s tests -v
```

La escritura de los documentos es atómica y la suite comprueba que los
archivos publicados coincidan exactamente con una importación fresca.
