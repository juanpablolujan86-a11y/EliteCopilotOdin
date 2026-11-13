"""Asistente gráfico para instalar Ollama y descargar el modelo de ODIN."""

from __future__ import annotations

import os
import logging
from datetime import datetime
import queue
import re
import subprocess
import tempfile
import threading
import time
import tkinter as tk
import urllib.request
from pathlib import Path
from tkinter import messagebox, ttk

from platform_adapters.process import hidden_process_flags


OLLAMA_URL = "https://ollama.com/download/OllamaSetup.exe"
MODEL = "gemma3:4b"
ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


def _human_bytes(value: float) -> str:
    value = max(0.0, float(value))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _parse_size(value: str) -> float:
    match = re.fullmatch(r"\s*([\d.]+)\s*([KMGT]?B)\s*", value, re.IGNORECASE)
    if not match:
        return 0.0
    multipliers = {"B": 1, "KB": 1024, "MB": 1024**2, "GB": 1024**3, "TB": 1024**4}
    return float(match.group(1)) * multipliers[match.group(2).upper()]


def _ollama_path() -> Path | None:
    candidates = (
        Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe",
        Path(os.environ.get("ProgramFiles", "")) / "Ollama" / "ollama.exe",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    try:
        result = subprocess.run(
            ["where.exe", "ollama.exe"], capture_output=True, text=True,
            creationflags=hidden_process_flags(), timeout=5,
        )
        first = result.stdout.splitlines()[0].strip() if result.returncode == 0 else ""
        return Path(first) if first else None
    except (OSError, subprocess.SubprocessError, IndexError):
        return None


class OllamaSetupWindow:
    def __init__(self) -> None:
        log_dir = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "ODIN" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        self.log_path = log_dir / ("ollama-setup-" + datetime.now().strftime("%Y%m%d-%H%M%S") + ".log")
        self.logger = logging.getLogger("odin.ollama.setup." + str(time.time_ns()))
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        handler = logging.FileHandler(self.log_path, encoding="utf-8")
        handler.setFormatter(logging.Formatter("%(asctime)s %(message)s"))
        self.logger.addHandler(handler)
        self.logger.info("ODIN 0.8.4-beta; model=%s", MODEL)
        self.root = tk.Tk()
        self.root.title("ODIN — Inteligencia local")
        self.root.geometry("820x460")
        self.root.minsize(620, 400)
        self.root.resizable(True, True)
        self.root.configure(bg="#090b0c")
        self.messages: queue.Queue[tuple] = queue.Queue()
        self.cancelled = threading.Event()
        self.process: subprocess.Popen | None = None
        self.result = 1

        tk.Label(
            self.root, text="ODIN · PREPARACIÓN DE OLLAMA", bg="#090b0c",
            fg="#ff8a00", font=("Segoe UI", 15, "bold"), anchor="w",
        ).pack(fill="x", padx=24, pady=(22, 5))
        tk.Label(
            self.root,
            text="Instalación opcional de la inteligencia conversacional local.",
            bg="#090b0c", fg="#d5b07a", font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", padx=24)
        self.stage = tk.StringVar(value="Preparando la instalación…")
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
            background="#ff8a00", bordercolor="#15191b", lightcolor="#ff8a00",
            darkcolor="#d66d00",
        )
        self.progress = ttk.Progressbar(
            self.root, style="Odin.Horizontal.TProgressbar", maximum=100,
        )
        self.progress.pack(fill="x", padx=24, pady=(0, 20), ipady=5)
        self.cancel = tk.Button(
            self.root, text="CANCELAR", command=self._cancel, bg="#24292c",
            fg="#ffb347", activebackground="#3a2a18", relief="flat",
            padx=18, pady=7, font=("Segoe UI", 9, "bold"),
        )
        self.cancel.pack(side="right", padx=24, pady=(0, 20))
        tk.Button(self.root, text="COPIAR REGISTRO", command=self._copy_log).pack(side="left", padx=24)
        tk.Label(self.root, text=str(self.log_path), wraplength=420,
                 bg="#090b0c", fg="#d5b07a").pack(side="left", fill="x", expand=True)
        self.root.protocol("WM_DELETE_WINDOW", self._cancel)

    def _copy_log(self):
        for handler in self.logger.handlers:
            handler.flush()
        self.root.clipboard_clear()
        self.root.clipboard_append(self.log_path.read_text(encoding="utf-8"))

    def run(self) -> int:
        threading.Thread(target=self._worker, name="odin-ollama-setup", daemon=True).start()
        self.root.after(80, self._poll)
        self.root.mainloop()
        return self.result

    def _cancel(self) -> None:
        self.logger.info("Cancelled by user")
        self.cancelled.set()
        if self.process is not None:
            try:
                self.process.terminate()
            except OSError:
                pass
        self.result = 2
        self.root.destroy()

    def _poll(self) -> None:
        try:
            while True:
                message = self.messages.get_nowait()
                kind, values = message[0], message[1:]
                if kind == "progress":
                    stage, detail, percent = values
                    self.stage.set(stage)
                    self.detail.set(detail)
                    self.progress.configure(mode="determinate")
                    self.progress["value"] = max(0, min(100, float(percent)))
                elif kind == "indeterminate":
                    self.stage.set(values[0])
                    self.detail.set(values[1])
                    self.progress.configure(mode="indeterminate")
                    self.progress.start(12)
                elif kind == "done":
                    self.progress.stop()
                    self.progress.configure(mode="determinate")
                    self.progress["value"] = 100
                    self.stage.set("Ollama y el modelo quedaron listos")
                    self.detail.set(f"Modelo instalado: {MODEL}")
                    self.cancel.configure(text="FINALIZAR", command=self._finish)
                    self.result = 0
                elif kind == "error":
                    self.progress.stop()
                    self.stage.set("No se pudo completar la preparación. Copiá el registro.")
                    messagebox.showerror("ODIN — Ollama", values[0] + "\n\nRegistro: " + str(self.log_path), parent=self.root)
                    self.result = 1
                    self.cancel.configure(text="CERRAR", command=self._finish)
        except queue.Empty:
            pass
        if self.root.winfo_exists():
            self.root.after(80, self._poll)

    def _finish(self) -> None:
        self.root.destroy()

    def _worker(self) -> None:
        try:
            executable = _ollama_path()
            self.logger.info("Detected executable: %s", executable)
            if executable is None:
                installer = Path(tempfile.gettempdir()) / "ODIN-OllamaSetup.exe"
                self._download_ollama(installer)
                if self.cancelled.is_set():
                    return
                self.messages.put(("indeterminate", "Instalando Ollama…", "La instalación se realiza en segundo plano."))
                completed = subprocess.run(
                    [str(installer), "/SILENT"],
                    creationflags=hidden_process_flags(),
                )
                try:
                    installer.unlink(missing_ok=True)
                except OSError:
                    pass
                executable = _ollama_path()
                if completed.returncode or executable is None:
                    raise RuntimeError("Ollama no pudo instalarse. ODIN igualmente quedó instalado.")
            try:
                version = subprocess.run([str(executable), "--version"], capture_output=True,
                    text=True, errors="replace", timeout=10, creationflags=hidden_process_flags())
                self.logger.info("Version exit=%s output=%s", version.returncode, (version.stdout + version.stderr).strip())
            except (OSError, subprocess.SubprocessError) as error:
                self.logger.info("Version check failed: %s", error)
            self._pull_model(executable)
            if not self.cancelled.is_set():
                self.messages.put(("done",))
                self.logger.info("Preparation successful")
        except Exception as error:
            self.logger.exception("Preparation failed")
            if not self.cancelled.is_set():
                self.messages.put(("error", str(error)))

    def _download_ollama(self, destination: Path) -> None:
        request = urllib.request.Request(OLLAMA_URL, headers={"User-Agent": "ODIN/0.7.3"})
        with urllib.request.urlopen(request, timeout=30) as response, destination.open("wb") as output:
            total = int(response.headers.get("Content-Length", 0) or 0)
            downloaded = 0
            started = time.monotonic()
            while not self.cancelled.is_set():
                chunk = response.read(1024 * 256)
                if not chunk:
                    break
                output.write(chunk)
                downloaded += len(chunk)
                elapsed = max(0.1, time.monotonic() - started)
                speed = downloaded / elapsed
                remaining = max(0, total - downloaded)
                percent = downloaded * 100 / total if total else 0
                self.messages.put((
                    "progress", "Descargando Ollama…",
                    f"{_human_bytes(downloaded)} de {_human_bytes(total)} · "
                    f"{_human_bytes(speed)}/s · faltan {_human_bytes(remaining)}",
                    percent,
                ))

    def _pull_model(self, executable: Path) -> None:
        self.messages.put(("indeterminate", f"Descargando el modelo {MODEL}…", "Esperando información de Ollama…"))
        self.process = subprocess.Popen(
            [str(executable), "pull", MODEL], stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, text=True, errors="replace", bufsize=1,
            creationflags=hidden_process_flags(),
        )
        assert self.process.stdout is not None
        buffer = ""
        while not self.cancelled.is_set():
            char = self.process.stdout.read(1)
            if not char:
                if self.process.poll() is not None:
                    break
                continue
            if char not in "\r\n":
                buffer += char
                continue
            line = ANSI.sub("", buffer).strip()
            buffer = ""
            if line:
                self._model_progress(line)
        code = self.process.wait()
        if buffer.strip():
            self._model_progress(ANSI.sub("", buffer).strip())
        self.logger.info("Model download exit code: %s", code)
        self.process = None
        if code and not self.cancelled.is_set():
            raise RuntimeError(f"No se pudo descargar el modelo {MODEL}. Puede reintentarlo desde ODIN.")

    def _model_progress(self, line: str) -> None:
        self.logger.info("%s", line)
        percent_match = re.search(r"(\d{1,3})\s*%", line)
        percent = float(percent_match.group(1)) if percent_match else 0
        transfer = re.search(
            r"([\d.]+\s*[KMGT]?B)\s*/\s*([\d.]+\s*[KMGT]?B)", line,
            re.IGNORECASE,
        )
        speed = re.search(r"([\d.]+\s*[KMGT]?B/s)", line, re.IGNORECASE)
        detail = line
        if transfer:
            detail = f"{transfer.group(1)} de {transfer.group(2)}"
            remaining = max(
                0.0, _parse_size(transfer.group(2)) - _parse_size(transfer.group(1))
            )
            detail += f" · faltan {_human_bytes(remaining)}"
            if speed:
                detail += f" · {speed.group(1)}"
            if percent_match:
                detail += f" · {int(percent)}% completado"
        if percent_match:
            self.messages.put(("progress", f"Descargando el modelo {MODEL}…", detail, percent))
        else:
            self.messages.put(("indeterminate", f"Preparando el modelo {MODEL}…", detail))


def run_ollama_setup() -> int:
    return OllamaSetupWindow().run()
