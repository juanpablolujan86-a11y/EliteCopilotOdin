"""
ODIN - Orbital Data Intelligence Nexus

edsm_lookup.py

Consulta EDSM cuando ODIN detecta un salto FSD.
"""

from services.edsm_service import EDSMService


class EDSMLookup:
    """
    Enriquece los eventos FSDJump con información externa de EDSM.
    """

    def __init__(self, edsm_service: EDSMService):
        self.edsm_service = edsm_service

    def handle(self, event: dict) -> None:
        system_name = event.get("StarSystem")

        if not system_name:
            print("EDSM                  : Nombre de sistema no disponible")
            return

        print("EDSM                  : Consultando sistema...")

        system_data = self.edsm_service.get_system(system_name)

        if system_data is None:
            print("EDSM                  : Sistema sin datos registrados")
            return

        information = system_data.get("information", {})

        print("EDSM                  : Información recibida")
        print(
            "Lealtad               : "
            f"{information.get('allegiance', 'Desconocida')}"
        )
        print(
            "Seguridad             : "
            f"{information.get('security', 'Desconocida')}"
        )
        print(
            "Economía              : "
            f"{information.get('economy', 'Desconocida')}"
        )
        print(
            "Población EDSM        : "
            f"{information.get('population', 0):,}"
        )