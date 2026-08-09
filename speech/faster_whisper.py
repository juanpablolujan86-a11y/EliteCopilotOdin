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
    "comercio Powerplay, ruta de neutrones, exobiología, Stratum Tectonicas, "
    "estado de la ruta comercial, qué tengo que comprar, qué tengo que vender, "
    "cancela la ruta comercial, recalculá la ruta comercial, "
    "repetí la instrucción comercial, cuánto beneficio tiene la ruta"
    ", cuánto beneficio llevo comerciando, cuánto invertí en comercio"
)


class FasterWhisperTranscriber:
    """Mantiene un modelo compacto residente sin competir con el juego."""

    def __init__(
        self,
        config: Config | None = None,
        fallback: WhisperTranscriber | None = None,
        *,
        model_name: str = "small",
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
            # Las órdenes ya llegan recortadas por MicrophoneRecorder. Una
            # segunda VAD descartaba voces de micrófono con volumen bajo.
            # Greedy decoding reduce de forma importante la latencia para
            # frases cortas sin cargar cinco hipótesis completas.
            beam_size=1,
            vad_filter=False,
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
                # Elite Dangerous ocupa casi toda la VRAM de una RTX 4060 de
                # 8 GB. Small/int8 en CPU deja la GPU disponible para el juego
                # y evita que una orden quede esperando indefinidamente.
                device="cpu",
                compute_type="int8",
                cpu_threads=4,
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
