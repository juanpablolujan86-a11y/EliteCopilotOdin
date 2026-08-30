"""Cliente de OpenAI para la capa conversacional de ODIN."""

from __future__ import annotations

from dataclasses import dataclass

import requests

from voice.credentials import WindowsCredentialStore


OPENAI_CREDENTIAL_TARGET = "ODIN/OpenAIApiKey"


class OpenAIError(RuntimeError):
    pass


class OpenAICredentialStore(WindowsCredentialStore):
    def __init__(self) -> None:
        super().__init__(OPENAI_CREDENTIAL_TARGET)

    def set(self, secret: str) -> None:
        if not secret.strip():
            raise ValueError("La clave de OpenAI no puede estar vacía.")
        super().set(secret)


@dataclass(frozen=True, slots=True)
class OpenAIReply:
    text: str
    model: str
    done: bool = True


class OpenAIClient:
    def __init__(self, model: str = "gpt-5-mini", timeout: float = 45.0) -> None:
        self.model = model
        self.timeout = timeout
        self.credentials = OpenAICredentialStore()

    def is_available(self) -> bool:
        return self.credentials.exists()

    def chat(self, prompt: str, *, system: str = "", context: str = "") -> OpenAIReply:
        api_key = self.credentials.get()
        if not api_key:
            raise OpenAIError("La API de OpenAI no está configurada.")
        instructions = system
        if context:
            instructions = f"{instructions}\n\nContexto actual de ODIN:\n{context}".strip()
        try:
            response = requests.post(
                "https://api.openai.com/v1/responses",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.model,
                    "instructions": instructions,
                    "input": prompt,
                    "max_output_tokens": 220,
                    "store": False,
                },
                timeout=self.timeout,
            )
            if response.status_code in {401, 403}:
                raise OpenAIError("La clave de OpenAI fue rechazada.")
            if response.status_code == 429:
                try:
                    error_code = str(
                        response.json().get("error", {}).get("code", "")
                    ).casefold()
                except (ValueError, AttributeError):
                    error_code = ""
                if error_code == "insufficient_quota":
                    raise OpenAIError(
                        "La cuenta API no tiene saldo o facturación activa."
                    )
                raise OpenAIError(
                    "OpenAI alcanzó temporalmente el límite de solicitudes."
                )
            response.raise_for_status()
            payload = response.json()
        except OpenAIError:
            raise
        except (requests.RequestException, ValueError) as error:
            raise OpenAIError("OpenAI no está disponible en este momento.") from error
        text = str(payload.get("output_text", "")).strip()
        if not text:
            for item in payload.get("output", []):
                for content in item.get("content", []):
                    if content.get("type") == "output_text":
                        text += str(content.get("text", ""))
            text = text.strip()
        if not text:
            raise OpenAIError("OpenAI respondió sin contenido.")
        return OpenAIReply(text=text, model=str(payload.get("model", self.model)))

    def test_connection(self) -> str:
        reply = self.chat(
            "Respondé únicamente: conexión correcta",
            system="Respondé en español y seguí exactamente la instrucción.",
        )
        return reply.model
