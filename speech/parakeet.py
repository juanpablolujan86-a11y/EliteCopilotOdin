"""Reconocimiento local multilingüe con NVIDIA Parakeet y sherpa-onnx."""

from __future__ import annotations

import array
import threading
import wave
from pathlib import Path

from speech.whisper import TranscriptionError


class ParakeetTranscriber:
    """Carga el modelo una sola vez y mantiene el reconocimiento fuera de la red."""

    REQUIRED_FILES = (
        "encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"
    )

    def __init__(self, model_root: Path, *, threads: int = 4) -> None:
        self.model_root = Path(model_root)
        self.threads = max(1, int(threads))
        self._recognizer = None
        self._lock = threading.Lock()

    @property
    def available(self) -> bool:
        return all((self.model_root / name).is_file() for name in self.REQUIRED_FILES)

    def warm_up(self) -> bool:
        try:
            self._load_recognizer()
            return True
        except Exception:
            return False

    def transcribe(self, audio: Path) -> str:
        text, _confidence = self.transcribe_with_confidence(audio)
        return text

    def transcribe_with_confidence(self, audio: Path) -> tuple[str, float]:
        path = Path(audio)
        if not path.is_file():
            raise TranscriptionError("No se encontró el audio de la orden.")
        try:
            sample_rate, samples = self._read_pcm_wav(path)
            recognizer = self._load_recognizer()
            stream = recognizer.create_stream()
            stream.accept_waveform(sample_rate, samples)
            recognizer.decode_stream(stream)
            text = str(stream.result.text).strip()
        except TranscriptionError:
            raise
        except Exception as error:
            raise TranscriptionError(f"Parakeet no pudo transcribir la orden: {error}") from error
        if len("".join(character for character in text if character.isalnum())) < 2:
            raise TranscriptionError("No se detectó una frase clara.")
        # El resultado transducer de sherpa no expone una probabilidad global
        # comparable con Whisper. Se informa una confianza neutral y estable.
        return text, 0.75

    @staticmethod
    def _read_pcm_wav(path: Path) -> tuple[int, list[float]]:
        with wave.open(str(path), "rb") as source:
            if source.getnchannels() != 1 or source.getsampwidth() != 2:
                raise TranscriptionError("Parakeet requiere audio WAV mono PCM de 16 bits.")
            sample_rate = source.getframerate()
            pcm = array.array("h", source.readframes(source.getnframes()))
        return sample_rate, [sample / 32768.0 for sample in pcm]

    def _load_recognizer(self):
        if self._recognizer is not None:
            return self._recognizer
        if not self.available:
            raise TranscriptionError("El paquete local de Parakeet no está instalado.")
        with self._lock:
            if self._recognizer is not None:
                return self._recognizer
            try:
                import sherpa_onnx
            except ImportError as error:
                raise TranscriptionError("Falta el motor local sherpa-onnx.") from error
            self._recognizer = sherpa_onnx.OfflineRecognizer.from_transducer(
                encoder=str(self.model_root / "encoder.int8.onnx"),
                decoder=str(self.model_root / "decoder.int8.onnx"),
                joiner=str(self.model_root / "joiner.int8.onnx"),
                tokens=str(self.model_root / "tokens.txt"),
                num_threads=self.threads,
                model_type="nemo_transducer",
                provider="cpu",
            )
            return self._recognizer
