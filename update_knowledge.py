"""
update_knowledge.py

Herramienta principal para actualizar la
Biblioteca del Conocimiento de ODIN.

HUGINN será invocado desde este punto.
"""

from knowledge.importer.provider_registry import (
    ProviderRegistry,
)


def main():

    print("=" * 60)
    print("HUGINN - Knowledge Acquisition")
    print("=" * 60)

    registry = ProviderRegistry()

    print()

    print("Proveedores registrados:\n")

    for provider in registry.all():

        print(
            f"  • {provider.source_name} "
            f"({provider.source_id})"
        )

    print()

    print(
        f"Total: {len(registry.available())} proveedor(es)"
    )


if __name__ == "__main__":
    main()