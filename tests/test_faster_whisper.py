from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock
import math
import tempfile
import unittest

from speech.faster_whisper import FasterWhisperTranscriber


class FasterWhisperTranscriberTests(unittest.TestCase):
    def test_gpu_transcription_returns_text_and_segment_confidence(self):
        with tempfile.TemporaryDirectory() as directory:
            audio=Path(directory)/"order.wav"; audio.write_bytes(b"audio")
            model=Mock()
            model.transcribe.return_value=(
                iter([SimpleNamespace(text=" quiero comerciar",avg_logprob=math.log(0.8))]),
                SimpleNamespace(language="es"),
            )
            transcriber=FasterWhisperTranscriber()
            transcriber._model=model

            text,confidence=transcriber.transcribe_with_confidence(audio)

            self.assertEqual(text,"quiero comerciar")
            self.assertAlmostEqual(confidence,0.8)
            self.assertEqual(model.transcribe.call_args.kwargs["language"],"es")

    def test_gpu_failure_uses_whisper_cpp_fallback(self):
        fallback=Mock()
        fallback.transcribe_with_confidence.return_value=("opción dos",0.7)
        transcriber=FasterWhisperTranscriber(fallback=fallback)
        transcriber._gpu_transcribe=Mock(side_effect=RuntimeError("CUDA"))

        result=transcriber.transcribe_with_confidence(Path("missing.wav"))

        self.assertEqual(result,("opción dos",0.7))
        fallback.transcribe_with_confidence.assert_called_once()


if __name__ == "__main__":
    unittest.main()
