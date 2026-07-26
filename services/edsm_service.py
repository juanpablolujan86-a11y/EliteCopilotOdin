"""
ODIN - Orbital Data Intelligence Nexus

edsm_service.py

Consulta información pública sobre sistemas estelares en EDSM.
"""

from typing import Any

import requests


class EDSMService:
    """
    Cliente HTTP para la API pública de EDSM.
    """

    BASE_URL = "https://www.edsm.net/api-v1/system"

    def __init__(self) -> None:
        self.session = requests.Session()

        self.session.headers.update(
            {
                "User-Agent": (
                    "ODIN-EliteCopilot/0.2 "
                    "(Elite Dangerous companion application)"
                ),
                "Accept": "application/json",
            }
        )

    def get_system(self, system_name: str) -> dict[str, Any] | None:
        """
        Obtiene información general y coordenadas de un sistema.
        """

        try:
            response = self.session.get(
                self.BASE_URL,
                params={
                    "systemName": system_name,
                    "showInformation": 1,
                    "showCoordinates": 1,
                },
                timeout=10,
            )

            response.raise_for_status()

            data = response.json()

            if not data or "name" not in data:
                print(f"EDSM: sistema no encontrado: {system_name}")
                return None

            return data

        except requests.Timeout:
            print("EDSM Error: la consulta superó el tiempo de espera.")
            return None

        except requests.HTTPError as error:
            status_code = error.response.status_code
            print(f"EDSM Error HTTP {status_code}: {error}")
            return None

        except requests.RequestException as error:
            print(f"EDSM Error de conexión: {error}")
            return None

        except ValueError:
            print("EDSM Error: la respuesta recibida no contiene JSON válido.")
            return None