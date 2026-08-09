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
import re
import sys
import threading
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
        self.preferences_file = self.data_root / "preferences.json"
        self._preferences_lock = threading.Lock()
        if self.preferences_file.exists():
            try:
                preferences = json.loads(
                    self.preferences_file.read_text(encoding="utf-8")
                )
                if isinstance(preferences, dict):
                    self.data.update(preferences)
            except (OSError, json.JSONDecodeError):
                pass

    def update_preferences(self, **values) -> None:
        """Guarda preferencias públicas del usuario fuera de la instalación."""

        allowed = {
            "eddn_capture_enabled", "eddn_upload_enabled",
            "edsm_capture_enabled", "edsm_upload_enabled",
            "inara_capture_enabled", "inara_upload_enabled",
            "push_to_talk_enabled", "wake_word_enabled",
            "desktop_geometry",
        }
        updates = {key: value for key, value in values.items() if key in allowed}
        with self._preferences_lock:
            preferences = {}
            if self.preferences_file.exists():
                try:
                    loaded = json.loads(
                        self.preferences_file.read_text(encoding="utf-8")
                    )
                    if isinstance(loaded, dict):
                        preferences = loaded
                except (OSError, json.JSONDecodeError):
                    pass
            preferences.update(updates)
            self.preferences_file.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.preferences_file.with_suffix(".tmp")
            temporary.write_text(
                json.dumps(preferences, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            temporary.replace(self.preferences_file)
            self.data.update(updates)

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

    @property
    def navroute_file(self) -> Path:
        return self.journal_path / "NavRoute.json"

    @property
    def cargo_file(self) -> Path:
        return self.journal_path / "Cargo.json"

    @property
    def market_file(self) -> Path:
        return self.journal_path / "Market.json"

    @property
    def faster_whisper_model_root(self) -> Path:
        if not getattr(sys, "frozen", False):
            runtime = self.project_root / ".runtime" / "speech_models"
            if runtime.exists():
                return runtime
        return self.data_root / "speech" / "models"

    @property
    def eddn_capture_enabled(self) -> bool:
        """Captura local optativa; no implica habilitar transmisiones."""

        value = self.data.get("eddn_capture_enabled", False)
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "si", "sí"}
        return bool(value)

    @property
    def eddn_upload_enabled(self) -> bool:
        """El envío requiere una autorización separada de la captura."""

        value = self.data.get("eddn_upload_enabled", False)
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "si", "sí"}
        return bool(value)

    @property
    def eddn_test_mode(self) -> bool:
        """Durante desarrollo EDDN exige utilizar el sufijo de esquema /test."""

        value = self.data.get("eddn_test_mode", True)
        if isinstance(value, str):
            return value.strip().casefold() not in {"0", "false", "no"}
        return bool(value)

    @staticmethod
    def _enabled(value, default: bool = False) -> bool:
        if value is None:
            return default
        if isinstance(value, str):
            return value.strip().casefold() in {"1", "true", "yes", "si", "sí"}
        return bool(value)

    @property
    def edsm_capture_enabled(self) -> bool:
        return self._enabled(self.data.get("edsm_capture_enabled"))

    @property
    def edsm_upload_enabled(self) -> bool:
        return self._enabled(self.data.get("edsm_upload_enabled"))

    @property
    def inara_capture_enabled(self) -> bool:
        return self._enabled(self.data.get("inara_capture_enabled"))

    @property
    def inara_upload_enabled(self) -> bool:
        return self._enabled(self.data.get("inara_upload_enabled"))

    @property
    def heimdall_auto_replan_enabled(self) -> bool:
        """Recalcula una ruta activa sólo después de confirmar un desvío."""

        return self._enabled(self.data.get("heimdall_auto_replan_enabled"))

    @property
    def push_to_talk_enabled(self) -> bool:
        return self._enabled(self.data.get("push_to_talk_enabled"), True)

    @property
    def wake_word_enabled(self) -> bool:
        return self._enabled(self.data.get("wake_word_enabled"), True)

    @property
    def desktop_geometry(self) -> str:
        value = str(self.data.get("desktop_geometry", "")).strip()
        if re.fullmatch(r"\d+x\d+[+-]\d+[+-]\d+", value):
            return value
        return ""
