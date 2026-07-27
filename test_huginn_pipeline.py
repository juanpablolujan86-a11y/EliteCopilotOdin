from knowledge.importer.import_manager import ImportManager
from knowledge.importer.providers.dsn_species_importer import (
    DSNSpeciesImporter,
)
from knowledge.importer.writer import KnowledgeWriter

print("=" * 60)
print("HUGINN - Pipeline Test")
print("=" * 60)

manager = ImportManager()

# Inspeccionar documento
report = manager.inspect_with_provider(
    "dsn",
    "knowledge/imported/raw/sample_dsn.json",
)

print("\nInforme")

print(f"Proveedor : {report['provider']}")
print(f"Registros : {report['record_count']}")
print(f"Válido    : {report['valid']}")

# Convertir especies
document = report["document"]

importer = DSNSpeciesImporter()

species = importer.convert_document(document)

print("\nEspecies convertidas")

for item in species:
    print(
        f"- {item['id']}"
    )

# Escribir biblioteca

writer = KnowledgeWriter()

writer.write_species(
    "knowledge/biology/species.json",
    species,
)

print("\nBiblioteca generada correctamente.")