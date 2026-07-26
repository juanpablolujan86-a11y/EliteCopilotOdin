class JumpProcessor:
    """
    Procesa todos los eventos FSDJump.
    """

    def handle(self, event):

        print("\n" + "=" * 50)
        print("ODIN")
        print("=" * 50)

        print(f"Comandante : {event.get('Commander', 'Desconocido')}")
        print(f"Sistema    : {event.get('StarSystem', 'Desconocido')}")
        print(f"Estrella   : {event.get('StarClass', 'Desconocida')}")
        print(f"Fecha      : {event.get('timestamp')}")

        print("=" * 50)