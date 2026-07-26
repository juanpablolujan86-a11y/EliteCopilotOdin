"""
EliteCopilot
------------

config.py

Este módulo se encarga de cargar la configuración del programa.
Toda la configuración se guarda en config.json para evitar
tener rutas o valores escritos directamente en el código.
"""

from pathlib import Path
import json


class Config:
    """
    Clase encargada de leer el archivo config.json
    """

    def __init__(self):

        # Carpeta raíz del proyecto
        self.project_root = Path(__file__).parent.parent

        # Archivo de configuración
        self.config_file = self.project_root / "config.json"

        if not self.config_file.exists():
            raise FileNotFoundError(
                f"No existe el archivo {self.config_file}"
            )

        with open(self.config_file, "r", encoding="utf-8") as file:
            self.data = json.load(file)

    @property
    def journal_path(self) -> Path:
        """
        Devuelve la carpeta donde Elite Dangerous guarda los Journals.
        """

        return Path(self.data["journal_path"])