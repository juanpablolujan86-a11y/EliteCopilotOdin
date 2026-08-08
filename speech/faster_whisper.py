"""Transcripción GPU de alta precisión con respaldo local whisper.cpp."""

from __future__ import annotations

import math
import os
import sys
import threading
from pathlib import Path

from core.config import Config
from speech.whisper import TranscriptionError, WhisperTranscriber


PROMPT = (
    "ODIN, MÍMIR, HEIMDALL, FREYJA, Elite Dangerous, quiero comerciar, "
    "vamos a comerciar, opción uno, opción dos, opción tres, opción cuatro, "
    "comercio Powerplay, ruta de neutrones, exobiología, Stratum Tectonicas"
)


class FasterWhisperTranscriber:
    """Mantiene large-v3-turbo residente en GPU entre órdenes."""

    def __init__(
        self,
        config: Config | None = None,
        fallback: WhisperTranscriber | None = None,
        *,
        model_name: str = "large-v3-turbo",
    ) -> None:
        self.config = config or Config()
        self.fallback = fallback or WhisperTranscriber(model_preference="small")
        self.model_name = model_name
        self._model = None
        self._model_lock = threading.Lock()
        self._dll_handles: list[object] = []

    def warm_up(self) -> bool:
        try:
            self._load_model()
            return True
        except Exception:
            return False

    def transcribe(self, audio: Path) -> str:
        try:
            text, _confidence = self._gpu_transcribe(audio)
            return text
        except Exception:
            return self.fallback.transcribe(audio)

    def transcribe_with_confidence(self, audio: Path) -> tuple[str, float]:
        try:
            return self._gpu_transcribe(audio)
        except Exception:
            return self.fallback.transcribe_with_confidence(audio)

    def _gpu_transcribe(self, audio: Path) -> tuple[str, float]:
        if not audio.exists():
            raise TranscriptionError("No se encontró el audio de la orden.")
        model = self._load_model()
        segments, _info = model.transcribe(
            str(audio),
            language="es",
            beam_size=5,
            vad_filter=True,
            condition_on_previous_text=False,
            initial_prompt=PROMPT,
        )
        materialized = tuple(segments)
        text = "".join(segment.text for segment in materialized).strip()
        meaningful = "".join(character for character in text if character.isalnum())
        if len(meaningful) < 3:
            raise TranscriptionError("No se detectó una frase clara.")
        probabilities = [
            max(0.0, min(1.0, math.exp(float(segment.avg_logprob))))
            for segment in materialized
        ]
        confidence = sum(probabilities) / len(probabilities) if probabilities else 0.0
        return text, confidence

    def _load_model(self):
        if self._model is not None:
            return self._model
        with self._model_lock:
            if self._model is not None:
                return self._model
            self._configure_cuda_dlls()
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_name,
                device="cuda",
                compute_type="int8_float16",
                download_root=str(self.config.faster_whisper_model_root),
                local_files_only=True,
            )
            return self._model

    def _configure_cuda_dlls(self) -> None:
        site_packages = Path(sys.prefix) / "Lib" / "site-packages" / "nvidia"
        directories = tuple(
            site_packages / package / "bin"
            for package in ("cublas", "cudnn", "cuda_nvrtc")
            if (site_packages / package / "bin").exists()
        )
        if directories:
            os.environ["PATH"] = os.pathsep.join(
                [*(str(path) for path in directories), os.environ.get("PATH", "")]
            )
        if hasattr(os, "add_dll_directory"):
            self._dll_handles.extend(
                os.add_dll_directory(str(path)) for path in directories
            )
