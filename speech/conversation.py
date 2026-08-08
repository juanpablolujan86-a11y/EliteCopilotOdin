"""Orquestación de una conversación hablada con ODIN."""

from __future__ import annotations

from core.config import Config
from intelligence.assistant import OdinLocalAssistant
from speech.recorder import MicrophoneRecorder
from speech.whisper import WhisperTranscriber
from voice.service import OfficerVoiceService


class VoiceConversation:
    def __init__(
        self,
        config: Config | None = None,
        recorder: MicrophoneRecorder | None = None,
        transcriber: WhisperTranscriber | None = None,
        assistant: OdinLocalAssistant | None = None,
        voice: OfficerVoiceService | None = None,
    ) -> None:
        self.config = config or Config()
        self.recorder = recorder or MicrophoneRecorder()
        self.transcriber = transcriber or WhisperTranscriber()
        self.assistant = assistant or OdinLocalAssistant()
        self.voice = voice or OfficerVoiceService(self.config)

    def listen_once(self, seconds: float = 7.0, context: str = "") -> tuple[str, str]:
        audio = self.config.data_root / "speech" / "last_command.wav"
        self.recorder.record_for(audio, seconds)
        question = self.transcriber.transcribe(audio)
        answer = self.assistant.ask(question, context=context).text
        self.voice.speak("ODIN", answer)
        return question, answer

    def respond(self, question: str, context: str = "") -> str:
        answer = self.answer(question, context)
        self.voice.speak("ODIN", answer)
        return answer

    def answer(self, question: str, context: str = "") -> str:
        return self.assistant.ask(question, context=context).text
