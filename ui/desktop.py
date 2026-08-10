"""Interfaz gráfica de escritorio para el Centro de Mando de ODIN."""

from __future__ import annotations

import queue
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.diagnostics import log_fatal_error
from heimdall.clipboard import write_text
from services.edsm_credentials import EDSMCredentialStore
from services.inara_credentials import InaraCredentialStore
from voice.credentials import WindowsCredentialStore
from voice.settings import VoiceSettingsRepository


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
        self.root.geometry(self.odin.config.desktop_geometry or "1180x720")
        self.root.minsize(900, 580)
        self.root.configure(bg=ELITE["background"])
        self.log_messages: queue.Queue[str] = queue.Queue()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.stream = GuiLogStream(self.log_messages)
        self.engine_thread: threading.Thread | None = None
        self._closing = False
        self.values: dict[str, tk.StringVar] = {}
        self.voice_repository = VoiceSettingsRepository(self.odin.config.data_root)
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
        try:
            self.odin.config.update_preferences(
                desktop_geometry=self.root.geometry()
            )
        except OSError:
            pass
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
        self.mute_button = tk.Button(
            header, command=self._toggle_mute, relief="flat", cursor="hand2",
            bg=ELITE["surface_alt"], fg=ELITE["amber"], padx=10, pady=5,
            font=("Segoe UI", 9, "bold"),
        )
        self.mute_button.pack(side="right", padx=(4, 0))
        tk.Button(
            header, text="CONFIGURACIÓN", command=self._open_settings,
            relief="flat", cursor="hand2", bg=ELITE["orange_soft"],
            fg=ELITE["background"], padx=10, pady=5,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=4)
        self._refresh_mute_button()

        content = tk.PanedWindow(
            self.root, orient="horizontal", sashwidth=5, sashrelief="flat",
            bg=ELITE["border"], bd=0,
        )
        content.pack(fill="both", expand=True)

        console_panel = tk.Frame(content, bg=ELITE["background"])
        side = tk.Frame(content, bg=ELITE["surface"], width=440)
        content.add(console_panel, stretch="always", minsize=520)
        content.add(side, stretch="never", minsize=390)

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
            text=self._voice_mode_footer(),
            anchor="w", bg=ELITE["surface"], fg=ELITE["muted"], padx=12, pady=8,
            font=("Segoe UI", 9),
        )
        footer.pack(fill="x")

        self._build_commander_panel(side)
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
        location_row = tk.Frame(body, bg=ELITE["surface"])
        location_row.pack(fill="x", pady=(2, 8))
        tk.Label(location_row, textvariable=self.values["system"], anchor="w",
                 bg=ELITE["surface"], fg=ELITE["orange"],
                 font=("Segoe UI", 10), wraplength=190).pack(
                     side="left", fill="x", expand=True
                 )
        self.values["community_status"] = tk.StringVar(value="○ CONSULTANDO")
        self.community_status_label = tk.Label(
            location_row, textvariable=self.values["community_status"],
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="e",
            font=("Segoe UI", 8, "bold"),
        )
        self.community_status_label.pack(side="right")
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
        body = tk.Frame(parent, bg=ELITE["surface"], padx=12, pady=12)
        body.pack(fill="both", expand=True)
        tk.Label(
            body, text="RUTA DE NEUTRONES", anchor="w", bg=ELITE["surface"],
            fg=ELITE["orange"], font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(0, 7))
        self.values["route_destination_input"] = tk.StringVar()
        destination_row = tk.Frame(body, bg=ELITE["surface"])
        destination_row.pack(fill="x", pady=(0, 9))
        self.route_destination_entry = tk.Entry(
            destination_row,
            textvariable=self.values["route_destination_input"],
            bg=ELITE["surface_alt"], fg=ELITE["text"],
            insertbackground=ELITE["orange"], relief="flat",
            font=("Cascadia Mono", 9),
        )
        self.route_destination_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.route_destination_entry.bind(
            "<Return>", lambda _event: self._request_neutron_route()
        )
        self.route_calculate_button = tk.Button(
            destination_row, text="CALCULAR", command=self._request_neutron_route,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=8, pady=5,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.route_calculate_button.pack(side="right", padx=(6, 0))
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
        mimir = tk.Frame(notebook, bg=ELITE["surface"], padx=12, pady=8)
        notebook.add(mimir, text="MÍMIR")
        for key, label in (("biology", "Resumen"),):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(mimir, label, self.values[key])
        tk.Label(
            mimir, text="PLANETAS CON BIOLOGÍA", anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(7, 3))
        self.values["biology_details"] = tk.StringVar(value="Sin señales biológicas")
        tk.Label(
            mimir, textvariable=self.values["biology_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))
        for key, label in (
            ("body", "Cuerpo actual"), ("samples", "Muestras completadas"),
        ):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(mimir, label, self.values[key])

        heimdall = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(heimdall, text="HEIMDALL")
        self._build_route_panel(heimdall)
        for key in ("destination", "fuel", "injections"):
            self.values[key] = tk.StringVar(value="—")
        for key, label in (
            ("destination", "Destino final"), ("fuel", "Combustible"),
            ("injections", "Inyecciones B/E/P"),
        ):
            self._detail_row(heimdall, label, self.values[key])

        freyja = tk.Frame(notebook, bg=ELITE["surface"], padx=12, pady=8)
        notebook.add(freyja, text="FREYJA")
        tk.Label(
            freyja, text="ELEGIR MODELO COMERCIAL", anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        trade_buttons = tk.Frame(freyja, bg=ELITE["surface"])
        trade_buttons.pack(fill="x", pady=(0, 8))
        self.trade_buttons = []
        for index, (strategy, label) in enumerate((
            ("quick", "1 · RUTA RÁPIDA"),
            ("three_station", "2 · TRES ESTACIONES"),
            ("expedition", "3 · EXPEDICIÓN"),
            ("powerplay", "4 · POWERPLAY"),
        )):
            button = tk.Button(
                trade_buttons, text=label,
                command=lambda selected=strategy: self._request_trade(selected),
                bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
                activebackground=ELITE["orange_soft"],
                activeforeground=ELITE["background"], padx=7, pady=7,
                font=("Segoe UI", 8, "bold"), cursor="hand2",
            )
            button.grid(
                row=index // 2, column=index % 2, sticky="nsew", padx=3, pady=3
            )
            trade_buttons.grid_columnconfigure(index % 2, weight=1)
            self.trade_buttons.append(button)
        for key, label in (
            ("trade_status", "Estado"), ("trade_strategy", "Modalidad"),
            ("trade_commodity", "Producto"), ("trade_target", "Próximo objetivo"),
            ("trade_units", "Toneladas"), ("trade_profit", "Beneficio estimado"),
            ("trade_balance", "Ganancia realizada"),
        ):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(freyja, label, self.values[key])

        network = tk.Frame(notebook, bg=ELITE["surface"], padx=12, pady=8)
        notebook.add(network, text="RED")
        for key, label in (("eddn", "EDDN"), ("edsm", "EDSM"), ("inara", "Inara")):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(network, label, self.values[key])

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
        community_status = snapshot.get("community_status", "unknown")
        if community_status == "registered":
            self.values["community_status"].set("◆ REGISTRO PREVIO")
            self.community_status_label.configure(fg=ELITE["green"])
        elif community_status == "unregistered":
            self.values["community_status"].set("◇ SIN REGISTRO")
            self.community_status_label.configure(fg=ELITE["amber"])
        else:
            self.values["community_status"].set("○ CONSULTANDO")
            self.community_status_label.configure(fg=ELITE["muted"])
        calculating = bool(snapshot.get("route_calculating"))
        self.route_calculate_button.configure(
            text="CALCULANDO…" if calculating else "CALCULAR",
            state="disabled" if calculating else "normal",
        )
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
        self.values["biology_details"].set(self._biology_details_text(biology))
        self.values["body"].set(snapshot.get("body") or "—")
        self.values["samples"].set(str(expedition.get("species", 0)))
        injections = snapshot.get("injections", {})
        self.values["injections"].set(
            f"{injections.get('basic', 0)} / {injections.get('standard', 0)} / {injections.get('premium', 0)}"
        )
        trade = snapshot.get("trade", {})
        trade_calculating = bool(trade.get("calculating"))
        requested_strategy = trade.get("requested_strategy", "")
        for button, strategy in zip(
            self.trade_buttons,
            ("quick", "three_station", "expedition", "powerplay"),
        ):
            button.configure(
                state="disabled" if trade_calculating else "normal",
                bg=(
                    ELITE["orange_soft"]
                    if trade_calculating and strategy == requested_strategy
                    else ELITE["surface_alt"]
                ),
            )
        self.values["trade_status"].set(trade.get("progress", "Sin ruta comercial activa"))
        self.values["trade_strategy"].set(trade.get("strategy", "Sin modalidad activa"))
        self.values["trade_commodity"].set(trade.get("commodity", "—"))
        self.values["trade_target"].set(trade.get("target", "—"))
        self.values["trade_units"].set(f"{int(trade.get('units', 0) or 0)} t")
        self.values["trade_profit"].set(
            self._credits(trade.get("estimated_profit", 0), True)
        )
        self.values["trade_balance"].set(
            self._credits(trade.get("realized_profit", 0))
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

    def _request_neutron_route(self) -> None:
        destination = self.values["route_destination_input"].get().strip()
        if not destination:
            messagebox.showwarning(
                "HEIMDALL", "Pegá o escribí el sistema de destino.", parent=self.root
            )
            return
        if self.odin.request_neutron_route(destination):
            self.route_calculate_button.configure(text="SOLICITADO", state="disabled")
            print(f"HEIMDALL: solicitud de ruta recibida hacia {destination}.")
            return
        messagebox.showinfo(
            "HEIMDALL", "Ya hay una ruta en proceso. Esperá a que finalice.",
            parent=self.root,
        )

    def _request_trade(self, strategy: str) -> None:
        labels = {
            "quick": "ruta rápida", "three_station": "tres estaciones",
            "expedition": "expedición comercial", "powerplay": "Powerplay",
        }
        if self.odin.request_trade_calculation(strategy):
            print(f"FREYJA: modalidad {labels[strategy]} solicitada desde la interfaz.")
            for button in self.trade_buttons:
                button.configure(state="disabled")
            return
        messagebox.showinfo(
            "FREYJA",
            "Freyja ya está calculando una operación. Esperá a que finalice.",
            parent=self.root,
        )

    def _toggle_mute(self) -> None:
        settings = self.voice_repository.load()
        settings.enabled = not settings.enabled
        self.voice_repository.save(settings)
        self._refresh_mute_button()
        state = "activadas" if settings.enabled else "silenciadas"
        print(f"Voces de los oficiales: {state}.")

    def _refresh_mute_button(self) -> None:
        enabled = self.voice_repository.load().enabled
        self.mute_button.configure(
            text="🔊 VOCES" if enabled else "🔇 SILENCIO",
            fg=ELITE["amber"] if enabled else ELITE["red"],
        )

    def _open_settings(self) -> None:
        window = tk.Toplevel(self.root)
        window.title("ODIN — Configuración del comandante")
        window.geometry("620x650")
        window.minsize(560, 560)
        window.resizable(True, True)
        window.configure(bg=ELITE["background"])
        window.transient(self.root)
        window.grab_set()

        container = tk.Frame(window, bg=ELITE["background"], padx=18, pady=14)
        container.pack(fill="both", expand=True)
        tk.Label(
            container, text="CONFIGURACIÓN DEL COMANDANTE",
            bg=ELITE["background"], fg=ELITE["orange"],
            font=("Segoe UI", 14, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 12))

        notebook = ttk.Notebook(container, style="Odin.TNotebook")
        notebook.pack(fill="both", expand=True)
        general_tab = tk.Frame(notebook, bg=ELITE["background"], padx=8, pady=8)
        credentials_tab = tk.Frame(
            notebook, bg=ELITE["background"], padx=8, pady=8
        )
        notebook.add(general_tab, text="GENERAL Y ESCUCHA")
        notebook.add(credentials_tab, text="API Y CREDENCIALES")

        network = self._settings_section(general_tab, "TRANSMISIÓN DE DATOS")
        network_vars = {}
        for key, label, enabled in (
            ("eddn", "Enviar mercados y Journal a EDDN", self.odin.config.eddn_upload_enabled),
            ("edsm", "Enviar progreso y exploración a EDSM", self.odin.config.edsm_upload_enabled),
            ("inara", "Enviar datos del comandante a Inara", self.odin.config.inara_upload_enabled),
        ):
            variable = tk.BooleanVar(value=enabled)
            network_vars[key] = variable
            tk.Checkbutton(
                network, text=label, variable=variable, anchor="w",
                bg=ELITE["surface"], fg=ELITE["text"], selectcolor=ELITE["surface_alt"],
                activebackground=ELITE["surface"], activeforeground=ELITE["orange"],
                font=("Segoe UI", 10),
            ).pack(fill="x", pady=3)
        tk.Label(
            network, text="Los cambios de red se aplican al reiniciar ODIN.",
            bg=ELITE["surface"], fg=ELITE["muted"], font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(5, 0))

        credentials = self._settings_section(
            credentials_tab, "API Y CREDENCIALES PERSONALES"
        )
        commander = tk.StringVar(value=self.values["commander"].get())
        frontier_id = tk.StringVar(
            value=str(
                getattr(self.odin, "dashboard_snapshot", {}).get("frontier_id", "")
                or getattr(getattr(self.odin, "commander_state", None), "fid", "")
            )
        )
        eleven_key = tk.StringVar()
        edsm_key = tk.StringVar()
        inara_key = tk.StringVar()
        installed = {
            "elevenlabs": WindowsCredentialStore().exists(),
            "edsm": EDSMCredentialStore().exists(),
            "inara": InaraCredentialStore().exists(),
        }
        for label, variable, secret, readonly, service in (
            ("Comandante", commander, False, False, ""),
            ("Frontier ID (detectado desde el Journal)", frontier_id, False, True, ""),
            ("ElevenLabs API key", eleven_key, True, False, "elevenlabs"),
            ("EDSM API key", edsm_key, True, False, "edsm"),
            ("Inara API key", inara_key, True, False, "inara"),
        ):
            label_row = tk.Frame(credentials, bg=ELITE["surface"])
            label_row.pack(fill="x", pady=(6, 2))
            tk.Label(
                label_row, text=label, bg=ELITE["surface"], fg=ELITE["muted"],
                anchor="w", font=("Segoe UI", 9),
            ).pack(side="left")
            if service:
                configured = installed[service]
                tk.Label(
                    label_row,
                    text="● CONFIGURADA" if configured else "○ NO CONFIGURADA",
                    bg=ELITE["surface"],
                    fg=ELITE["green"] if configured else ELITE["muted"],
                    font=("Segoe UI", 8, "bold"),
                ).pack(side="right")
            entry = tk.Entry(
                credentials, textvariable=variable, show="●" if secret else "",
                bg=ELITE["surface_alt"], fg=ELITE["text"], insertbackground=ELITE["orange"],
                relief="flat", font=("Segoe UI", 10),
                readonlybackground=ELITE["surface_alt"],
            )
            if readonly:
                entry.configure(state="readonly")
            entry.pack(fill="x", ipady=5)
        tk.Label(
            credentials,
            text="Dejá una clave vacía para conservar la que ya está protegida en Windows.",
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="w",
            font=("Segoe UI", 8), wraplength=510, justify="left",
        ).pack(fill="x", pady=(8, 0))

        sound = self._settings_section(general_tab, "VOZ Y MODO DE ACTIVACIÓN")
        voice_settings = self.voice_repository.load()
        initial_volume = (
            next(iter(voice_settings.officers.values())).volume
            if voice_settings.officers else 100
        )
        volume = tk.IntVar(value=initial_volume)
        volume_label = tk.StringVar(value=f"{initial_volume}%")
        volume_row = tk.Frame(sound, bg=ELITE["surface"])
        volume_row.pack(fill="x")
        tk.Scale(
            volume_row, from_=0, to=100, orient="horizontal", variable=volume,
            command=lambda value: volume_label.set(f"{int(float(value))}%"),
            bg=ELITE["surface"], fg=ELITE["text"], troughcolor=ELITE["surface_alt"],
            activebackground=ELITE["orange"], highlightthickness=0,
            showvalue=False, length=430,
        ).pack(side="left", fill="x", expand=True)
        tk.Label(
            volume_row, textvariable=volume_label, width=5,
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Segoe UI", 10, "bold"),
        ).pack(side="right")
        current_mode = (
            "both" if self.odin.config.push_to_talk_enabled and self.odin.config.wake_word_enabled
            else "ptt" if self.odin.config.push_to_talk_enabled else "wake"
        )
        voice_mode = tk.StringVar(value=current_mode)
        tk.Label(
            sound, text="MODO DE ACTIVACIÓN", bg=ELITE["surface"],
            fg=ELITE["muted"], anchor="w", font=("Segoe UI", 8, "bold"),
        ).pack(fill="x", pady=(8, 2))
        modes = tk.Frame(sound, bg=ELITE["surface"])
        modes.pack(fill="x")
        for value, label in (
            ("ptt", "Push to Talk (F8)"),
            ("wake", 'Activación por voz ("ODIN")'),
            ("both", "Ambos"),
        ):
            tk.Radiobutton(
                modes, text=label, variable=voice_mode, value=value,
                bg=ELITE["surface"], fg=ELITE["text"],
                selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
                activeforeground=ELITE["orange"], font=("Segoe UI", 9),
            ).pack(side="left", padx=(0, 10))

        def save() -> None:
            name = commander.get().strip()
            if (edsm_key.get().strip() or inara_key.get().strip()) and not name:
                messagebox.showerror("ODIN", "Indicá el nombre del comandante.", parent=window)
                return
            try:
                if eleven_key.get().strip():
                    WindowsCredentialStore().set(eleven_key.get().strip())
                if edsm_key.get().strip():
                    EDSMCredentialStore().set(name, edsm_key.get().strip())
                if inara_key.get().strip():
                    InaraCredentialStore().set(
                        name, inara_key.get().strip(), frontier_id.get().strip()
                    )
                self.odin.config.update_preferences(
                    eddn_capture_enabled=network_vars["eddn"].get(),
                    eddn_upload_enabled=network_vars["eddn"].get(),
                    edsm_capture_enabled=network_vars["edsm"].get(),
                    edsm_upload_enabled=network_vars["edsm"].get(),
                    inara_capture_enabled=network_vars["inara"].get(),
                    inara_upload_enabled=network_vars["inara"].get(),
                    push_to_talk_enabled=voice_mode.get() in {"ptt", "both"},
                    wake_word_enabled=voice_mode.get() in {"wake", "both"},
                )
                voice_settings = self.voice_repository.load()
                for assignment in voice_settings.officers.values():
                    assignment.volume = volume.get()
                self.voice_repository.save(voice_settings)
            except (OSError, ValueError) as error:
                messagebox.showerror("ODIN", f"No se pudo guardar: {error}", parent=window)
                return
            print("Configuración personal guardada. Los cambios de red se aplicarán al reiniciar ODIN.")
            messagebox.showinfo(
                "ODIN", "Configuración guardada de forma segura.", parent=window
            )
            window.destroy()

        actions = tk.Frame(container, bg=ELITE["background"])
        actions.pack(fill="x", pady=(12, 0))
        tk.Button(
            actions, text="CANCELAR", command=window.destroy,
            bg=ELITE["surface_alt"], fg=ELITE["text"], relief="flat",
            activebackground=ELITE["border"], activeforeground=ELITE["text"],
            padx=12, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2",
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(
            actions, text="ACEPTAR", command=save,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=12, pady=8,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        ).pack(side="right", fill="x", expand=True, padx=(5, 0))

    def _settings_section(self, parent, title: str):
        panel = tk.Frame(
            parent, bg=ELITE["surface"], padx=12, pady=10,
            highlightthickness=1, highlightbackground=ELITE["border"],
        )
        panel.pack(fill="x", pady=5)
        tk.Label(
            panel, text=title, bg=ELITE["surface"], fg=ELITE["orange"],
            anchor="w", font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(0, 4))
        return panel

    def _voice_mode_footer(self) -> str:
        modes = []
        if self.odin.config.push_to_talk_enabled:
            modes.append("F8: HABLAR")
        if self.odin.config.wake_word_enabled:
            modes.append("ACTIVACIÓN: ODIN")
        modes.append("JOURNAL EN TIEMPO REAL")
        return "    ·    ".join(modes)

    @staticmethod
    def _credits(value, approximate: bool = False) -> str:
        prefix = "≈ " if approximate else ""
        return f"{prefix}{int(value or 0):,} CR".replace(",", ".")

    @staticmethod
    def _biology_details_text(biology: dict) -> str:
        lines = []
        for item in biology.get("details", ()):
            signals = int(item.get("signals", 0) or 0)
            signal_text = f" · {signals} señales" if signals else ""
            lines.append(f"◆ {item.get('body', 'Cuerpo desconocido')}{signal_text}")
            for species in item.get("confirmed", ()):
                lines.append(f"  ✓ {species}")
            probable_values = item.get("probable_values", {})
            probable_rewards = item.get("probable_rewards", {})
            for species in item.get("probable", ()):
                reward = probable_rewards.get(species, {})
                base_value = reward.get("base", probable_values.get(species))
                potential_value = reward.get("potential", base_value)
                first_footfall = bool(
                    base_value and potential_value == int(base_value) * 5
                )
                value = potential_value if first_footfall else base_value
                reward_type = "PRIMERA PISADA ×5" if first_footfall else "NORMAL"
                value_text = (
                    f" — {reward_type}: {OdinDesktopApp._credits(value, True)}"
                    if value else ""
                )
                lines.append(f"  ◇ {species}{value_text}")
            if not item.get("confirmed") and not item.get("probable"):
                lines.append("  ○ Especies por identificar")
            lines.append("")
        return "\n".join(lines).rstrip() or "Sin señales biológicas"


def run_desktop(odin) -> None:
    OdinDesktopApp(odin).run()
