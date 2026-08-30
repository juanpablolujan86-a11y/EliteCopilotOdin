"""Reconocimiento rápido y local de la palabra de activación."""

from __future__ import annotations

import json
import wave
from pathlib import Path


class WakeRecognitionError(RuntimeError):
    pass


class VoskWakeRecognizer:
    def __init__(self, model_path: Path) -> None:
        try:
            from vosk import Model, SetLogLevel

            SetLogLevel(-1)
            self.model = Model(str(model_path))
        except (ImportError, OSError, RuntimeError) as error:
            raise WakeRecognitionError("Vosk no está disponible.") from error

    def transcribe(self, audio: Path) -> str:
        try:
            from vosk import KaldiRecognizer

            with wave.open(str(audio), "rb") as recording:
                grammar = json.dumps(
                    [
                        "odin", "odín", "olín", "odim",
                        "odin solicita atraque", "odín solicita atraque",
                        "odin solicita aterrizaje", "odin pide atraque",
                        "odin tren de aterrizaje", "odín tren de aterrizaje",
                        "odin despliega el tren de aterrizaje",
                        "odín despliega el tren de aterrizaje",
                        "odin repliega el tren de aterrizaje",
                        "odín repliega el tren de aterrizaje",
                        "odin baja el tren de aterrizaje",
                        "odín baja el tren de aterrizaje",
                        "odin sube el tren de aterrizaje",
                        "odín sube el tren de aterrizaje",
                        "odin luz nocturna", "odin visión nocturna",
                        "odin colector de carga", "odin compuerta de carga",
                        "odin hipersalto", "odín hipersalto",
                        "odin hiper salto", "odín hiper salto",
                        "odin salto hiperespacial", "odín salto hiperespacial",
                        "odin salto al hiperespacio", "odín salto al hiperespacio",
                        "odin donde vendo mi carga minera",
                        "odín dónde vendo mi carga minera",
                        "odin busca donde vender los minerales",
                        "odín busca dónde vender los minerales",
                        "[unk]",
                    ],
                    ensure_ascii=False,
                )
                recognizer = KaldiRecognizer(
                    self.model, recording.getframerate(), grammar
                )
                recognizer.AcceptWaveform(
                    recording.readframes(recording.getnframes())
                )
                result = json.loads(recognizer.FinalResult())
        except (OSError, RuntimeError, ValueError, wave.Error) as error:
            raise WakeRecognitionError("Vosk no pudo reconocer la activación.") from error
        return str(result.get("text", "")).strip()
