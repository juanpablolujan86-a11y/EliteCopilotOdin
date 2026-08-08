"""Cliente local de Ollama sin consumo de créditos externos."""

from __future__ import annotations

from dataclasses import dataclass

import requests


class OllamaError(RuntimeError):
    pass


@dataclass(frozen=True, slots=True)
class OllamaReply:
    text: str
    model: str
    done: bool


class OllamaClient:
    def __init__(self, model: str = "gemma3:4b", base_url: str = "http://127.0.0.1:11434") -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")

    def is_available(self) -> bool:
        try:
            response = requests.get(f"{self.base_url}/api/tags", timeout=2)
            response.raise_for_status()
            return True
        except requests.RequestException:
            return False

    def chat(self, prompt: str, *, system: str = "", context: str = "") -> OllamaReply:
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        if context:
            messages.append({"role": "system", "content": f"Contexto actual de ODIN:\n{context}"})
        messages.append({"role": "user", "content": prompt})
        try:
            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "think": False,
                    "options": {"num_ctx": 4096, "num_predict": 160},
                    "keep_alive": "10m",
                },
                timeout=180,
            )
            response.raise_for_status()
            payload = response.json()
        except (requests.RequestException, ValueError) as error:
            raise OllamaError("Ollama no está disponible o el modelo no está descargado.") from error
        text = str(payload.get("message", {}).get("content", "")).strip()
        if not text:
            raise OllamaError("Ollama respondió sin contenido.")
        return OllamaReply(text, str(payload.get("model", self.model)), bool(payload.get("done", False)))
