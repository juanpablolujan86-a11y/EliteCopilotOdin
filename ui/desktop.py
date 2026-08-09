"""Interfaz gráfica de escritorio para el Centro de Mando de ODIN."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import ttk

from core.diagnostics import log_fatal_error
from heimdall.clipboard import write_text


ELITE = {
    "background": "#090b0c",
    "surface": "#111416",
    "surface_alt": "#171b1e",
    "border": "#5b3515",
    "orange": "#ff8a00",
    "orange_soft": "#c96400",
    "amber": "#ffc04a",
    "text": "#f4d6b0",
    "muted": "#a5805b",
    "green": "#63d483",
    "red": "#ff6655",
}


class GuiLogStream:
    """Stream no bloqueante: cualquier hilo escribe; Tkinter sólo consume."""

    def __init__(self, messages: queue.Queue[str], fallback=None) -> None:
        self.messages = messages
        self.fallback = fallback
        self.encoding = "utf-8"

    def write(self, text: str) -> int:
        if text:
            self.messages.put(str(text))
            if self.fallback is not None:
                self.fallback.write(text)
        return len(text)

    def flush(self) -> None:
        if self.fallback is not None:
            self.fallback.flush()

    def isatty(self) -> bool:
        return False


class OdinDesktopApp:
    def __init__(self, odin) -> None:
        self.odin = odin
        self.root = tk.Tk()
        self.root.title("ODIN — Centro de Mando")
        self.root.geometry("1180x720")
        self.root.minsize(900, 580)
        self.root.configure(bg=ELITE["background"])
        self.log_messages: queue.Queue[str] = queue.Queue()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.stream = GuiLogStream(self.log_messages)
        self.engine_thread: threading.Thread | None = None
        self._closing = False
        self.values: dict[str, tk.StringVar] = {}
        self._build_styles()
        self._build_window()
        self.root.protocol("WM_DELETE_WINDOW", self.close)

    def run(self) -> None:
        sys.stdout = self.stream
        sys.stderr = self.stream
        self.engine_thread = threading.Thread(
            target=self._run_engine,
            name="odin-engine",
            daemon=True,
        )
        self.engine_thread.start()
        self.root.after(80, self._drain_log)
        self.root.after(250, self._refresh_state)
        try:
            self.root.mainloop()
        finally:
            sys.stdout = self.original_stdout
            sys.stderr = self.original_stderr

    def _run_engine(self) -> None:
        try:
            self.odin.start()
        except Exception as error:
            log_fatal_error()
            print(f"ODIN encontró un error inesperado: {error}")

    def close(self) -> None:
        if self._closing:
            return
        self._closing = True
        self.odin.request_stop()
        self.root.after(150, self._finish_close)

    def _finish_close(self) -> None:
        if self.engine_thread is not None and self.engine_thread.is_alive():
            self.engine_thread.join(timeout=0.05)
            self.root.after(100, self._finish_close)
            return
        self.root.destroy()

    def _build_styles(self) -> None:
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(
            "Odin.TNotebook", background=ELITE["surface"], borderwidth=0
        )
        style.configure(
            "Odin.TNotebook.Tab",
            background=ELITE["surface_alt"],
            foreground=ELITE["muted"],
            padding=(12, 7),
            borderwidth=0,
        )
        style.map(
            "Odin.TNotebook.Tab",
            background=[("selected", ELITE["surface"])],
            foreground=[("selected", ELITE["orange"])],
        )

    def _build_window(self) -> None:
        header = tk.Frame(self.root, bg=ELITE["surface"], height=54)
        header.pack(fill="x")
        header.pack_propagate(False)
        tk.Label(
            header, text="◈  ODIN", bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 16, "bold"),
        ).pack(side="left", padx=(16, 7))
        tk.Label(
            header, text="CENTRO DE MANDO", bg=ELITE["surface"],
            fg=ELITE["muted"], font=("Segoe UI", 10),
        ).pack(side="left")
        self.values["status"] = tk.StringVar(value="INICIALIZANDO")
        tk.Label(
            header, textvariable=self.values["status"], bg=ELITE["surface"],
            fg=ELITE["green"], font=("Segoe UI", 10, "bold"),
        ).pack(side="right", padx=16)

        content = tk.PanedWindow(
            self.root, orient="horizontal", sashwidth=5, sashrelief="flat",
            bg=ELITE["border"], bd=0,
        )
        content.pack(fill="both", expand=True)

        console_panel = tk.Frame(content, bg=ELITE["background"])
        side = tk.Frame(content, bg=ELITE["surface"], width=360)
        content.add(console_panel, stretch="always", minsize=520)
        content.add(side, stretch="never", minsize=330)

        self._section_title(console_panel, "REGISTRO OPERATIVO", "● EN VIVO")
        self.console = tk.Text(
            console_panel, bg="#050708", fg="#f2b36b", insertbackground=ELITE["orange"],
            selectbackground="#6f3e12", selectforeground="#ffffff",
            font=("Cascadia Mono", 10), wrap="word", relief="flat", padx=14,
            pady=12, state="disabled",
        )
        self.console.pack(fill="both", expand=True)
        footer = tk.Label(
            console_panel,
            text="F8: HABLAR    ·    ACTIVACIÓN: ODIN    ·    REGISTRO DEL JOURNAL EN TIEMPO REAL",
            anchor="w", bg=ELITE["surface"], fg=ELITE["muted"], padx=12, pady=8,
            font=("Segoe UI", 9),
        )
        footer.pack(fill="x")

        self._build_commander_panel(side)
        self._build_route_panel(side)
        self._build_details_panel(side)

    def _section_title(self, parent, title: str, extra: str = "") -> None:
        row = tk.Frame(parent, bg=ELITE["surface_alt"])
        row.pack(fill="x")
        tk.Label(
            row, text=title, bg=ELITE["surface_alt"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"), padx=12, pady=8,
        ).pack(side="left")
        if extra:
            tk.Label(
                row, text=extra, bg=ELITE["surface_alt"], fg=ELITE["green"],
                font=("Segoe UI", 9), padx=12,
            ).pack(side="right")

    def _build_commander_panel(self, parent) -> None:
        panel = tk.Frame(parent, bg=ELITE["surface"], highlightthickness=1,
                         highlightbackground=ELITE["border"])
        panel.pack(fill="x", padx=10, pady=(10, 5))
        self._section_title(panel, "COMANDANTE Y NAVE")
        body = tk.Frame(panel, bg=ELITE["surface"], padx=12, pady=10)
        body.pack(fill="x")
        for key in ("commander", "system", "ship", "ship_stats"):
            self.values[key] = tk.StringVar(value="—")
        tk.Label(body, textvariable=self.values["commander"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["text"],
                 font=("Segoe UI", 13, "bold")).pack(fill="x")
        tk.Label(body, textvariable=self.values["system"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["orange"],
                 font=("Segoe UI", 10)).pack(fill="x", pady=(2, 8))
        tk.Label(body, textvariable=self.values["ship"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["text"],
                 font=("Segoe UI", 10, "bold")).pack(fill="x")
        tk.Label(body, textvariable=self.values["ship_stats"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["muted"],
                 font=("Segoe UI", 9)).pack(fill="x", pady=(2, 8))
        metrics = tk.Frame(body, bg=ELITE["surface"])
        metrics.pack(fill="x")
        self._metric(metrics, "credits", "CRÉDITOS", 0, 0)
        self._metric(metrics, "pending", "EXPEDICIÓN", 0, 1)
        self._metric(metrics, "cartography", "CARTOGRAFÍA", 1, 0)
        self._metric(metrics, "exobiology", "EXOBIOLOGÍA", 1, 1)

    def _metric(self, parent, key, label, row, column) -> None:
        frame = tk.Frame(parent, bg=ELITE["surface_alt"], padx=9, pady=7,
                         highlightthickness=1, highlightbackground="#382612")
        frame.grid(row=row, column=column, sticky="nsew", padx=3, pady=3)
        parent.grid_columnconfigure(column, weight=1)
        self.values[key] = tk.StringVar(value="0 CR")
        tk.Label(frame, text=label, anchor="w", bg=ELITE["surface_alt"],
                 fg=ELITE["muted"], font=("Segoe UI", 8)).pack(fill="x")
        tk.Label(frame, textvariable=self.values[key], anchor="w",
                 bg=ELITE["surface_alt"], fg=ELITE["amber"],
                 font=("Segoe UI", 10, "bold")).pack(fill="x")

    def _build_route_panel(self, parent) -> None:
        panel = tk.Frame(parent, bg=ELITE["surface"], highlightthickness=1,
                         highlightbackground=ELITE["border"])
        panel.pack(fill="x", padx=10, pady=5)
        self._section_title(panel, "HEIMDALL · RUTA ACTIVA")
        body = tk.Frame(panel, bg=ELITE["surface"], padx=12, pady=10)
        body.pack(fill="x")
        self.values["next_system"] = tk.StringVar(value="Sin ruta activa")
        self.values["route_progress"] = tk.StringVar(value="—")
        tk.Label(body, text="SIGUIENTE SISTEMA", anchor="w", bg=ELITE["surface"],
                 fg=ELITE["muted"], font=("Segoe UI", 8)).pack(fill="x")
        tk.Label(body, textvariable=self.values["next_system"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["amber"],
                 font=("Cascadia Mono", 11, "bold"), wraplength=310,
                 justify="left").pack(fill="x", pady=(3, 7))
        row = tk.Frame(body, bg=ELITE["surface"])
        row.pack(fill="x")
        tk.Label(row, textvariable=self.values["route_progress"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["muted"],
                 font=("Segoe UI", 9)).pack(side="left", fill="x", expand=True)
        tk.Button(row, text="COPIAR", command=self._copy_next_system,
                  bg=ELITE["orange_soft"], fg="#090b0c", activebackground=ELITE["orange"],
                  activeforeground="#090b0c", relief="flat", padx=10, pady=5,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="right")

    def _build_details_panel(self, parent) -> None:
        panel = tk.Frame(parent, bg=ELITE["surface"], highlightthickness=1,
                         highlightbackground=ELITE["border"])
        panel.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        notebook = ttk.Notebook(panel, style="Odin.TNotebook")
        notebook.pack(fill="both", expand=True)
        for title, fields in (
            ("MÍMIR", (("biology", "Predicciones"), ("body", "Cuerpo actual"),
                        ("samples", "Muestras completadas"))),
            ("RUTA", (("destination", "Destino final"), ("fuel", "Combustible"),
                       ("injections", "Inyecciones B/E/P"))),
            ("RED", (("eddn", "EDDN"), ("edsm", "EDSM"), ("inara", "Inara"))),
        ):
            tab = tk.Frame(notebook, bg=ELITE["surface"], padx=12, pady=8)
            notebook.add(tab, text=title)
            for key, label in fields:
                self.values[key] = tk.StringVar(value="—")
                self._detail_row(tab, label, self.values[key])

    def _detail_row(self, parent, label, variable) -> None:
        row = tk.Frame(parent, bg=ELITE["surface"], pady=6)
        row.pack(fill="x")
        tk.Label(row, text=label, anchor="w", bg=ELITE["surface"],
                 fg=ELITE["muted"], font=("Segoe UI", 9)).pack(side="left")
        tk.Label(row, textvariable=variable, anchor="e", bg=ELITE["surface"],
                 fg=ELITE["text"], font=("Segoe UI", 9, "bold"),
                 wraplength=180, justify="right").pack(side="right", fill="x", expand=True)

    def _drain_log(self) -> None:
        chunks = []
        while True:
            try:
                chunks.append(self.log_messages.get_nowait())
            except queue.Empty:
                break
        if chunks:
            self.console.configure(state="normal")
            self.console.insert("end", "".join(chunks))
            line_count = int(self.console.index("end-1c").split(".")[0])
            if line_count > 2500:
                self.console.delete("1.0", f"{line_count - 2000}.0")
            self.console.see("end")
            self.console.configure(state="disabled")
        if not self._closing:
            self.root.after(80, self._drain_log)

    def _refresh_state(self) -> None:
        snapshot = dict(getattr(self.odin, "dashboard_snapshot", {}) or {})
        self.values["status"].set(str(snapshot.get("status", "INICIALIZANDO")).upper())
        self.values["commander"].set(snapshot.get("commander", "Comandante"))
        self.values["system"].set(snapshot.get("system", "Sin sistema"))
        ident = snapshot.get("ship_ident", "")
        self.values["ship"].set(
            snapshot.get("ship", "Nave desconocida") + (f" · {ident}" if ident else "")
        )
        fsd_health = snapshot.get("fsd_health")
        health = f" · FSD {float(fsd_health) * 100:.1f}%" if fsd_health is not None else ""
        self.values["ship_stats"].set(
            f"{float(snapshot.get('jump_range', 0)):.2f} ly{health}"
        )
        self.values["credits"].set(self._credits(snapshot.get("credits", 0)))
        expedition = snapshot.get("expedition", {})
        self.values["pending"].set(self._credits(expedition.get("total_base", 0), True))
        self.values["cartography"].set(self._credits(expedition.get("cartography", 0), True))
        self.values["exobiology"].set(self._credits(expedition.get("exobiology_base", 0), True))
        route = snapshot.get("route", {})
        self.values["next_system"].set(route.get("next_system") or "Sin ruta activa")
        self.values["route_progress"].set(
            f"{route.get('remaining_jumps', 0)} de {route.get('total_jumps', 0)} saltos restantes"
            if route else "—"
        )
        self.values["destination"].set(route.get("destination") or "—")
        fuel_capacity = float(snapshot.get("fuel_capacity", 0) or 0)
        self.values["fuel"].set(
            f"{float(snapshot.get('fuel', 0)):.1f} / {fuel_capacity:.1f} t"
            if fuel_capacity else "Sin datos"
        )
        biology = snapshot.get("biology", {})
        self.values["biology"].set(
            f"{biology.get('species', 0)} especies · {biology.get('bodies', 0)} planetas"
        )
        self.values["body"].set(snapshot.get("body") or "—")
        self.values["samples"].set(str(expedition.get("species", 0)))
        injections = snapshot.get("injections", {})
        self.values["injections"].set(
            f"{injections.get('basic', 0)} / {injections.get('standard', 0)} / {injections.get('premium', 0)}"
        )
        network = snapshot.get("network", {})
        self.values["eddn"].set("ACTIVO" if network.get("eddn") else "INACTIVO")
        self.values["edsm"].set("ACTIVO" if network.get("edsm") else "INACTIVO")
        self.values["inara"].set("ACTIVO" if network.get("inara") else "EN ESPERA")
        if not self._closing:
            self.root.after(250, self._refresh_state)

    def _copy_next_system(self) -> None:
        system = self.values["next_system"].get().strip()
        if system and system != "Sin ruta activa":
            write_text(system)

    @staticmethod
    def _credits(value, approximate: bool = False) -> str:
        prefix = "≈ " if approximate else ""
        return f"{prefix}{int(value or 0):,} CR".replace(",", ".")


def run_desktop(odin) -> None:
    OdinDesktopApp(odin).run()
