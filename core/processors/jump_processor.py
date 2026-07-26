class JumpProcessor:
    """
    Procesa los saltos FSD detectados por ODIN.
    """

    def handle(self, event):

        system = event.get("StarSystem", "Desconocido")
        arrival_star = event.get("Body", "Desconocida")
        jump_distance = event.get("JumpDist", 0)
        fuel_used = event.get("FuelUsed", 0)
        fuel_level = event.get("FuelLevel", 0)
        population = event.get("Population", 0)

        print("\n" + "=" * 50)
        print("ODIN")
        print("=" * 50)

        print("Salto FSD completado")
        print(f"Sistema              : {system}")
        print(f"Estrella de llegada  : {arrival_star}")
        print(f"Distancia recorrida  : {jump_distance:.2f} Ly")
        print(f"Combustible utilizado: {fuel_used:.3f} t")
        print(f"Combustible restante : {fuel_level:.2f} t")

        if population == 0:
            print("Estado               : Sistema no habitado")
        else:
            print(f"Población            : {population:,}")

        print("=" * 50)