"""
EliteCopilot
------------

config.py

Este módulo se encarga de cargar la configuración del programa.
Toda la configuración se guarda en config.json para evitar
tener rutas o valores escritos directamente en el código.
"""

import json
import os
import sys
from pathlib import Path


class Config:
    """
    Clase encargada de leer el archivo config.json
    """

    def __init__(self):
        self.project_root = Path(
            getattr(sys, "_MEIPASS", Path(__file__).parent.parent)
        )
        local_app_data = Path(
            os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local")
        )
        self.data_root = local_app_data / "ODIN"
        self.data_root.mkdir(parents=True, exist_ok=True)

        # Durante el desarrollo se respeta config.json. La distribución no
        # lo incluye: detecta automáticamente el Journal de cada usuario.
        self.config_file = self.project_root / "config.json"
        self.data = {}
        if self.config_file.exists() and not getattr(sys, "frozen", False):
            with self.config_file.open("r", encoding="utf-8") as file:
                self.data = json.load(file)

    @property
    def journal_path(self) -> Path:
        """
        Devuelve la carpeta donde Elite Dangerous guarda los Journals.
        """

        configured = self.data.get("journal_path")
        if configured:
            return Path(configured)

        return (
            Path.home()
            / "Saved Games"
            / "Frontier Developments"
            / "Elite Dangerous"
        )

    @property
    def status_file(self) -> Path:
        return self.journal_path / "Status.json"

    @property
    def bindings_path(self) -> Path:
        configured = self.data.get("bindings_path")
        if configured:
            return Path(configured)
        return (
            Path.home() / "AppData" / "Local" / "Frontier Developments"
            / "Elite Dangerous" / "Options" / "Bindings"
        )
