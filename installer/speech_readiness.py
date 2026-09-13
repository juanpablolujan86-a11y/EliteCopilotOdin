"""Comprobación de modelos sin descargas, micrófono ni credenciales."""

from speech.parakeet import ParakeetTranscriber
from speech.whisper import WhisperTranscriber


def has_recognition_models(config):
    if config.speech_recognition_provider != "whisper":
        model = ParakeetTranscriber(config.parakeet_model_root)
        if model.available and all((model.model_root / name).stat().st_size > 0
                                   for name in model.REQUIRED_FILES):
            return True
    root = config.faster_whisper_model_root
    snapshots = root / "models--Systran--faster-whisper-small" / "snapshots"
    if snapshots.exists():
        for folder in snapshots.iterdir():
            if all((folder / name).is_file() and (folder / name).stat().st_size > 0
                   for name in ("model.bin", "config.json", "tokenizer.json")):
                return True
    whisper = WhisperTranscriber(config.data_root / "speech")
    return whisper.executable.is_file() and whisper.model.is_file() and whisper.model.stat().st_size > 0


def offer_speech_setup(config):
    if has_recognition_models(config):
        return
    import tkinter as tk
    from tkinter import messagebox
    from installer.local_speech_gui import run_local_speech_setup
    root = tk.Tk()
    root.withdraw()
    try:
        install = messagebox.askyesno(
            "ODIN — Reconocimiento de voz pendiente",
            "Faltan los modelos para reconocer su voz. ¿Desea instalarlos ahora?\n\n"
            "Requiere Internet y aproximadamente 1 GB. Ollama no sustituye estos modelos.\n"
            "Si elige No, puede usar la interfaz y repararlo después desde el menú Inicio: "
            "ODIN → Reparar reconocimiento de voz.", parent=root)
    finally:
        root.destroy()
    if install:
        run_local_speech_setup()
