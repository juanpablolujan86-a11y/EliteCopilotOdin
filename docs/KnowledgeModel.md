# Knowledge Model v1.0

## Biological Species

Toda especie conocida por ODIN utilizará el siguiente modelo.

```json
{
    "id": "",

    "genus": "",

    "species": "",

    "variant": "",

    "rarity": "",

    "estimated_value": 0,

    "sampling_distance": 0,

    "planet_classes": [],

    "atmospheres": [],

    "gravity": {

        "min": null,

        "max": null

    },

    "temperature": {

        "min": null,

        "max": null

    },

    "volcanism": [],

    "star_types": [],

    "first_discovered": null,

    "sources": [],

    "confidence": 1.0
}
```

## Filosofía

Una especie no representa solamente un nombre.

Representa todo el conocimiento científico conocido por ODIN sobre ella.

HUGINN actualizará este conocimiento.

MÍMIR lo utilizará para razonar.

Las observaciones del comandante podrán modificar únicamente el nivel de confianza, nunca la fuente original.