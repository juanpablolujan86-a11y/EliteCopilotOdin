from knowledge.importer.import_manager import ImportManager

manager = ImportManager()

print("=" * 50)
print("HUGINN - Knowledge Acquisition Test")
print("=" * 50)

print("\nFuentes registradas:")

for source in manager.available_sources():
    ok, errors = manager.validate_source(source)

    status = "OK" if ok else "ERROR"

    print(f"  {source:10} {status}")

    if errors:
        for error in errors:
            print("     -", error)

print("\nProvider DSN")

provider = manager.get_provider("dsn")

print("Nombre :", provider.source_name)
print("ID     :", provider.source_id)

print("\nHUGINN inicializado correctamente.")