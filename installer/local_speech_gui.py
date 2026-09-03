"""Descarga gráfica de los modelos locales de escucha y voz de ODIN."""

from __future__ import annotations

import os
import queue
import shutil
import tarfile
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from tkinter import messagebox, ttk


@dataclass(frozen=True)
class ModelPackage:
    title: str
    url: str
    directory: str
    relative_parent: Path
    required: tuple[str, ...]


PACKAGES = (
    ModelPackage(
        "Parakeet · reconocimiento de voz",
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models/"
        "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8.tar.bz2",
        "sherpa-onnx-nemo-parakeet-tdt-0.6b-v3-int8",
        Path("speech") / "models",
        ("encoder.int8.onnx", "decoder.int8.onnx", "joiner.int8.onnx", "tokens.txt"),
    ),
    ModelPackage(
        "Kokoro · voces locales",
        "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/"
        "kokoro-int8-multi-lang-v1_0.tar.bz2",
        "kokoro-int8-multi-lang-v1_0",
        Path("voice") / "models",
        ("model.int8.onnx", "voices.bin", "tokens.txt", "espeak-ng-data"),
    ),
)


def _human_bytes(value: float) -> str:
    value = max(0.0, float(value))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


class LocalSpeechSetupWindow:
    def __init__(self, data_root: Path | None = None) -> None:
        local = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        self.data_root = data_root or local / "ODIN"
        self.messages: queue.Queue[tuple] = queue.Queue()
        self.cancelled = threading.Event()
        self.result = 1
        self.root = tk.Tk()
        self.root.title("ODIN — Voz local")
        self.root.geometry("650x340")
        self.root.resizable(False, False)
        self.root.configure(bg="#090b0c")
        tk.Label(
            self.root, text="ODIN · SISTEMA DE VOZ LOCAL", bg="#090b0c",
            fg="#ff8a00", font=("Segoe UI", 15, "bold"), anchor="w",
        ).pack(fill="x", padx=24, pady=(22, 5))
        tk.Label(
            self.root,
            text="Parakeet escucha al comandante y Kokoro da voz a los oficiales.",
            bg="#090b0c", fg="#d5b07a", font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=24)
        self.stage = tk.StringVar(value="Preparando los modelos…")
        self.detail = tk.StringVar(value="")
        tk.Label(
            self.root, textvariable=self.stage, bg="#090b0c", fg="#ffffff",
            font=("Segoe UI", 11, "bold"), anchor="w",
        ).pack(fill="x", padx=24, pady=(28, 5))
        tk.Label(
            self.root, textvariable=self.detail, bg="#090b0c", fg="#d5b07a",
            font=("Cascadia Mono", 9), anchor="w",
        ).pack(fill="x", padx=24, pady=(0, 8))
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Odin.Horizontal.TProgressbar", troughcolor="#15191b",
            background="#ff8a00", bordercolor="#15191b",
        )
        self.progress = ttk.Progressbar(
            self.root, style="Odin.Horizontal.TProgressbar", maximum=100
        )
        self.progress.pack(fill="x", padx=24, pady=(0, 20), ipady=5)
        self.button = tk.Button(
            self.root, text="CANCELAR", command=self._cancel, bg="#24292c",
            fg="#ffb347", relief="flat", padx=18, pady=7,
            font=("Segoe UI", 9, "bold"),
        )
        self.button.pack(side="right", padx=24, pady=(0, 20))
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)

    def run(self) -> int:
        threading.Thread(target=self._worker, name="odin-local-speech", daemon=True).start()
        self.root.after(80, self._poll)
        self.root.mainloop()
        return self.result

    def _cancel(self) -> None:
        self.cancelled.set()
        self.result = 2
        self.root.destroy()

    def _poll(self) -> None:
        try:
            while True:
                kind, *values = self.messages.get_nowait()
                if kind == "progress":
                    self.stage.set(values[0]); self.detail.set(values[1])
                    self.progress["value"] = values[2]
                elif kind == "done":
                    self.stage.set("Voz local instalada correctamente")
                    self.detail.set("Parakeet y Kokoro están disponibles para ODIN.")
                    self.progress["value"] = 100
                    self.button.configure(text="FINALIZAR", command=self.root.destroy)
                    self.result = 0
                elif kind == "error":
                    messagebox.showerror("ODIN — Voz local", values[0], parent=self.root)
                    self.root.destroy()
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(80, self._poll)

    def _worker(self) -> None:
        try:
            for index, package in enumerate(PACKAGES):
                if self.cancelled.is_set():
                    return
                target = self.data_root / package.relative_parent / package.directory
                if all((target / item).exists() for item in package.required):
                    continue
                self._install(package, index)
            if not self.cancelled.is_set():
                self.messages.put(("done",))
        except Exception as error:
            if not self.cancelled.is_set():
                self.messages.put(("error", str(error)))

    def _install(self, package: ModelPackage, package_index: int) -> None:
        with tempfile.TemporaryDirectory(prefix="odin-model-") as temporary:
            staging = Path(temporary)
            archive = staging / "model.tar.bz2"
            request = urllib.request.Request(package.url, headers={"User-Agent": "ODIN/0.9"})
            with urllib.request.urlopen(request, timeout=60) as response, archive.open("wb") as output:
                total = int(response.headers.get("Content-Length", 0) or 0)
                downloaded = 0
                started = time.monotonic()
                while not self.cancelled.is_set():
                    chunk = response.read(1024 * 512)
                    if not chunk:
                        break
                    output.write(chunk); downloaded += len(chunk)
                    speed = downloaded / max(0.1, time.monotonic() - started)
                    remaining = max(0, total - downloaded)
                    local_percent = downloaded * 100 / total if total else 0
                    overall = (package_index * 50) + local_percent / len(PACKAGES)
                    self.messages.put((
                        "progress", f"Descargando {package.title}…",
                        f"{_human_bytes(downloaded)} de {_human_bytes(total)} · "
                        f"{_human_bytes(speed)}/s · faltan {_human_bytes(remaining)}",
                        overall,
                    ))
            if self.cancelled.is_set():
                return
            self.messages.put(("progress", f"Instalando {package.title}…", "Verificando archivos…", package_index * 50 + 48))
            extract_root = staging / "extracted"
            extract_root.mkdir()
            with tarfile.open(archive, "r:bz2") as bundle:
                bundle.extractall(extract_root, filter="data")
            source = extract_root / package.directory
            if not all((source / item).exists() for item in package.required):
                raise RuntimeError(f"El paquete descargado de {package.title} está incompleto.")
            parent = self.data_root / package.relative_parent
            parent.mkdir(parents=True, exist_ok=True)
            target = parent / package.directory
            if target.exists():
                raise RuntimeError(
                    f"Existe una instalación incompleta en {target}. Elimínela y reintente."
                )
            shutil.move(str(source), str(target))


def run_local_speech_setup() -> int:
    return LocalSpeechSetupWindow().run()
