from knowledge.engine import KnowledgeEngine


engine = KnowledgeEngine()
engine.load()

print("Biblioteca cargada:", engine.is_loaded())
print("Dominios:", engine.get_domains())

for domain in engine.get_domains():
    catalog = engine.get_catalog(domain)

    print()
    print("=" * 40)
    print("Dominio:", domain)
    print("Recursos:", engine.count_resources(domain))

    if catalog is None:
        print("Catálogo no disponible")
        continue

    print("Nombre:", catalog.name)
    print("Versión:", catalog.version)
    print("Estado:", catalog.status)
    print("Fuentes:", len(catalog.sources))