"""Síntesis de voz local Kokoro mediante sherpa-onnx."""

from __future__ import annotations

import io
import threading
import wave
from array import array
from pathlib import Path


class KokoroTtsError(RuntimeError):
    pass


class KokoroTtsClient:
    REQUIRED_FILES = ("model.int8.onnx", "voices.bin", "tokens.txt")

    def __init__(
        self, model_root: Path, *, threads: int = 4, language: str = "es"
    ) -> None:
        self.model_root = Path(model_root)
        self.threads = max(1, int(threads))
        self.language = language
        self._engine = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return all((self.model_root / name).is_file() for name in self.REQUIRED_FILES)

    def synthesize(self, text: str, voice: str = "0", *, speed: float = 1.0) -> bytes:
        try:
            speaker = int(voice) if str(voice).strip().isdigit() else 0
            audio = self._load_engine().generate(text, sid=speaker, speed=speed)
            samples = array("h", (
                max(-32768, min(32767, round(float(sample) * 32767)))
                for sample in audio.samples
            ))
            target = io.BytesIO()
            with wave.open(target, "wb") as wav:
                wav.setnchannels(1)
                wav.setsampwidth(2)
                wav.setframerate(int(audio.sample_rate))
                wav.writeframes(samples.tobytes())
            return target.getvalue()
        except KokoroTtsError:
            raise
        except Exception as error:
            raise KokoroTtsError(f"Kokoro no pudo generar la voz: {error}") from error

    def _load_engine(self):
        if self._engine is not None:
            return self._engine
        if not self.available:
            raise KokoroTtsError("El paquete local de Kokoro no está instalado.")
        with self._lock:
            if self._engine is not None:
                return self._engine
            try:
                import sherpa_onnx
            except ImportError as error:
                raise KokoroTtsError("Falta el motor local sherpa-onnx.") from error
            kokoro = sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=str(self.model_root / "model.int8.onnx"),
                voices=str(self.model_root / "voices.bin"),
                tokens=str(self.model_root / "tokens.txt"),
                data_dir=str(self.model_root / "espeak-ng-data"),
                lang=self.language,
            )
            model = sherpa_onnx.OfflineTtsModelConfig(
                kokoro=kokoro, num_threads=self.threads, provider="cpu", debug=False
            )
            config = sherpa_onnx.OfflineTtsConfig(model=model)
            if not config.validate():
                raise KokoroTtsError("La configuración local de Kokoro no es válida.")
            self._engine = sherpa_onnx.OfflineTts(config)
            return self._engine
