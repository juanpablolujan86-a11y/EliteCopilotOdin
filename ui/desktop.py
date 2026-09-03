"""Interfaz gráfica de escritorio para el Centro de Mando de ODIN."""

from __future__ import annotations

import queue
import ctypes
import logging
import sys
import threading
import tkinter as tk
from tkinter import messagebox, ttk

from core.diagnostics import log_fatal_error
from core.database import DatabaseManager
from core.localization import SUPPORTED_LANGUAGES, text as localized_text
from platform_adapters.clipboard import copy_text
from guardian.unlocks import GUARDIAN_MODULE_RECIPES
from core.officer_names import public_officer_name
from engineering.planner import ENGINEERS, ENGINEERING_PLANS
from services.edsm_credentials import EDSMCredentialStore
from services.inara_credentials import InaraCredentialStore
from intelligence.openai_client import OpenAICredentialStore
from intelligence.voice_calibration import CALIBRATION_COMMANDS
from intelligence.voice_calibration import VoiceCalibrationManager, analyze_calibration_wav
from intelligence.command_memory import VoiceCommandMemory
from speech.recorder import MicrophoneError
from speech.whisper import TranscriptionError
from security.secret_store import create_secret_store
from voice.credentials import ELEVENLABS_TARGET
from voice.settings import VoiceSettingsRepository, apply_language_voice_preset
from ui.voice_commands import voice_command_catalog


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
        try:
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "ODIN.EliteCopilot.Desktop"
            )
        except (AttributeError, OSError):
            pass
        self.root = tk.Tk()
        self.root.report_callback_exception = self._report_callback_exception
        try:
            icon = self.odin.config.project_root / "assets" / "odin_raven.ico"
            if icon.exists():
                self.root.iconbitmap(default=str(icon))
        except tk.TclError:
            pass
        self.root.title(self._t("app.title"))
        self.root.geometry(self.odin.config.desktop_geometry or "1180x720")
        self.root.minsize(900, 580)
        self.root.configure(bg=ELITE["background"])
        self.log_messages: queue.Queue[str] = queue.Queue()
        self.original_stdout = sys.stdout
        self.original_stderr = sys.stderr
        self.stream = GuiLogStream(self.log_messages)
        self.engine_thread: threading.Thread | None = None
        self._closing = False
        self._geometry_save_job: str | None = None
        self._last_normal_geometry = self.odin.config.desktop_geometry or "1180x720"
        self.values: dict[str, tk.StringVar] = {}
        self._guardian_collection_system = ""
        self._guardian_broker_system = ""
        self._guardian_selection_restored = False
        self._engineering_system = ""
        self._engineering_selection_restored = False
        self.voice_repository = VoiceSettingsRepository(self.odin.config.data_root)
        # SQLite vincula cada conexión al hilo que la creó. El motor de ODIN
        # abre la suya en ``odin-engine``; la GUI necesita una conexión propia
        # para consultar y editar la calibración sin cruzar hilos.
        self.voice_calibration_database = DatabaseManager(self.odin.config.data_root)
        self.voice_calibration_database.connect()
        self.voice_calibration_database.create_tables()
        self.voice_calibration = VoiceCalibrationManager(
            VoiceCommandMemory(self.voice_calibration_database)
        )
        self._build_styles()
        self._build_window()
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        self.root.bind("<Configure>", self._schedule_geometry_save, add="+")

    def _t(self, key: str, **values) -> str:
        return localized_text(key, self.odin.config.language, **values)

    def _report_callback_exception(self, exception, value, traceback) -> None:
        logging.getLogger("odin").error(
            "GUI_CALLBACK_FAILED | %s: %s",
            exception.__name__, value,
            exc_info=(exception, value, traceback),
        )
        print(f"ODIN encontró un error en la interfaz: {value}")

    def _schedule_geometry_save(self, _event=None) -> None:
        """Persiste posición y tamaño aunque ODIN sea cerrado externamente."""

        if self._closing or self.root.state() != "normal":
            return
        self._last_normal_geometry = self.root.geometry()
        if self._geometry_save_job is not None:
            self.root.after_cancel(self._geometry_save_job)
        self._geometry_save_job = self.root.after(600, self._save_geometry)

    def _save_geometry(self) -> None:
        self._geometry_save_job = None
        try:
            self.odin.config.update_preferences(
                desktop_geometry=self._last_normal_geometry
            )
        except OSError:
            pass

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
        if self.root.state() == "normal":
            self._last_normal_geometry = self.root.geometry()
        self._save_geometry()
        self.odin.request_stop()
        self.root.after(150, self._finish_close)

    def _finish_close(self) -> None:
        if self.engine_thread is not None and self.engine_thread.is_alive():
            self.engine_thread.join(timeout=0.05)
            self.root.after(100, self._finish_close)
            return
        self.voice_calibration_database.disconnect()
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
            header, text=self._t("app.command_center"), bg=ELITE["surface"],
            fg=ELITE["muted"], font=("Segoe UI", 10),
        ).pack(side="left")
        self.values["status"] = tk.StringVar(value=self._t("app.initializing"))
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
            header, text=self._t("app.settings"), command=self._open_settings,
            relief="flat", cursor="hand2", bg=ELITE["orange_soft"],
            fg=ELITE["background"], padx=10, pady=5,
            font=("Segoe UI", 9, "bold"),
        ).pack(side="right", padx=4)
        tk.Button(
            header, text=self._t("app.voice_commands"),
            command=self._open_voice_commands,
            relief="flat", cursor="hand2", bg=ELITE["surface_alt"],
            fg=ELITE["amber"], padx=10, pady=5,
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

        self._section_title(
            console_panel, self._t("app.operational_log"), self._t("app.live")
        )
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
        self._section_title(panel, self._t("app.commander_ship"))
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
        self._metric(metrics, "credits", self._t("app.credits"), 0, 0)
        self._metric(metrics, "pending", self._t("app.expedition"), 0, 1)
        self._metric(metrics, "cartography", self._t("app.cartography"), 1, 0)
        self._metric(metrics, "exobiology", self._t("app.exobiology"), 1, 1)

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
            body, text=self._t("heimdall.neutron_route"), anchor="w", bg=ELITE["surface"],
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
        button_row = tk.Frame(body, bg=ELITE["surface"])
        button_row.pack(fill="x", pady=(0, 9))
        self.route_calculate_button = tk.Button(
            button_row, text=self._t("heimdall.calculate_neutron"), command=self._request_neutron_route,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=8, pady=5,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.route_calculate_button.pack(side="left", fill="x", expand=True)
        self.exact_route_calculate_button = tk.Button(
            button_row, text=self._t("heimdall.calculate_exact"),
            command=self._request_exact_route,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=8, pady=5,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.exact_route_calculate_button.pack(
            side="left", fill="x", expand=True, padx=(6, 0)
        )
        self.values["next_system"] = tk.StringVar(value=self._t("heimdall.no_route"))
        self.values["route_progress"] = tk.StringVar(value=self._t("common.none"))
        tk.Label(body, text=self._t("heimdall.next_system"), anchor="w", bg=ELITE["surface"],
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
        tk.Button(row, text=self._t("common.copy"), command=self._copy_next_system,
                  bg=ELITE["orange_soft"], fg="#090b0c", activebackground=ELITE["orange"],
                  activeforeground="#090b0c", relief="flat", padx=10, pady=5,
                  font=("Segoe UI", 9, "bold"), cursor="hand2").pack(side="right")

    def _build_details_panel(self, parent) -> None:
        panel = tk.Frame(parent, bg=ELITE["surface"], highlightthickness=1,
                         highlightbackground=ELITE["border"])
        panel.pack(fill="both", expand=True, padx=10, pady=(5, 10))
        notebook = ttk.Notebook(panel, style="Odin.TNotebook")
        notebook.pack(fill="both", expand=True)
        mimir_tab = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(mimir_tab, text="MÍMIR")
        mimir = self._scrollable_tab(mimir_tab)
        for key, label in (("biology", self._t("mimir.summary")),):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(mimir, label, self.values[key])
        tk.Label(
            mimir, text=self._t("mimir.biological_planets"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(7, 3))
        self.values["biology_details"] = tk.StringVar(value=self._t("mimir.no_biology"))
        tk.Label(
            mimir, textvariable=self.values["biology_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))
        tk.Label(
            mimir, text=self._t("mimir.sample_tracking"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(5, 3))
        self.values["sampling_details"] = tk.StringVar(value=self._t("mimir.no_samples"))
        tk.Label(
            mimir, textvariable=self.values["sampling_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["text"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))
        for key, label in (
            ("body", self._t("mimir.current_body")),
            ("samples", self._t("mimir.completed_samples")),
        ):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(mimir, label, self.values[key])

        heimdall = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(heimdall, text=public_officer_name("HEIMDALL"))
        self._build_route_panel(heimdall)
        for key in ("destination", "route_comparison", "route_leg", "exact_plotter", "high_energy", "fuel", "injections"):
            self.values[key] = tk.StringVar(value="—")
        for key, label in (
            ("destination", self._t("heimdall.final_destination")),
            ("route_comparison", self._t("heimdall.route_comparison")),
            ("route_leg", self._t("heimdall.next_leg")),
            ("exact_plotter", self._t("heimdall.exact_plotter")),
            ("high_energy", self._t("heimdall.high_energy")),
            ("fuel", self._t("heimdall.fuel")),
            ("injections", self._t("heimdall.injections")),
        ):
            self._detail_row(heimdall, label, self.values[key])

        freyja_tab = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(freyja_tab, text="FREYJA")
        freyja = self._scrollable_tab(freyja_tab)
        tk.Label(
            freyja, text=self._t("freyja.choose_model"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        commodity_row = tk.Frame(freyja, bg=ELITE["surface"])
        commodity_row.pack(fill="x", pady=(0, 8))
        tk.Label(
            commodity_row, text=self._t("freyja.commodity"), bg=ELITE["surface"],
            fg=ELITE["muted"], font=("Segoe UI", 8),
        ).pack(side="left", padx=(0, 8))
        self.values["trade_commodity_input"] = tk.StringVar()
        self.trade_commodity_entry = tk.Entry(
            commodity_row,
            textvariable=self.values["trade_commodity_input"],
            bg=ELITE["surface_alt"], fg=ELITE["text"],
            insertbackground=ELITE["orange"], relief="flat",
            font=("Segoe UI", 9),
        )
        self.trade_commodity_entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.trade_commodity_entry.insert(0, "")
        self.values["trade_allow_planetary"] = tk.BooleanVar(value=True)
        tk.Checkbutton(
            freyja, text=self._t("freyja.include_planetary"),
            variable=self.values["trade_allow_planetary"],
            bg=ELITE["surface"], fg=ELITE["amber"],
            activebackground=ELITE["surface"], activeforeground=ELITE["orange"],
            selectcolor=ELITE["surface_alt"], anchor="w",
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        ).pack(fill="x", pady=(0, 8))
        self.powerplay_sale_button = tk.Button(
            freyja, text=self._t("freyja.powerplay_sale"),
            command=self._request_powerplay_sale,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=7, pady=6,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.powerplay_sale_button.pack(fill="x", pady=(0, 8))
        trade_buttons = tk.Frame(freyja, bg=ELITE["surface"])
        trade_buttons.pack(fill="x", pady=(0, 8))
        self.trade_buttons = []
        for index, (strategy, label) in enumerate((
            ("quick", self._t("freyja.quick")),
            ("three_station", self._t("freyja.three")),
            ("expedition", self._t("freyja.expedition")),
            ("powerplay", self._t("freyja.powerplay")),
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
            ("trade_status", self._t("freyja.status")),
            ("trade_strategy", self._t("freyja.strategy")),
            ("trade_commodity", self._t("freyja.product")),
            ("trade_target", self._t("freyja.next_target")),
            ("trade_units", self._t("freyja.tons")),
            ("trade_profit", self._t("freyja.estimated_profit")),
            ("trade_unit_price", self._t("freyja.unit_price")),
            ("trade_distance", self._t("freyja.distance")),
            ("trade_powerplay_state", self._t("freyja.powerplay_territory")),
            ("trade_balance", self._t("freyja.realized_profit")),
        ):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(freyja, label, self.values[key])

        powerplay_tab = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(powerplay_tab, text="POWERPLAY")
        powerplay = self._scrollable_tab(powerplay_tab)
        tk.Label(
            powerplay, text=self._t("powerplay.choose_activity"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        self.powerplay_subject = tk.StringVar()
        tk.Label(
            powerplay, text=self._t("powerplay.subject"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["muted"], font=("Segoe UI", 8),
        ).pack(fill="x", pady=(0, 2))
        tk.Entry(
            powerplay, textvariable=self.powerplay_subject,
            bg=ELITE["surface_alt"], fg=ELITE["text"],
            insertbackground=ELITE["orange"], relief="flat",
            font=("Segoe UI", 9),
        ).pack(fill="x", ipady=5, pady=(0, 6))
        activity_buttons = tk.Frame(powerplay, bg=ELITE["surface"])
        activity_buttons.pack(fill="x", pady=(0, 8))
        self.powerplay_activity_buttons = []
        for index, (activity, key) in enumerate((
            ("combat", "powerplay.combat"), ("trade", "powerplay.trade"),
            ("mining", "powerplay.mining"), ("transport", "powerplay.transport"),
            ("exploration", "powerplay.exploration"),
            ("on_foot", "powerplay.on_foot"), ("salvage", "powerplay.salvage"),
        )):
            button = tk.Button(
                activity_buttons, text=self._t(key),
                command=lambda selected=activity: self._request_powerplay_activity(selected),
                bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
                activebackground=ELITE["orange_soft"],
                activeforeground=ELITE["background"], padx=6, pady=7,
                font=("Segoe UI", 8, "bold"), cursor="hand2",
            )
            button.grid(row=index // 2, column=index % 2, sticky="nsew", padx=3, pady=3)
            activity_buttons.grid_columnconfigure(index % 2, weight=1)
            self.powerplay_activity_buttons.append(button)
        for key, label in (
            ("powerplay_power", self._t("powerplay.power")),
            ("powerplay_rank", self._t("powerplay.rank")),
            ("powerplay_merits", self._t("powerplay.merits")),
            ("powerplay_earned", self._t("powerplay.earned")),
            ("powerplay_territory", self._t("powerplay.territory")),
            ("powerplay_activity", self._t("powerplay.activity")),
        ):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(powerplay, label, self.values[key])
        self.values["powerplay_objective"] = tk.StringVar(value="—")
        tk.Label(
            powerplay, textvariable=self.values["powerplay_objective"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["amber"], font=("Segoe UI", 9),
            justify="left", wraplength=285,
        ).pack(fill="x", pady=(5, 8))
        tk.Label(
            powerplay, text=self._t("powerplay.locations"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(3, 4))
        self.powerplay_location_list = tk.Listbox(
            powerplay, height=6, bg=ELITE["surface_alt"], fg=ELITE["text"],
            selectbackground=ELITE["orange_soft"], selectforeground=ELITE["background"],
            relief="flat", font=("Cascadia Mono", 8), exportselection=False,
        )
        self.powerplay_location_list.pack(fill="x", pady=(0, 6))
        self.powerplay_location_systems = []
        self._powerplay_location_signature = ()
        powerplay_actions = tk.Frame(powerplay, bg=ELITE["surface"])
        powerplay_actions.pack(fill="x")
        tk.Button(
            powerplay_actions, text=self._t("common.copy"),
            command=self._copy_powerplay_location, bg=ELITE["orange_soft"],
            fg=ELITE["background"], relief="flat", padx=7, pady=5,
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            powerplay_actions, text=self._t("powerplay.use_heimdall"),
            command=self._powerplay_location_to_heimdall,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            padx=7, pady=5,
        ).pack(side="left", fill="x", expand=True, padx=(6, 0))
        tk.Button(
            powerplay, text=self._t("powerplay.open_weekly_guide"),
            command=self._open_powerplay_weekly_guide,
            bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
            font=("Segoe UI", 8, "bold"), cursor="hand2", pady=7,
        ).pack(fill="x", pady=(10, 4))

        brokk_tab = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(brokk_tab, text="BROKK")
        brokk = self._scrollable_tab(brokk_tab)
        tk.Label(
            brokk, text=self._t("brokk.operation"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        technique_row = tk.Frame(brokk, bg=ELITE["surface"])
        technique_row.pack(fill="x", pady=(0, 6))
        tk.Label(
            technique_row, text=self._t("brokk.technique"), bg=ELITE["surface"],
            fg=ELITE["muted"], font=("Segoe UI", 8),
        ).pack(side="left", padx=(0, 7))
        self.values["mining_technique_input"] = tk.StringVar(
            value=self._t("brokk.technique.laser")
        )
        technique_selector = ttk.Combobox(
            technique_row,
            textvariable=self.values["mining_technique_input"],
            values=(
                self._t("brokk.technique.laser"), self._t("brokk.technique.abrasion"),
                self._t("brokk.technique.subsurface"), self._t("brokk.technique.core"),
            ),
            state="readonly", font=("Segoe UI", 9),
        )
        technique_selector.pack(side="right", fill="x", expand=True)
        mining_target_row = tk.Frame(brokk, bg=ELITE["surface"])
        mining_target_row.pack(fill="x", pady=(0, 6))
        self.values["mining_target_input"] = tk.StringVar()
        tk.Entry(
            mining_target_row, textvariable=self.values["mining_target_input"],
            bg=ELITE["surface_alt"], fg=ELITE["text"],
            insertbackground=ELITE["orange"], relief="flat",
            font=("Segoe UI", 9),
        ).pack(side="left", fill="x", expand=True, ipady=5, padx=(0, 5))
        tk.Button(
            mining_target_row, text=self._t("brokk.prepare"),
            command=lambda: self._control_mining("start"),
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=7, pady=5,
        ).pack(side="right")
        self.mining_search_button = tk.Button(
            brokk, text=self._t("brokk.search_mine"),
            command=self._request_mining_search,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=7, pady=6,
        )
        self.mining_search_button.pack(fill="x", pady=(0, 7))
        self.values["mining_search_status"] = tk.StringVar(
            value=self._t("brokk.search_hint")
        )
        tk.Label(
            brokk, textvariable=self.values["mining_search_status"],
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="w",
            justify="left", wraplength=290, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(0, 6))
        self.mining_search_rows = {}
        for tier, label in (("short", self._t("brokk.short")), ("medium", self._t("brokk.medium")), ("long", self._t("brokk.long"))):
            row = tk.Frame(brokk, bg=ELITE["surface_alt"], padx=6, pady=5)
            row.pack(fill="x", pady=2)
            value = tk.StringVar(value=f"{label} · {self._t('brokk.no_result')}")
            self.values[f"mining_search_{tier}"] = value
            tk.Label(
                row, textvariable=value, bg=ELITE["surface_alt"], fg=ELITE["text"],
                anchor="w", justify="left", wraplength=190,
                font=("Cascadia Mono", 8),
            ).pack(side="left", fill="x", expand=True)
            copy_button = tk.Button(
                row, text=self._t("common.copy"), state="disabled",
                command=lambda selected=tier: self._copy_mining_system(selected),
                bg=ELITE["surface"], fg=ELITE["amber"], relief="flat",
                font=("Segoe UI", 7, "bold"), cursor="hand2",
            )
            copy_button.pack(side="left", padx=2)
            route_button = tk.Button(
                row, text=self._t("brokk.route"), state="disabled",
                command=lambda selected=tier: self._route_mining_system(selected),
                bg=ELITE["surface"], fg=ELITE["amber"], relief="flat",
                font=("Segoe UI", 7, "bold"), cursor="hand2",
            )
            route_button.pack(side="right")
            self.mining_search_rows[tier] = (copy_button, route_button, "")
        mining_actions = tk.Frame(brokk, bg=ELITE["surface"])
        mining_actions.pack(fill="x", pady=(0, 8))
        for text, action in ((self._t("brokk.pause"), "pause"), (self._t("brokk.close"), "close")):
            tk.Button(
                mining_actions, text=text,
                command=lambda selected=action: self._control_mining(selected),
                bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
                activebackground=ELITE["border"], activeforeground=ELITE["text"],
                font=("Segoe UI", 8, "bold"), cursor="hand2", pady=5,
            ).pack(side="left", fill="x", expand=True, padx=3)
        self.mining_sale_button = tk.Button(
            brokk, text=self._t("brokk.search_sale"),
            command=self._request_mining_sale_search,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=7, pady=6,
        )
        self.mining_sale_button.pack(fill="x", pady=(0, 8))
        for key, label in (
            ("mining_status", self._t("brokk.status")),
            ("mining_target", self._t("brokk.target")),
            ("mining_location", self._t("brokk.location")),
            ("mining_technique", self._t("brokk.technique")),
            ("mining_environment", self._t("brokk.environment")),
            ("mining_surface_vehicle", self._t("brokk.surface_vehicle")),
            ("mining_geology", self._t("brokk.geology")),
            ("mining_prospected", self._t("brokk.prospected")),
            ("mining_cargo", self._t("brokk.cargo")),
            ("mining_revenue", self._t("brokk.performance")),
            ("mining_sale_target", self._t("brokk.sale_target")),
            ("mining_sale_demand", self._t("brokk.sale_demand")),
            ("mining_sale_distance", self._t("freyja.distance")),
            ("mining_global_sale", self._t("brokk.global_sale")),
        ):
            self.values[key] = tk.StringVar(value="—")
            self._detail_row(brokk, label, self.values[key])
        tk.Label(
            brokk, text=self._t("brokk.last_asteroid"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(9, 3))
        self.values["mining_prospect_details"] = tk.StringVar(
            value=self._t("brokk.no_prospects")
        )
        tk.Label(
            brokk, textvariable=self.values["mining_prospect_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))
        tk.Label(
            brokk, text=self._t("brokk.refined"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(6, 3))
        self.values["mining_refined_details"] = tk.StringVar(
            value=self._t("brokk.no_refined")
        )
        tk.Label(
            brokk, textvariable=self.values["mining_refined_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["text"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))
        tk.Label(
            brokk, text=self._t("brokk.materials"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(6, 3))
        self.values["mining_material_details"] = tk.StringVar(
            value=self._t("brokk.no_materials")
        )
        tk.Label(
            brokk, textvariable=self.values["mining_material_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["text"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))
        tk.Label(
            brokk, text=self._t("brokk.ship_capabilities"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(6, 3))
        self.values["mining_equipment_details"] = tk.StringVar(
            value=self._t("brokk.waiting_equipment")
        )
        tk.Label(
            brokk, textvariable=self.values["mining_equipment_details"], anchor="nw",
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Cascadia Mono", 9), justify="left", wraplength=285,
        ).pack(fill="x", pady=(0, 7))

        guardian_tab = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(guardian_tab, text=public_officer_name("GUARDIAN"))
        guardian = self._scrollable_tab(guardian_tab)
        tk.Label(
            guardian, text=self._t("guardian.unlock"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        self.guardian_module_by_label = {
            recipe["label"]: key
            for key, recipe in GUARDIAN_MODULE_RECIPES.items()
        }
        first_guardian_module = next(iter(self.guardian_module_by_label))
        self.values["guardian_selection"] = tk.StringVar(
            value=first_guardian_module
        )
        self.guardian_selector = ttk.Combobox(
            guardian, textvariable=self.values["guardian_selection"],
            values=tuple(self.guardian_module_by_label), state="readonly",
            font=("Segoe UI", 9),
        )
        self.guardian_selector.pack(fill="x", pady=(0, 9), ipady=4)
        self.guardian_search_button = tk.Button(
            guardian, text=self._t("guardian.search"),
            command=self._request_guardian_search,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=8, pady=7,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.guardian_search_button.pack(fill="x", pady=(0, 9))
        self.values["guardian_status"] = tk.StringVar(value=self._t("guardian.reading"))
        tk.Label(
            guardian, textvariable=self.values["guardian_status"], anchor="w",
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(0, 8))
        tk.Label(
            guardian, text=self._t("guardian.requirements"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(4, 3))
        self.values["guardian_requirements"] = tk.StringVar(
            value=self._t("guardian.waiting")
        )
        tk.Label(
            guardian, textvariable=self.values["guardian_requirements"],
            anchor="nw", justify="left", wraplength=300,
            bg=ELITE["surface"], fg=ELITE["text"],
            font=("Cascadia Mono", 9),
        ).pack(fill="x", pady=(0, 7))
        tk.Label(
            guardian, text=self._t("guardian.where"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(7, 3))
        self.values["guardian_collection"] = tk.StringVar(
            value=self._t("guardian.select_search")
        )
        tk.Label(
            guardian, textvariable=self.values["guardian_collection"],
            anchor="nw", justify="left", wraplength=300,
            bg=ELITE["surface"], fg=ELITE["text"],
            font=("Cascadia Mono", 9),
        ).pack(fill="x", pady=(0, 7))
        self.guardian_collection_copy_button = tk.Button(
            guardian, text=self._t("guardian.copy_collection"),
            command=lambda: self._copy_guardian_system("collection"),
            state="disabled", bg=ELITE["surface_alt"], fg=ELITE["amber"],
            disabledforeground=ELITE["muted"], relief="flat",
            activebackground=ELITE["border"], activeforeground=ELITE["text"],
            padx=8, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.guardian_collection_copy_button.pack(fill="x", pady=(0, 7))
        tk.Label(
            guardian, text=self._t("guardian.broker"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(7, 3))
        self.values["guardian_broker"] = tk.StringVar(value=self._t("guardian.no_search"))
        tk.Label(
            guardian, textvariable=self.values["guardian_broker"],
            anchor="nw", justify="left", wraplength=300,
            bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Cascadia Mono", 9),
        ).pack(fill="x", pady=(0, 7))
        self.guardian_broker_copy_button = tk.Button(
            guardian, text=self._t("guardian.copy_broker"),
            command=lambda: self._copy_guardian_system("broker"),
            state="disabled", bg=ELITE["surface_alt"], fg=ELITE["amber"],
            disabledforeground=ELITE["muted"], relief="flat",
            activebackground=ELITE["border"], activeforeground=ELITE["text"],
            padx=8, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.guardian_broker_copy_button.pack(fill="x", pady=(0, 7))

        engineering_tab = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(engineering_tab, text=public_officer_name("INGENIERÍA"))
        engineering = self._scrollable_tab(engineering_tab)
        tk.Label(
            engineering, text=self._t("engineering.unlocks"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        self.values["engineering_engineer"] = tk.StringVar(value=next(iter(ENGINEERS)))
        self.engineering_engineer_selector = ttk.Combobox(
            engineering, textvariable=self.values["engineering_engineer"],
            values=tuple(ENGINEERS), state="readonly", font=("Segoe UI", 9),
        )
        self.engineering_engineer_selector.pack(fill="x", pady=(0, 7), ipady=3)
        self.engineering_engineer_selector.bind(
            "<<ComboboxSelected>>", lambda _event: self._refresh_engineering(
                getattr(self.odin, "dashboard_snapshot", {}).get("engineering", {})
            )
        )
        self.values["engineering_engineer_details"] = tk.StringVar(value=self._t("common.no_data"))
        tk.Label(
            engineering, textvariable=self.values["engineering_engineer_details"],
            anchor="nw", justify="left", wraplength=300, bg=ELITE["surface"],
            fg=ELITE["text"], font=("Cascadia Mono", 9),
        ).pack(fill="x", pady=(0, 7))
        self.engineering_copy_button = tk.Button(
            engineering, text=self._t("engineering.copy_system"),
            command=self._copy_engineering_system, state="disabled",
            bg=ELITE["surface_alt"], fg=ELITE["amber"],
            disabledforeground=ELITE["muted"], relief="flat",
            padx=8, pady=6, font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.engineering_copy_button.pack(fill="x", pady=(0, 12))

        tk.Label(
            engineering, text=self._t("engineering.plan"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        self.engineering_plan_by_label = {
            item["label"]: key for key, item in ENGINEERING_PLANS.items()
        }
        first_plan = next(iter(self.engineering_plan_by_label))
        self.values["engineering_plan"] = tk.StringVar(value=first_plan)
        self.engineering_plan_selector = ttk.Combobox(
            engineering, textvariable=self.values["engineering_plan"],
            values=tuple(self.engineering_plan_by_label), state="readonly",
            font=("Segoe UI", 9),
        )
        self.engineering_plan_selector.pack(fill="x", pady=(0, 7), ipady=3)
        self.engineering_plan_selector.bind(
            "<<ComboboxSelected>>", lambda _event: self._refresh_engineering(
                getattr(self.odin, "dashboard_snapshot", {}).get("engineering", {})
            )
        )
        tk.Button(
            engineering, text=self._t("engineering.save_plan"),
            command=self._save_engineering_plan, bg=ELITE["orange_soft"],
            fg=ELITE["background"], relief="flat", padx=8, pady=6,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        ).pack(fill="x", pady=(0, 8))
        self.values["engineering_plan_status"] = tk.StringVar(value=self._t("engineering.no_plan"))
        tk.Label(
            engineering, textvariable=self.values["engineering_plan_status"],
            anchor="w", bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(0, 5))
        self.values["engineering_requirements"] = tk.StringVar(value=self._t("common.no_data"))
        tk.Label(
            engineering, textvariable=self.values["engineering_requirements"],
            anchor="nw", justify="left", wraplength=300, bg=ELITE["surface"],
            fg=ELITE["text"], font=("Cascadia Mono", 9),
        ).pack(fill="x", pady=(0, 12))
        tk.Label(
            engineering, text=self._t("engineering.modules"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 7))
        self.values["engineering_modules"] = tk.StringVar(value=self._t("engineering.no_modules"))
        tk.Label(
            engineering, textvariable=self.values["engineering_modules"],
            anchor="nw", justify="left", wraplength=300, bg=ELITE["surface"],
            fg=ELITE["text"], font=("Cascadia Mono", 8),
        ).pack(fill="x", pady=(0, 7))

        ai_tab = tk.Frame(notebook, bg=ELITE["surface"])
        if not self.odin.config.public_beta_no_ai:
            notebook.add(ai_tab, text=self._t("ai.tab"))
        ai = self._scrollable_tab(ai_tab)
        tk.Label(
            ai, text=self._t("ai.coordinator"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 10, "bold"),
        ).pack(fill="x", pady=(2, 5))
        tk.Label(
            ai, text=self._t("ai.help"), anchor="nw", justify="left",
            wraplength=300, bg=ELITE["surface"], fg=ELITE["muted"],
            font=("Segoe UI", 8),
        ).pack(fill="x", pady=(0, 8))
        self.values["ai_objective"] = tk.StringVar()
        ai_entry = tk.Entry(
            ai, textvariable=self.values["ai_objective"],
            bg=ELITE["surface_alt"], fg=ELITE["text"],
            insertbackground=ELITE["orange"], relief="flat",
            font=("Segoe UI", 9),
        )
        ai_entry.pack(fill="x", ipady=5, pady=(0, 7))
        ai_entry.bind("<Return>", lambda _event: self._request_ai_answer())
        self.ai_ask_button = tk.Button(
            ai, text=self._t("ai.ask"), command=self._request_ai_answer,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=8, pady=7,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.ai_ask_button.pack(fill="x", pady=(0, 5))
        self.ai_plan_button = tk.Button(
            ai, text=self._t("ai.create_plan"), command=self._request_ai_plan,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=8, pady=7,
            font=("Segoe UI", 8, "bold"), cursor="hand2",
        )
        self.ai_plan_button.pack(fill="x", pady=(0, 9))
        self.values["ai_provider"] = tk.StringVar(value="—")
        tk.Label(
            ai, textvariable=self.values["ai_provider"], anchor="w",
            bg=ELITE["surface"], fg=ELITE["amber"], font=("Segoe UI", 8, "bold"),
        ).pack(fill="x", pady=(0, 5))
        self.values["ai_officers"] = tk.StringVar(value=self._t("ai.no_officers"))
        tk.Label(
            ai, textvariable=self.values["ai_officers"], anchor="w",
            bg=ELITE["surface"], fg=ELITE["muted"], font=("Segoe UI", 8),
        ).pack(fill="x", pady=(0, 6))
        self.values["ai_status"] = tk.StringVar(value=self._t("ai.no_plan"))
        tk.Label(
            ai, textvariable=self.values["ai_status"], anchor="nw", justify="left",
            wraplength=300, bg=ELITE["surface"], fg=ELITE["text"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(0, 8))
        self.values["ai_steps"] = tk.StringVar(value=self._t("ai.advisory"))
        tk.Label(
            ai, textvariable=self.values["ai_steps"], anchor="nw", justify="left",
            wraplength=300, bg=ELITE["surface"], fg=ELITE["text"],
            font=("Cascadia Mono", 9),
        ).pack(fill="x", pady=(0, 7))
        tk.Label(
            ai, text=self._t("ai.last_answer"), anchor="w",
            bg=ELITE["surface"], fg=ELITE["orange"],
            font=("Segoe UI", 9, "bold"),
        ).pack(fill="x", pady=(10, 4))
        self.values["ai_answer"] = tk.StringVar(value=self._t("ai.no_answer"))
        tk.Label(
            ai, textvariable=self.values["ai_answer"], anchor="nw", justify="left",
            wraplength=300, bg=ELITE["surface"], fg=ELITE["text"],
            font=("Segoe UI", 9),
        ).pack(fill="x", pady=(0, 7))

        # El estado de red se conserva para el panel de Configuración, pero ya
        # no ocupa una pestaña operativa propia.
        for key in ("eddn", "edsm", "inara"):
            self.values[key] = tk.StringVar(value="—")

    def _scrollable_tab(self, parent) -> tk.Frame:
        """Crea una pestaña con desplazamiento vertical y rueda del mouse."""
        canvas = tk.Canvas(
            parent, bg=ELITE["surface"], highlightthickness=0, borderwidth=0,
        )
        scrollbar = tk.Scrollbar(
            parent, orient="vertical", command=canvas.yview,
            bg=ELITE["surface_alt"], activebackground=ELITE["orange_soft"],
            troughcolor=ELITE["background"], relief="flat", width=12,
        )
        canvas.configure(yscrollcommand=scrollbar.set)
        scrollbar.pack(side="right", fill="y")
        canvas.pack(side="left", fill="both", expand=True)

        content = tk.Frame(canvas, bg=ELITE["surface"], padx=12, pady=8)
        window_id = canvas.create_window((0, 0), window=content, anchor="nw")
        content.bind(
            "<Configure>",
            lambda _event: canvas.configure(scrollregion=canvas.bbox("all")),
        )
        canvas.bind(
            "<Configure>",
            lambda event: canvas.itemconfigure(window_id, width=event.width),
        )

        def scroll(event) -> str:
            delta = -1 if event.delta > 0 else 1
            canvas.yview_scroll(delta, "units")
            return "break"

        def enable_wheel(_event) -> None:
            canvas.bind_all("<MouseWheel>", scroll)

        def disable_wheel(_event) -> None:
            canvas.unbind_all("<MouseWheel>")

        parent.bind("<Enter>", enable_wheel)
        parent.bind("<Leave>", disable_wheel)
        return content

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
        self.values["commander"].set(snapshot.get("commander", self._t("dashboard.commander")))
        self.values["system"].set(snapshot.get("system", self._t("dashboard.no_system")))
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
            text="CALCULANDO…" if calculating else self._t("heimdall.calculate_neutron"),
            state="disabled" if calculating else "normal",
        )
        self.exact_route_calculate_button.configure(
            text="CALCULANDO…" if calculating else self._t("heimdall.calculate_exact"),
            state="disabled" if calculating else "normal",
        )
        self.values["next_system"].set(route.get("next_system") or self._t("heimdall.no_route"))
        self.values["route_progress"].set(
            f"{route.get('remaining_jumps', 0)} de {route.get('total_jumps', 0)} saltos restantes"
            if route else "—"
        )
        self.values["destination"].set(route.get("destination") or "—")
        conventional = route.get("conventional", {})
        if route.get("strategy") == "galaxy_exact":
            self.values["route_comparison"].set(self._t("heimdall.exact_active"))
            if route.get("must_refuel"):
                refuel = self._t("heimdall.refuel_required")
            elif route.get("scoopable"):
                refuel = self._t("heimdall.scoop_available")
            else:
                refuel = self._t("heimdall.no_refuel_required")
            self.values["route_leg"].set(self._t(
                "heimdall.exact_leg",
                distance=float(route.get("leg_distance_ly", 0)),
                fuel=float(route.get("fuel_in_tank", 0)),
                used=float(route.get("fuel_used", 0)), refuel=refuel,
            ))
        elif conventional:
            saved = int(route.get("exact_jumps_saved", 0))
            self.values["route_comparison"].set(self._t(
                "heimdall.route_comparison_exact",
                conventional=conventional.get("total_jumps", 0),
                neutron=route.get("total_jumps", 0),
                saved=saved,
            ))
        else:
            self.values["route_comparison"].set(
                self._t("heimdall.route_comparison_waiting")
            )
        if route.get("strategy") != "galaxy_exact":
            self.values["route_leg"].set(self._t("common.no_data"))
        exact = snapshot.get("exact_plotter", {})
        self.values["exact_plotter"].set(
            self._t("heimdall.exact_ready") if exact.get("ready")
            else self._t("heimdall.exact_missing", count=len(exact.get("missing", ())))
        )
        high_energy = snapshot.get("high_energy", {})
        if high_energy.get("charged"):
            cone_state = self._t("heimdall.cone_state_charged")
        elif str(high_energy.get("target_class", "")).upper() == "N":
            cone_state = self._t("heimdall.cone_state_neutron")
        elif str(high_energy.get("target_class", "")).upper().startswith("D"):
            cone_state = self._t("heimdall.cone_state_white_dwarf")
        else:
            cone_state = self._t("heimdall.cone_state_idle")
        self.values["high_energy"].set(cone_state)
        fuel_capacity = float(snapshot.get("fuel_capacity", 0) or 0)
        self.values["fuel"].set(
            f"{float(snapshot.get('fuel', 0)):.1f} / {fuel_capacity:.1f} t"
            if fuel_capacity else self._t("common.no_data")
        )
        biology = snapshot.get("biology", {})
        self.values["biology"].set(
            self._t("dashboard.biology", species=biology.get("species", 0), bodies=biology.get("bodies", 0))
        )
        self.values["biology_details"].set(self._biology_details_text(biology))
        self.values["sampling_details"].set(self._sampling_details_text(biology))
        self.values["body"].set(snapshot.get("body") or "—")
        self.values["samples"].set(str(expedition.get("species", 0)))
        injections = snapshot.get("injections", {})
        self.values["injections"].set(
            f"{injections.get('basic', 0)} / {injections.get('standard', 0)} / {injections.get('premium', 0)}"
        )
        powerplay = snapshot.get("powerplay", {})
        self.values["powerplay_power"].set(powerplay.get("power") or self._t("common.no_data"))
        self.values["powerplay_rank"].set(str(powerplay.get("rank", 0)))
        self.values["powerplay_merits"].set(f"{int(powerplay.get('merits', 0)):,}")
        self.values["powerplay_earned"].set(f"+{int(powerplay.get('earned', 0)):,}")
        territory = " · ".join(filter(None, (
            powerplay.get("controlling_power"), powerplay.get("system_state"),
        )))
        self.values["powerplay_territory"].set(territory or self._t("common.no_data"))
        selected_activity = str(powerplay.get("selected", ""))
        activity = (
            self._t(f"powerplay.{selected_activity}")
            if selected_activity else self._t("powerplay.no_activity")
        )
        verification = powerplay.get("verification", "")
        if verification:
            verification = self._t(f"powerplay.verification.{verification}")
        self.values["powerplay_activity"].set(
            f"{activity} · {verification}" if verification else activity
        )
        objective = powerplay.get("error") or powerplay.get("objective") or "—"
        guidance = (
            self._t(f"powerplay.guidance.{selected_activity}")
            if selected_activity else ""
        )
        if guidance and not powerplay.get("error"):
            objective = f"{objective}\n\n{guidance}"
        if powerplay.get("source_warning"):
            objective = f"{objective}\n\n{powerplay['source_warning']}"
        if powerplay.get("calculating"):
            objective = self._t("powerplay.searching_combat")
        self.values["powerplay_objective"].set(objective)
        for button in self.powerplay_activity_buttons:
            button.configure(state="disabled" if powerplay.get("calculating") else "normal")
        locations = tuple(
            (item.get("system", ""), item.get("operation", ""),
             float(item.get("distance_ly", 0)), item.get("conflict", ""),
             item.get("body", ""), item.get("ring", ""),
             item.get("reserve_level", ""), int(item.get("hotspot_count", 0) or 0),
             item.get("station", ""), int(item.get("sell_price", 0) or 0),
             int(item.get("demand", 0) or 0),
             bool(item.get("contact_unverified", False)),
             float(item.get("distance_ls", 0) or 0),
             item.get("power_state", ""), item.get("instructions", ""))
            for item in powerplay.get("locations", ())
        )
        if locations != self._powerplay_location_signature:
            self._powerplay_location_signature = locations
            self.powerplay_location_systems = [item[0] for item in locations]
            self.powerplay_location_list.delete(0, "end")
            for (system, operation, distance, conflict, body, ring, reserve,
                 hotspots, station, sell_price, demand, contact_unverified,
                 distance_ls, category, instructions) in locations:
                suffix = f" · {conflict}" if conflict else ""
                if ring:
                    suffix += f" · {body} / {ring} · {reserve} · {hotspots} hotspot"
                if station:
                    suffix += f" · {station}"
                    if sell_price:
                        suffix += f" · {sell_price:,} CR · demanda {demand:,}"
                    elif distance_ls:
                        suffix += f" · {distance_ls:,.0f} ls"
                if category:
                    suffix += f" · {category}"
                if instructions:
                    concise = " ".join(str(instructions).split())
                    suffix += f" · {concise[:90]}{'…' if len(concise) > 90 else ''}"
                if contact_unverified:
                    suffix += f" · {self._t('powerplay.contact_unverified')}"
                operation_label = self._t(f"powerplay.operation.{operation}")
                self.powerplay_location_list.insert(
                    "end", f"{operation_label} · {system} · {distance:.1f} ly{suffix}"
                )
        trade = snapshot.get("trade", {})
        trade_calculating = bool(trade.get("calculating"))
        requested_strategy = trade.get("requested_strategy", "")
        self.trade_commodity_entry.configure(
            state="disabled" if trade_calculating else "normal"
        )
        self.powerplay_sale_button.configure(
            state="disabled" if trade_calculating else "normal"
        )
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
        self.values["trade_status"].set(
            trade.get("progress", self._t("freyja.no_route"))
        )
        self.values["trade_strategy"].set(
            trade.get("strategy", self._t("freyja.no_strategy"))
        )
        self.values["trade_commodity"].set(
            trade.get("commodity", self._t("common.none"))
        )
        self.values["trade_target"].set(
            trade.get("target", self._t("common.none"))
        )
        self.values["trade_units"].set(f"{int(trade.get('units', 0) or 0)} t")
        self.values["trade_profit"].set(
            self._credits(trade.get("estimated_profit", 0), True)
        )
        unit_price = int(trade.get("unit_price", 0) or 0)
        self.values["trade_unit_price"].set(
            self._credits(unit_price, True) if unit_price else self._t("common.none")
        )
        if not unit_price:
            self.values["trade_unit_price"].set(self._t("common.no_data"))
        distance_ly = float(trade.get("distance_ly", 0) or 0)
        self.values["trade_distance"].set(
            self._t("units.light_years", value=f"{distance_ly:.1f}")
            if distance_ly else self._t("common.none")
        )
        if not distance_ly:
            self.values["trade_distance"].set(self._t("common.no_data"))
        self.values["trade_powerplay_state"].set(
            trade.get("powerplay_state", self._t("common.none"))
        )
        self.values["trade_balance"].set(
            self._credits(trade.get("realized_profit", 0))
        )
        mining = snapshot.get("mining", {})
        status_labels = {
            "idle": self._t("dashboard.mining.idle"),
            "ready": self._t("dashboard.mining.ready"),
            "prospecting": self._t("dashboard.mining.prospecting"),
            "extracting": self._t("dashboard.mining.extracting"),
            "selling": self._t("dashboard.mining.selling"),
            "paused": self._t("dashboard.mining.paused"),
            "completed": self._t("dashboard.mining.completed"),
        }
        mining_status = status_labels.get(
            mining.get("status"), str(mining.get("status") or self._t("common.no_data"))
        )
        if mining.get("cargo_full"):
            mining_status = self._t("dashboard.mining.full")
        self.values["mining_status"].set(mining_status)
        self.values["mining_target"].set(
            mining.get("target", "") or self._t("brokk.no_target")
        )
        location = " · ".join(
            item for item in (mining.get("system", ""), mining.get("body", "")) if item
        )
        self.values["mining_location"].set(location or self._t("brokk.no_location"))
        technique_labels = {
            "laser": self._t("brokk.technique.laser"),
            "core": self._t("brokk.technique.core"),
            "subsurface": self._t("brokk.technique.subsurface"),
            "abrasion": self._t("brokk.technique.abrasion"),
            "surface": self._t("brokk.technique.surface"),
        }
        technique_text = technique_labels.get(
            mining.get("technique"), mining.get("technique") or "—"
        )
        if mining.get("technique_confirmed"):
            technique_text += f" · {self._t('brokk.journal_confirmed')}"
        elif mining.get("technique_source") == "commander":
            technique_text += f" · {self._t('brokk.commander_selected')}"
        self.values["mining_technique"].set(technique_text)
        environment = str(mining.get("environment", "space") or "space")
        self.values["mining_environment"].set(
            self._t(f"brokk.environment.{environment}")
        )
        vehicle = str(mining.get("surface_vehicle", "") or "")
        if vehicle and mining.get("surface_vehicle_active"):
            vehicle += f" · {self._t('network.active')}"
        self.values["mining_surface_vehicle"].set(
            vehicle or self._t("brokk.no_surface_vehicle")
        )
        geological = int(mining.get("geological_signals", 0) or 0)
        pending = int(mining.get("surface_event_count", 0) or 0)
        self.values["mining_geology"].set(
            self._t("brokk.geology_summary", signals=geological, pending=pending)
        )
        self.values["mining_prospected"].set(str(int(mining.get("prospected", 0) or 0)))
        cargo_count = int(mining.get("cargo_count", 0) or 0)
        capacity = int(mining.get("cargo_capacity", 0) or 0)
        limpets = int(mining.get("limpets", 0) or 0)
        self.values["mining_cargo"].set(
            (f"{cargo_count} / {capacity} t · {limpets} {self._t('brokk.limpets')}"
             if capacity else f"{cargo_count} t · {limpets} {self._t('brokk.limpets')}")
        )
        self.values["mining_revenue"].set(
            self._credits(mining.get("sale_revenue", 0))
        )
        produced = int(mining.get("produced_total", 0) or 0)
        hours = float(mining.get("duration_hours", 0) or 0)
        performance = mining.get("performance", {}) or {}
        valuation = mining.get("valuation", {}).get("best_permanent", {})
        valuation_calculating = bool(mining.get("valuation_calculating"))
        has_mined_cargo = bool(mining.get("sale_manifest", {}).get("cargo"))
        self.mining_sale_button.configure(
            text=(self._t("brokk.searching_sale") if valuation_calculating
                  else self._t("brokk.search_sale")),
            state=(
                "disabled" if valuation_calculating or not has_mined_cargo
                else "normal"
            ),
        )
        distance_options = mining.get("valuation", {}).get(
            "distance_options", {}
        )
        estimated_value = int(valuation.get("estimated_value", 0) or 0)
        if valuation:
            self.values["mining_sale_target"].set(
                f"{valuation.get('station', '—')} · {valuation.get('system', '—')}"
            )
            self.values["mining_sale_demand"].set(
                f"{int(valuation.get('demand', 0) or 0):,} t · "
                f"{valuation.get('risk', self._t('dashboard.unclassified'))}".replace(",", ".")
            )
            self.values["mining_sale_distance"].set(
                f"{float(valuation.get('distance_ly', 0) or 0):.2f} al · "
                f"{float(valuation.get('distance_ls', 0) or 0):.0f} ls"
            )
        else:
            self.values["mining_sale_target"].set(
                self._t("brokk.consulting_prices") if valuation_calculating
                else self._t("dashboard.sale_prompt")
                if has_mined_cargo else self._t("dashboard.no_mining_cargo")
            )
            self.values["mining_sale_demand"].set("—")
            self.values["mining_sale_distance"].set("—")
        if distance_options:
            labels = {"short": self._t("brokk.short"), "medium": self._t("brokk.medium"), "long": self._t("brokk.long")}
            self.values["mining_global_sale"].set(
                "\n".join(
                    f"{labels[key]} · {item.get('station', '—')} · "
                    f"{float(item.get('distance_ly', 0) or 0):.1f} al · "
                    f"≈ {self._credits(item.get('estimated_value', 0))}"
                    for key in ("short", "medium", "long")
                    if (item := distance_options.get(key))
                )
            )
        else:
            self.values["mining_global_sale"].set(
                self._t("dashboard.consulting") if valuation_calculating else self._t("dashboard.no_search")
            )
        if produced and hours > 0:
            tonnes_per_hour = float(
                performance.get("tonnes_per_hour", produced / hours) or 0
            )
            estimated_per_hour = int(
                performance.get("estimated_credits_per_hour", 0) or 0
            )
            realized_per_hour = int(
                performance.get("realized_credits_per_hour", 0) or 0
            )
            rate = (
                f"≈ {self._credits(estimated_per_hour)}/h"
                if estimated_per_hour else
                    self._t("brokk.confirmed_per_hour", value=self._credits(realized_per_hour))
            )
            self.values["mining_revenue"].set(
                f"{tonnes_per_hour:.1f} t/h · {rate} · "
                + (
                    self._t("brokk.estimated_cargo", value=self._credits(estimated_value))
                    if estimated_value else
                    self._t("brokk.sold_value", value=self._credits(mining.get('sale_revenue', 0)))
                )
            )
        self.values["mining_prospect_details"].set(
            self._mining_prospect_text(mining.get("last_prospect", {}), self.odin.config.language)
        )
        self.values["mining_refined_details"].set(
            self._mining_inventory_text(
                mining.get("refined", {}), self._t("brokk.no_refined"), "t"
            )
        )
        self.values["mining_material_details"].set(
            self._mining_inventory_text(
                mining.get("materials", {}), self._t("brokk.no_materials"), "u"
            )
        )
        self.values["mining_equipment_details"].set(
            self._mining_equipment_text(mining.get("equipment", {}), self.odin.config.language)
        )
        self._refresh_mining_search(mining.get("search", {}))
        self._refresh_guardian(snapshot.get("guardian", {}))
        self._refresh_engineering(snapshot.get("engineering", {}))
        self._refresh_ai(snapshot.get("ai", {}))
        network = snapshot.get("network", {})
        self.values["eddn"].set(self._t("network.active") if network.get("eddn") else self._t("network.inactive"))
        self.values["edsm"].set(self._t("network.active") if network.get("edsm") else self._t("network.inactive"))
        self.values["inara"].set(self._t("network.active") if network.get("inara") else self._t("network.waiting"))
        if not self._closing:
            self.root.after(250, self._refresh_state)

    def _refresh_guardian(self, guardian: dict) -> None:
        label = self.values["guardian_selection"].get()
        module_key = self.guardian_module_by_label.get(label, "fsd_booster")
        module = (guardian.get("modules", {}) or {}).get(module_key, {})
        requirements = module.get("requirements", ()) or ()
        if not requirements:
            self.values["guardian_status"].set(self._t("guardian.waiting"))
            self.values["guardian_requirements"].set(self._t("common.no_data"))
            self._set_guardian_copy_systems("", "")
            return
        missing_total = sum(int(item.get("missing", 0) or 0) for item in requirements)
        self.values["guardian_status"].set(
            self._t("guardian.ready")
            if module.get("complete") else
            self._t("guardian.missing_units", count=missing_total)
        )
        lines = []
        for item in requirements:
            available = int(item.get("available", 0) or 0)
            required = int(item.get("required", 0) or 0)
            missing = int(item.get("missing", 0) or 0)
            marker = "✓" if not missing else "○"
            detail = (self._t("guardian.complete") if not missing
                      else self._t("guardian.missing", count=missing))
            lines.append(
                f"{marker} {item.get('label', self._t('guardian.material'))}\n"
                f"   {available} / {required} · {detail}"
            )
        self.values["guardian_requirements"].set("\n\n".join(lines))
        calculating = bool(guardian.get("calculating"))
        self.guardian_search_button.configure(
            text=(self._t("brokk.searching") if calculating
                  else self._t("guardian.search")),
            state="disabled" if calculating else "normal",
        )
        plan = guardian.get("plan", {}) or {}
        if not self._guardian_selection_restored and plan.get("module_key"):
            restored = GUARDIAN_MODULE_RECIPES.get(plan["module_key"], {})
            restored_label = restored.get("label")
            if restored_label in self.guardian_module_by_label:
                self.values["guardian_selection"].set(restored_label)
                label = restored_label
                module_key = plan["module_key"]
                module = (guardian.get("modules", {}) or {}).get(module_key, {})
            self._guardian_selection_restored = True
        if plan.get("module_key") != module_key:
            self.values["guardian_collection"].set(
                self._t("guardian.run_search")
            )
            self.values["guardian_broker"].set(self._t("guardian.no_search"))
            self._set_guardian_copy_systems("", "")
            return
        if plan.get("error"):
            self.values["guardian_collection"].set(plan["error"])
            self.values["guardian_broker"].set(self._t("guardian.unavailable"))
            self._set_guardian_copy_systems("", "")
            return
        destinations = plan.get("collection", ()) or ()
        self.values["guardian_collection"].set(
            "\n\n".join(self._guardian_destination_text(item) for item in destinations)
            if destinations else self._t("guardian.no_pending")
        )
        broker = plan.get("broker", {}) or {}
        self.values["guardian_broker"].set(
            self._guardian_destination_text(broker)
            if broker else self._t("guardian.no_broker")
        )
        collection_system = str(destinations[0].get("system", "")).strip() if destinations else ""
        broker_system = str(broker.get("system", "")).strip() if broker else ""
        self._set_guardian_copy_systems(collection_system, broker_system)

    def _set_guardian_copy_systems(self, collection: str, broker: str) -> None:
        self._guardian_collection_system = collection
        self._guardian_broker_system = broker
        self.guardian_collection_copy_button.configure(
            state="normal" if collection else "disabled"
        )
        self.guardian_broker_copy_button.configure(
            state="normal" if broker else "disabled"
        )

    def _copy_guardian_system(self, destination: str) -> None:
        system = (
            self._guardian_collection_system
            if destination == "collection" else self._guardian_broker_system
        )
        if not system:
            return
        copy_text(system)
        print(f"GUARDIAN: {system} copiado al portapapeles.")

    def _refresh_engineering(self, engineering: dict) -> None:
        engineers = engineering.get("engineers", {}) or {}
        name = self.values["engineering_engineer"].get()
        engineer = engineers.get(name, ENGINEERS.get(name, {})) or {}
        status = str(engineer.get("status", "Unknown") or "Unknown")
        rank = int(engineer.get("rank", 0) or 0)
        rank_progress = int(engineer.get("rank_progress", 0) or 0)
        self._engineering_system = str(engineer.get("system", "") or "").strip()
        self.engineering_copy_button.configure(
            state="normal" if self._engineering_system else "disabled"
        )
        self.values["engineering_engineer_details"].set("\n".join((
            self._t("engineering.status", value=status),
            self._t("engineering.rank", rank=rank, progress=rank_progress),
            self._t("engineering.location", system=self._engineering_system or "—",
                    station=engineer.get("station", "—") or "—"),
            self._t("engineering.unlock", value=engineer.get("unlock", "—") or "—"),
            self._t("engineering.specialties", value=engineer.get("specialties", "—") or "—"),
        )))

        selected_key = str(engineering.get("selected_plan", "") or "")
        if not self._engineering_selection_restored and selected_key in ENGINEERING_PLANS:
            self.values["engineering_plan"].set(ENGINEERING_PLANS[selected_key]["label"])
            self._engineering_selection_restored = True
        plan_key = self.engineering_plan_by_label.get(
            self.values["engineering_plan"].get(), selected_key
        )
        plan = (engineering.get("plans", {}) or {}).get(plan_key, {}) or {}
        requirements = plan.get("requirements", ()) or ()
        missing_total = sum(int(item.get("missing", 0) or 0) for item in requirements)
        self.values["engineering_plan_status"].set(
            self._t("engineering.ready") if requirements and not missing_total
            else self._t("engineering.missing", count=missing_total)
            if requirements else self._t("engineering.no_plan")
        )
        plan_lines = []
        if plan:
            plan_lines.extend((
                f"{plan.get('engineer', '—')}",
                f"{plan.get('blueprint', '—')} · G{int(plan.get('grade', 0) or 0)}",
                "",
            ))
        for item in requirements:
            marker = "✓" if not int(item.get("missing", 0) or 0) else "○"
            plan_lines.append(
                f"{marker} {item.get('label', item.get('material', '—'))}: "
                f"{int(item.get('available', 0) or 0)} / {int(item.get('required', 0) or 0)}"
            )
        self.values["engineering_requirements"].set(
            "\n".join(plan_lines).strip() or self._t("common.no_data")
        )

        module_lines = []
        for module in engineering.get("modules", ()) or ():
            effect = str(module.get("experimental", "") or "").strip()
            line = (f"{module.get('slot', '—')}\n"
                    f"  {module.get('blueprint', '—')} · G{int(module.get('grade', 0) or 0)}")
            if effect:
                line += f" · {effect}"
            module_lines.append(line)
        self.values["engineering_modules"].set(
            "\n\n".join(module_lines) if module_lines else self._t("engineering.no_modules")
        )

    def _save_engineering_plan(self) -> None:
        plan_key = self.engineering_plan_by_label.get(
            self.values["engineering_plan"].get(), ""
        )
        if self.odin.select_engineering_plan(plan_key):
            self._engineering_selection_restored = True
            self._refresh_engineering(
                getattr(self.odin, "dashboard_snapshot", {}).get("engineering", {})
            )
            print(f"ODIN: {self._t('engineering.plan_saved')}")

    def _copy_engineering_system(self) -> None:
        if self._engineering_system:
            copy_text(self._engineering_system)
            print(f"ODIN: {self._engineering_system} copiado al portapapeles.")

    def _request_ai_plan(self) -> None:
        objective = self.values["ai_objective"].get().strip()
        if not objective:
            messagebox.showwarning(
                "ODIN IA", self._t("ai.objective_required"), parent=self.root
            )
            return
        if not self.odin.request_ai_plan(objective):
            messagebox.showinfo(
                "ODIN IA", self._t("ai.already_working"), parent=self.root
            )

    def _request_ai_answer(self) -> None:
        question = self.values["ai_objective"].get().strip()
        if not question:
            messagebox.showwarning(
                "ODIN IA", self._t("ai.question_required"), parent=self.root
            )
            return
        if not self.odin.request_ai_answer(question):
            messagebox.showinfo(
                "ODIN IA", self._t("ai.answer_busy"), parent=self.root
            )

    def _refresh_ai(self, ai: dict) -> None:
        provider = str(ai.get("provider", "—") or "—")
        model = str(ai.get("model", "") or "")
        self.values["ai_provider"].set(
            self._t("ai.provider", provider=provider, model=model)
        )
        officers = tuple(ai.get("consulted_officers", ()) or ())
        self.values["ai_officers"].set(
            self._t("ai.officers", names=", ".join(officers))
            if officers else self._t("ai.no_officers")
        )
        calculating = bool(ai.get("calculating"))
        self.ai_plan_button.configure(
            text=self._t("ai.thinking") if calculating else self._t("ai.create_plan"),
            state="disabled" if calculating else "normal",
        )
        error = str(ai.get("error", "") or "").strip()
        self.values["ai_status"].set(
            self._t("ai.error", value=error) if error
            else str(ai.get("summary", "") or self._t("ai.no_plan"))
        )
        lines = []
        for index, step in enumerate(ai.get("steps", ()) or (), 1):
            authorization = (
                f" · {self._t('ai.authorization')}"
                if step.get("requires_authorization") else ""
            )
            lines.append(
                f"{index}. {step.get('officer', 'ODIN')} · "
                f"{str(step.get('action', '')).replace('_', ' ')}{authorization}\n"
                f"   {step.get('reason', '')}"
            )
        self.values["ai_steps"].set(
            "\n\n".join(lines) if lines else self._t("ai.advisory")
        )
        conversation = ai.get("conversation", {}) or {}
        answering = bool(conversation.get("calculating"))
        self.ai_ask_button.configure(
            text=self._t("ai.answering") if answering else self._t("ai.ask"),
            state="disabled" if answering else "normal",
        )
        conversation_error = str(conversation.get("error", "") or "").strip()
        answer = str(conversation.get("answer", "") or "").strip()
        self.values["ai_answer"].set(
            self._t("ai.error", value=conversation_error) if conversation_error
            else answer or self._t("ai.no_answer")
        )

    @staticmethod
    def _guardian_destination_text(destination: dict) -> str:
        stock = int(destination.get("stock", 0) or 0)
        stock_text = f" · stock {stock}" if stock else ""
        return (
            f"{destination.get('purpose', '')}\n"
            f"{destination.get('system', '—')} · {destination.get('location', '—')}\n"
            f"{float(destination.get('distance_ly', 0) or 0):.1f} al"
            f"{stock_text} · {destination.get('provider', 'Spansh')}"
        ).strip()

    def _request_guardian_search(self) -> None:
        label = self.values["guardian_selection"].get()
        module_key = self.guardian_module_by_label.get(label, "")
        if not module_key or not self.odin.request_guardian_search(module_key):
            messagebox.showinfo(
                "GUARDIAN",
                self._t("guardian.search_failed"),
                parent=self.root,
            )

    def _copy_next_system(self) -> None:
        system = self.values["next_system"].get().strip()
        if system and system != self._t("heimdall.no_route"):
            copy_text(system)

    def _request_neutron_route(self) -> None:
        destination = self.values["route_destination_input"].get().strip()
        if not destination:
            messagebox.showwarning(
                "HEIMDALL", self._t("dialog.route_destination"), parent=self.root
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

    def _request_exact_route(self) -> None:
        destination = self.values["route_destination_input"].get().strip()
        accepted, detail = self.odin.request_exact_route(destination)
        if accepted:
            self.exact_route_calculate_button.configure(
                text="SOLICITADO", state="disabled"
            )
            print(f"HEIMDALL: solicitud de ruta exacta recibida hacia {destination}.")
            return
        messagebox.showinfo("HEIMDALL", detail, parent=self.root)

    def _request_trade(self, strategy: str) -> None:
        labels = {
            "quick": "ruta rápida", "three_station": "tres estaciones",
            "expedition": "expedición comercial", "powerplay": "Powerplay",
        }
        commodity = self.values["trade_commodity_input"].get().strip()
        allow_planetary = bool(self.values["trade_allow_planetary"].get())
        if self.odin.request_trade_calculation(
            strategy, commodity, allow_planetary=allow_planetary
        ):
            product = f" para {commodity}" if commodity else ""
            print(
                f"FREYJA: modalidad {labels[strategy]}{product} "
                "solicitada desde la interfaz."
            )
            for button in self.trade_buttons:
                button.configure(state="disabled")
            return
        messagebox.showinfo(
            "FREYJA",
            self._t("dialog.trade_busy"),
            parent=self.root,
        )

    def _request_powerplay_activity(self, activity: str) -> None:
        accepted, detail = self.odin.request_powerplay_activity(
            activity, self.powerplay_subject.get()
        )
        if accepted:
            print(f"POWERPLAY: {detail}")
            return
        messagebox.showinfo("POWERPLAY", detail, parent=self.root)

    def _open_powerplay_weekly_guide(self) -> None:
        """Abre una referencia independiente sin capturar la pantalla del juego."""

        window = tk.Toplevel(self.root)
        window.title(self._t("powerplay.weekly_guide_title"))
        window.configure(bg=ELITE["background"])
        window.geometry("720x620")
        window.minsize(520, 420)
        container = tk.Frame(window, bg=ELITE["background"])
        container.pack(fill="both", expand=True, padx=12, pady=12)
        scrollbar = ttk.Scrollbar(container, orient="vertical")
        guide = tk.Text(
            container, wrap="word", yscrollcommand=scrollbar.set,
            bg=ELITE["surface"], fg=ELITE["text"], insertbackground=ELITE["orange"],
            relief="flat", padx=14, pady=12, font=("Segoe UI", 10),
        )
        scrollbar.configure(command=guide.yview)
        scrollbar.pack(side="right", fill="y")
        guide.pack(side="left", fill="both", expand=True)
        guide.insert("end", self._t("powerplay.weekly_guide_intro") + "\n\n")
        for activity, steps in self.odin.powerplay_weekly_guide():
            guide.insert("end", self._t(f"powerplay.{activity}") + "\n")
            for index, step in enumerate(steps, 1):
                guide.insert("end", f"  {index}. {step}\n")
            guide.insert("end", "\n")
        guide.configure(state="disabled")

    def _selected_powerplay_system(self) -> str:
        selection = self.powerplay_location_list.curselection()
        if not selection:
            return ""
        index = int(selection[0])
        return self.powerplay_location_systems[index]

    def _copy_powerplay_location(self) -> None:
        system = self._selected_powerplay_system()
        if system:
            copy_text(system)
            print(f"POWERPLAY: {system} copiado al portapapeles.")

    def _powerplay_location_to_heimdall(self) -> None:
        system = self._selected_powerplay_system()
        if not system:
            return
        self.values["route_destination_input"].set(system)
        print(f"POWERPLAY: {system} preparado como destino de HEIMDALL.")

    def _request_powerplay_sale(self) -> None:
        commodity = self.values["trade_commodity_input"].get().strip()
        if not commodity:
            messagebox.showwarning(
                "FREYJA", self._t("dialog.trade_product"),
                parent=self.root,
            )
            return
        if self.odin.request_powerplay_sale_search(
            commodity,
            allow_planetary=bool(self.values["trade_allow_planetary"].get()),
        ):
            self.powerplay_sale_button.configure(state="disabled")
            print(
                f"FREYJA: búsqueda de venta Powerplay solicitada para {commodity}."
            )
            return
        messagebox.showinfo(
            "FREYJA", self._t("dialog.trade_busy"),
            parent=self.root,
        )

    def _control_mining(self, action: str) -> None:
        target = self.values["mining_target_input"].get().strip()
        technique_by_label = {
            self._t("brokk.technique.laser"): "laser",
            self._t("brokk.technique.abrasion"): "abrasion",
            self._t("brokk.technique.subsurface"): "subsurface",
            self._t("brokk.technique.core"): "core",
        }
        technique = technique_by_label.get(
            self.values["mining_technique_input"].get(), "laser"
        )
        message = self.odin.control_mining_session(action, target, technique)
        print(f"BROKK: {message}")

    def _request_mining_search(self) -> None:
        mineral = self.values["mining_target_input"].get().strip()
        if not mineral:
            messagebox.showwarning(
                "BROKK", self._t("dialog.mining_target"), parent=self.root
            )
            return
        if self.odin.request_mining_search(mineral):
            print(f"BROKK: buscando zonas conocidas para {mineral}.")

    def _request_mining_sale_search(self) -> None:
        if self.odin.request_mining_sale_search():
            print("BROKK: búsqueda de venta solicitada por el comandante.")
            return
        messagebox.showinfo(
            "BROKK",
            self._t("dialog.mining_busy"),
            parent=self.root,
        )

    def _refresh_mining_search(self, search: dict) -> None:
        calculating = bool(search.get("calculating"))
        self.mining_search_button.configure(
            text=(self._t("brokk.searching") if calculating
                  else self._t("brokk.search_mine")),
            state="disabled" if calculating else "normal",
        )
        self.values["mining_search_status"].set(
            search.get("error") or search.get("status")
            or self._t("brokk.search_hint")
        )
        labels = {
            "short": self._t("brokk.short"),
            "medium": self._t("brokk.medium"),
            "long": self._t("brokk.long"),
        }
        options = search.get("options", {}) or {}
        for tier, label in labels.items():
            option = options.get(tier, {}) or {}
            system = str(option.get("system", ""))
            if option:
                self.values[f"mining_search_{tier}"].set(
                    f"{label} · {system}\n{option.get('ring', option.get('body', '—'))}\n"
                    f"{float(option.get('distance_ly', 0) or 0):.1f} al · "
                    f"{option.get('reserve_level', 'reservas desconocidas')} · "
                    f"{int(option.get('hotspot_count', 0) or 0)} hotspot"
                )
            else:
                self.values[f"mining_search_{tier}"].set(
                    f"{label} · {self._t('brokk.no_result')}"
                )
            copy_button, route_button, _old = self.mining_search_rows[tier]
            state = "normal" if system else "disabled"
            copy_button.configure(state=state)
            route_button.configure(state=state)
            self.mining_search_rows[tier] = (copy_button, route_button, system)

    def _copy_mining_system(self, tier: str) -> None:
        system = self.mining_search_rows.get(tier, (None, None, ""))[2]
        if system:
            copy_text(system)
            print(f"BROKK: {system} copiado al portapapeles.")

    def _route_mining_system(self, tier: str) -> None:
        if self.odin.select_mining_destination(tier):
            print("BROKK: destino entregado a HEIMDALL.")

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

    def _open_voice_commands(self) -> None:
        window = tk.Toplevel(self.root)
        window.title(self._t("voice_commands.title"))
        available_height = max(480, window.winfo_screenheight() - 120)
        window.geometry(f"760x{min(720, available_height)}")
        window.minsize(560, min(480, available_height))
        window.configure(bg=ELITE["background"])
        window.transient(self.root)

        container = tk.Frame(window, bg=ELITE["background"], padx=18, pady=14)
        container.pack(fill="both", expand=True)
        tk.Label(
            container, text=self._t("voice_commands.heading"),
            bg=ELITE["background"], fg=ELITE["orange"],
            font=("Segoe UI", 14, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            container, text=self._t("voice_commands.hint"),
            bg=ELITE["background"], fg=ELITE["muted"],
            font=("Segoe UI", 9), justify="left", anchor="w", wraplength=700,
        ).pack(fill="x", pady=(4, 12))

        query = tk.StringVar()
        search = tk.Entry(
            container, textvariable=query, bg=ELITE["surface_alt"],
            fg=ELITE["text"], insertbackground=ELITE["orange"],
            relief="flat", font=("Segoe UI", 10),
        )
        search.pack(fill="x", ipady=7, pady=(0, 10))

        body = tk.Frame(container, bg=ELITE["surface"])
        body.pack(fill="both", expand=True)
        scrollbar = tk.Scrollbar(body, orient="vertical")
        command_list = tk.Text(
            body, yscrollcommand=scrollbar.set, bg=ELITE["surface"],
            fg=ELITE["text"], selectbackground="#6f3e12",
            selectforeground="#ffffff", relief="flat", wrap="word",
            padx=14, pady=10, font=("Segoe UI", 10), cursor="arrow",
        )
        scrollbar.configure(command=command_list.yview)
        scrollbar.pack(side="right", fill="y")
        command_list.pack(side="left", fill="both", expand=True)
        command_list.tag_configure(
            "heading", foreground=ELITE["orange"],
            font=("Segoe UI", 11, "bold"), spacing1=8, spacing3=4,
        )
        command_list.tag_configure(
            "command", foreground=ELITE["text"], lmargin1=8, lmargin2=24,
            spacing1=2, spacing3=2,
        )
        command_list.tag_configure(
            "empty", foreground=ELITE["muted"], justify="center", spacing1=20,
        )

        catalog = voice_command_catalog(self.odin.config.language)

        def render(*_args) -> None:
            needle = query.get().strip().casefold()
            command_list.configure(state="normal")
            command_list.delete("1.0", "end")
            matches = 0
            for heading, commands in catalog:
                visible = tuple(
                    command for command in commands
                    if not needle
                    or needle in heading.casefold()
                    or needle in command.casefold()
                )
                if not visible:
                    continue
                matches += len(visible)
                command_list.insert("end", f"{heading}\n", "heading")
                for command in visible:
                    command_list.insert("end", f"◆  {command}\n", "command")
                command_list.insert("end", "\n")
            if not matches:
                command_list.insert(
                    "end", self._t("voice_commands.no_results"), "empty"
                )
            command_list.configure(state="disabled")
            command_list.yview_moveto(0)

        query.trace_add("write", render)
        render()
        search.focus_set()

    def _open_settings(self) -> None:
        window = tk.Toplevel(self.root)
        window.title(self._t("settings.title"))
        available_height = max(460, window.winfo_screenheight() - 100)
        window.geometry(f"620x{min(650, available_height)}")
        window.minsize(540, min(460, available_height))
        window.resizable(True, True)
        window.configure(bg=ELITE["background"])
        window.transient(self.root)
        window.grab_set()

        container = tk.Frame(window, bg=ELITE["background"], padx=18, pady=14)
        container.pack(fill="both", expand=True)
        tk.Label(
            container, text=self._t("settings.heading"),
            bg=ELITE["background"], fg=ELITE["orange"],
            font=("Segoe UI", 14, "bold"), anchor="w",
        ).pack(fill="x", pady=(0, 12))

        # Se reserva primero el pie: así Aceptar/Cancelar nunca quedan fuera
        # de pantalla aunque Windows use escalado alto o poca altura útil.
        actions = tk.Frame(container, bg=ELITE["background"])
        actions.pack(side="bottom", fill="x", pady=(12, 0))

        notebook = ttk.Notebook(container, style="Odin.TNotebook")
        notebook.pack(fill="both", expand=True)
        general_page = tk.Frame(notebook, bg=ELITE["surface"])
        credentials_page = tk.Frame(notebook, bg=ELITE["surface"])
        heimdall_page = tk.Frame(notebook, bg=ELITE["surface"])
        notebook.add(general_page, text=self._t("settings.general_tab"))
        notebook.add(credentials_page, text=self._t("settings.credentials_tab"))
        notebook.add(heimdall_page, text=public_officer_name("HEIMDALL"))
        general_tab = self._scrollable_tab(general_page)
        credentials_tab = self._scrollable_tab(credentials_page)
        heimdall_tab = self._scrollable_tab(heimdall_page)

        docking = self._settings_section(
            heimdall_tab, self._t("settings.docking")
        )
        auto_docking = tk.BooleanVar(
            value=self.odin.config.heimdall_auto_docking_enabled
        )
        tk.Checkbutton(
            docking,
            text=self._t("settings.docking_enable"),
            variable=auto_docking, anchor="w", bg=ELITE["surface"],
            fg=ELITE["text"], selectcolor=ELITE["surface_alt"],
            activebackground=ELITE["surface"], activeforeground=ELITE["orange"],
            font=("Segoe UI", 10),
        ).pack(fill="x", pady=3)
        tk.Label(
            docking,
            text=self._t("settings.docking_help"),
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="w",
            justify="left", wraplength=510, font=("Segoe UI", 9),
        ).pack(fill="x", pady=(5, 0))

        network = self._settings_section(general_tab, self._t("settings.network"))
        network_vars = {}
        for key, label, enabled in (
            ("eddn", self._t("settings.eddn"), self.odin.config.eddn_upload_enabled),
            ("edsm", self._t("settings.edsm"), self.odin.config.edsm_upload_enabled),
            ("inara", self._t("settings.inara"), self.odin.config.inara_upload_enabled),
        ):
            variable = tk.BooleanVar(value=enabled)
            network_vars[key] = variable
            row = tk.Frame(network, bg=ELITE["surface"])
            row.pack(fill="x", pady=3)
            tk.Checkbutton(
                row, text=label, variable=variable, anchor="w",
                bg=ELITE["surface"], fg=ELITE["text"], selectcolor=ELITE["surface_alt"],
                activebackground=ELITE["surface"], activeforeground=ELITE["orange"],
                font=("Segoe UI", 10),
            ).pack(side="left", fill="x", expand=True)
            tk.Label(
                row, textvariable=self.values[key], bg=ELITE["surface"],
                fg=ELITE["green"], font=("Segoe UI", 8, "bold"),
            ).pack(side="right")
        tk.Label(
            network, text=self._t("settings.network_restart"),
            bg=ELITE["surface"], fg=ELITE["muted"], font=("Segoe UI", 8),
            anchor="w",
        ).pack(fill="x", pady=(5, 0))

        canonn = self._settings_section(
            general_tab, self._t("canonn.section")
        )
        canonn_source = tk.StringVar(value=self.odin.config.canonn_poi_source)
        canonn_status = tk.StringVar(
            value=(
                self._t("canonn.updated", count=len(self.odin.canonn_poi_catalog.items))
                if self.odin.canonn_poi_catalog.items else self._t("common.no_data")
            )
        )
        tk.Label(
            canonn, text=self._t("canonn.source"), bg=ELITE["surface"],
            fg=ELITE["muted"], anchor="w", font=("Segoe UI", 9),
        ).pack(fill="x", pady=(0, 3))
        tk.Entry(
            canonn, textvariable=canonn_source, bg=ELITE["surface_alt"],
            fg=ELITE["text"], insertbackground=ELITE["orange"],
            relief="flat", font=("Segoe UI", 9),
        ).pack(fill="x", ipady=5)
        canonn_update = tk.Button(
            canonn, text=self._t("canonn.update"), bg=ELITE["surface_alt"],
            fg=ELITE["amber"], relief="flat", font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=8, pady=6,
        )
        canonn_update.pack(fill="x", pady=(6, 3))
        tk.Label(
            canonn, textvariable=canonn_status, bg=ELITE["surface"],
            fg=ELITE["green"], anchor="w", font=("Segoe UI", 8, "bold"),
        ).pack(fill="x")
        tk.Label(
            canonn, text=self._t("canonn.help"), bg=ELITE["surface"],
            fg=ELITE["muted"], anchor="w", justify="left", wraplength=510,
            font=("Segoe UI", 8),
        ).pack(fill="x", pady=(3, 0))

        def refresh_canonn() -> None:
            source = canonn_source.get().strip()
            if not source:
                canonn_status.set(self._t("canonn.source_required"))
                return
            canonn_update.configure(state="disabled")
            canonn_status.set(self._t("canonn.updating"))

            def worker() -> None:
                success, detail = self.odin.refresh_canonn_poi(source)
                def finish() -> None:
                    if not window.winfo_exists():
                        return
                    canonn_update.configure(state="normal")
                    canonn_status.set(detail)
                    if success:
                        self.odin.config.update_preferences(canonn_poi_source=source)
                self.root.after(0, finish)

            threading.Thread(
                target=worker, name="odin-canonn-refresh", daemon=True
            ).start()

        canonn_update.configure(command=refresh_canonn)

        credentials = self._settings_section(
            credentials_tab, self._t("settings.credentials")
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
        openai_key = tk.StringVar()
        ai_provider = tk.StringVar(value=self.odin.config.ai_provider)
        openai_model = tk.StringVar(value=self.odin.config.openai_model)
        ai_share_trade_data = tk.BooleanVar(
            value=self.odin.config.ai_share_trade_data
        )
        ai_share_mining_data = tk.BooleanVar(
            value=self.odin.config.ai_share_mining_data
        )
        ai_share_navigation_data = tk.BooleanVar(
            value=self.odin.config.ai_share_navigation_data
        )
        ai_share_science_data = tk.BooleanVar(
            value=self.odin.config.ai_share_science_data
        )
        ai_share_progression_data = tk.BooleanVar(
            value=self.odin.config.ai_share_progression_data
        )
        ai_share_powerplay_data = tk.BooleanVar(
            value=self.odin.config.ai_share_powerplay_data
        )
        ai_share_commander_data = tk.BooleanVar(
            value=self.odin.config.ai_share_commander_data
        )
        ai_share_station_search_data = tk.BooleanVar(
            value=self.odin.config.ai_share_station_search_data
        )
        installed = {
            "elevenlabs": create_secret_store(ELEVENLABS_TARGET).exists(),
            "edsm": EDSMCredentialStore().exists(),
            "inara": InaraCredentialStore().exists(),
            "openai": OpenAICredentialStore().exists(),
        }
        credential_rows = [
            (self._t("settings.commander"), commander, False, False, ""),
            (self._t("settings.frontier_id"), frontier_id, False, True, ""),
            ("ElevenLabs API key", eleven_key, True, False, "elevenlabs"),
            ("EDSM API key", edsm_key, True, False, "edsm"),
            ("Inara API key", inara_key, True, False, "inara"),
        ]
        if not self.odin.config.public_beta_no_ai:
            credential_rows.append(
                ("OpenAI API key", openai_key, True, False, "openai")
            )
        for label, variable, secret, readonly, service in credential_rows:
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
                    text=(self._t("settings.configured") if configured
                          else self._t("settings.not_configured")),
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
            text=self._t("settings.secret_help"),
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="w",
            font=("Segoe UI", 8), wraplength=510, justify="left",
        ).pack(fill="x", pady=(8, 0))

        ai_credentials_parent = (
            credentials if not self.odin.config.public_beta_no_ai
            else tk.Frame(window, bg=ELITE["surface"])
        )
        ai_row = tk.Frame(ai_credentials_parent, bg=ELITE["surface"])
        if not self.odin.config.public_beta_no_ai:
            ai_row.pack(fill="x", pady=(10, 0))
        tk.Label(ai_row, text=self._t("settings.ai_provider"), bg=ELITE["surface"],
                 fg=ELITE["muted"], font=("Segoe UI", 9)).pack(side="left")
        ttk.Combobox(
            ai_row, textvariable=ai_provider, state="readonly", width=13,
            values=("automatic", "openai", "ollama"),
        ).pack(side="right")
        model_row = tk.Frame(credentials, bg=ELITE["surface"])
        model_row.pack(fill="x", pady=(8, 0))
        tk.Label(model_row, text=self._t("settings.openai_model"), bg=ELITE["surface"],
                 fg=ELITE["muted"], font=("Segoe UI", 9)).pack(side="left")
        tk.Entry(model_row, textvariable=openai_model, width=22,
                 bg=ELITE["surface_alt"], fg=ELITE["text"], relief="flat").pack(side="right", ipady=3)
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_trade_data"),
            variable=ai_share_trade_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(8, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_mining_data"),
            variable=ai_share_mining_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_navigation_data"),
            variable=ai_share_navigation_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_science_data"),
            variable=ai_share_science_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_progression_data"),
            variable=ai_share_progression_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_powerplay_data"),
            variable=ai_share_powerplay_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_commander_data"),
            variable=ai_share_commander_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))
        tk.Checkbutton(
            ai_credentials_parent, text=self._t("settings.ai_share_station_search_data"),
            variable=ai_share_station_search_data, bg=ELITE["surface"], fg=ELITE["text"],
            selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
            activeforeground=ELITE["orange"], anchor="w", justify="left",
            wraplength=500, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))

        bindings = self._settings_section(
            general_tab, self._t("settings.bindings_backup")
        )
        snapshots = self.odin.binding_custodian.list_snapshots()
        snapshot_by_label = {path.name: path for path in snapshots}
        selected_snapshot = tk.StringVar(
            value=next(iter(snapshot_by_label), self._t("settings.no_snapshots"))
        )
        bindings_row = tk.Frame(bindings, bg=ELITE["surface"])
        bindings_row.pack(fill="x")
        ttk.Combobox(
            bindings_row, textvariable=selected_snapshot, state="readonly",
            values=tuple(snapshot_by_label) or (self._t("settings.no_snapshots"),),
            width=30,
        ).pack(side="left", fill="x", expand=True)
        tk.Button(
            bindings_row, text=self._t("settings.restore_bindings"),
            command=lambda: self._restore_binding_snapshot(
                snapshot_by_label.get(selected_snapshot.get()), window
            ),
            bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
            activebackground=ELITE["border"], font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=8, pady=6,
        ).pack(side="right", padx=(6, 0))
        tk.Label(
            bindings, text=self._t("settings.bindings_restore_help"),
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="w",
            justify="left", wraplength=510, font=("Segoe UI", 8),
        ).pack(fill="x", pady=(5, 0))

        sound = self._settings_section(general_tab, self._t("settings.voice"))
        voice_settings = self.voice_repository.load()
        language_by_label = {
            label: code for code, label in SUPPORTED_LANGUAGES.items()
        }
        language_label = tk.StringVar(
            value=SUPPORTED_LANGUAGES[self.odin.config.language]
        )
        language_row = tk.Frame(sound, bg=ELITE["surface"])
        language_row.pack(fill="x", pady=(0, 8))
        tk.Label(
            language_row,
            text=localized_text("settings.language", self.odin.config.language),
            bg=ELITE["surface"], fg=ELITE["muted"], font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        ttk.Combobox(
            language_row, textvariable=language_label, state="readonly", width=27,
            values=tuple(SUPPORTED_LANGUAGES.values()),
        ).pack(side="right")
        tk.Label(
            sound,
            text=localized_text(
                "settings.language_restart", self.odin.config.language
            ),
            bg=ELITE["surface"], fg=ELITE["muted"], anchor="w",
            font=("Segoe UI", 8),
        ).pack(fill="x", pady=(0, 8))
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
        recognition_labels = {
            self._t("settings.recognition_auto"): "auto",
            self._t("settings.recognition_parakeet"): "parakeet",
            self._t("settings.recognition_whisper"): "whisper",
        }
        recognition_by_provider = {
            provider: label for label, provider in recognition_labels.items()
        }
        recognition = tk.StringVar(value=recognition_by_provider.get(
            self.odin.config.speech_recognition_provider,
            self._t("settings.recognition_auto"),
        ))
        recognition_row = tk.Frame(sound, bg=ELITE["surface"])
        recognition_row.pack(fill="x", pady=(8, 0))
        tk.Label(
            recognition_row, text=self._t("settings.recognition"),
            bg=ELITE["surface"], fg=ELITE["muted"],
            font=("Segoe UI", 8, "bold"),
        ).pack(side="left")
        ttk.Combobox(
            recognition_row, textvariable=recognition, state="readonly", width=27,
            values=tuple(recognition_labels),
        ).pack(side="right")
        current_mode = (
            "both" if self.odin.config.push_to_talk_enabled and self.odin.config.wake_word_enabled
            else "ptt" if self.odin.config.push_to_talk_enabled else "wake"
        )
        voice_mode = tk.StringVar(value=current_mode)
        tk.Label(
            sound, text=self._t("settings.activation"), bg=ELITE["surface"],
            fg=ELITE["muted"], anchor="w", font=("Segoe UI", 8, "bold"),
        ).pack(fill="x", pady=(8, 2))
        modes = tk.Frame(sound, bg=ELITE["surface"])
        modes.pack(fill="x")
        for value, label in (
            ("ptt", self._t("settings.ptt")),
            ("wake", self._t("settings.wake")),
            ("both", self._t("settings.both")),
        ):
            tk.Radiobutton(
                modes, text=label, variable=voice_mode, value=value,
                bg=ELITE["surface"], fg=ELITE["text"],
                selectcolor=ELITE["surface_alt"], activebackground=ELITE["surface"],
                activeforeground=ELITE["orange"], font=("Segoe UI", 9),
            ).pack(side="left", padx=(0, 10))

        calibration_status = tk.StringVar()
        calibration_row = tk.Frame(sound, bg=ELITE["surface"])
        calibration_row.pack(fill="x", pady=(12, 0))

        def commander_key() -> str:
            return str(
                frontier_id.get().strip() or commander.get().strip()
            )

        def refresh_calibration_status() -> None:
            key = commander_key()
            if not key:
                calibration_status.set(self._t("settings.no_commander"))
                return
            status = self.voice_calibration.status(key)
            count = int(status.get("sample_count", 0) or 0)
            calibration_status.set(
                self._t("settings.profile_count", count=count)
                if status.get("consented") else self._t("settings.no_profile")
            )

        tk.Button(
            calibration_row, text=self._t("settings.calibrate"),
            command=lambda: self._open_voice_calibration(
                commander_key(), window, refresh_calibration_status
            ),
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=8, pady=6,
        ).pack(side="left")
        tk.Button(
            calibration_row, text=self._t("settings.delete_profile"),
            command=lambda: self._delete_voice_calibration(
                commander_key(), window, refresh_calibration_status
            ),
            bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
            activebackground=ELITE["border"], font=("Segoe UI", 8, "bold"),
            cursor="hand2", padx=8, pady=6,
        ).pack(side="left", padx=6)
        tk.Label(
            sound, textvariable=calibration_status, bg=ELITE["surface"],
            fg=ELITE["muted"], anchor="w", font=("Segoe UI", 8),
        ).pack(fill="x", pady=(4, 0))
        refresh_calibration_status()

        def save() -> None:
            name = commander.get().strip()
            selected_language = language_by_label.get(
                language_label.get(), self.odin.config.language
            )
            language_changed = selected_language != self.odin.config.language
            if (edsm_key.get().strip() or inara_key.get().strip()) and not name:
                messagebox.showerror("ODIN", self._t("dialog.commander_required"), parent=window)
                return
            try:
                if eleven_key.get().strip():
                    create_secret_store(ELEVENLABS_TARGET).set(eleven_key.get().strip())
                if edsm_key.get().strip():
                    EDSMCredentialStore().set(name, edsm_key.get().strip())
                if inara_key.get().strip():
                    InaraCredentialStore().set(
                        name, inara_key.get().strip(), frontier_id.get().strip()
                    )
                if openai_key.get().strip():
                    OpenAICredentialStore().set(openai_key.get().strip())
                self.odin.config.update_preferences(
                    eddn_capture_enabled=network_vars["eddn"].get(),
                    eddn_upload_enabled=network_vars["eddn"].get(),
                    edsm_capture_enabled=network_vars["edsm"].get(),
                    edsm_upload_enabled=network_vars["edsm"].get(),
                    inara_capture_enabled=network_vars["inara"].get(),
                    inara_upload_enabled=network_vars["inara"].get(),
                    push_to_talk_enabled=voice_mode.get() in {"ptt", "both"},
                    wake_word_enabled=voice_mode.get() in {"wake", "both"},
                    speech_recognition_provider=recognition_labels.get(
                        recognition.get(), "auto"
                    ),
                    heimdall_auto_docking_enabled=auto_docking.get(),
                    ai_provider=ai_provider.get(),
                    openai_model=openai_model.get().strip() or "gpt-5-mini",
                    ai_share_trade_data=ai_share_trade_data.get(),
                    ai_share_mining_data=ai_share_mining_data.get(),
                    ai_share_navigation_data=ai_share_navigation_data.get(),
                    ai_share_science_data=ai_share_science_data.get(),
                    ai_share_progression_data=ai_share_progression_data.get(),
                    ai_share_powerplay_data=ai_share_powerplay_data.get(),
                    ai_share_commander_data=ai_share_commander_data.get(),
                    ai_share_station_search_data=ai_share_station_search_data.get(),
                    language=selected_language,
                    canonn_poi_source=canonn_source.get().strip(),
                )
                self.odin.docking_assist.configure(
                    enabled=auto_docking.get(), audit=self.odin.binding_audit
                )
                self.odin.apply_voice_activation_mode(
                    wake_enabled=voice_mode.get() in {"wake", "both"}
                )
                voice_settings = self.voice_repository.load()
                if language_changed:
                    apply_language_voice_preset(
                        voice_settings, selected_language
                    )
                for assignment in voice_settings.officers.values():
                    assignment.volume = volume.get()
                self.voice_repository.save(voice_settings)
            except (OSError, ValueError) as error:
                messagebox.showerror("ODIN", self._t("dialog.save_failed", error=error), parent=window)
                return
            print(
                self._t("settings.saved_log")
            )
            messagebox.showinfo(
                "ODIN", self._t("dialog.saved"), parent=window
            )
            window.destroy()

        tk.Button(
            actions, text=self._t("common.cancel"), command=window.destroy,
            bg=ELITE["surface_alt"], fg=ELITE["text"], relief="flat",
            activebackground=ELITE["border"], activeforeground=ELITE["text"],
            padx=12, pady=8, font=("Segoe UI", 10, "bold"), cursor="hand2",
        ).pack(side="left", fill="x", expand=True, padx=(0, 5))
        tk.Button(
            actions, text=self._t("common.accept"), command=save,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            activebackground=ELITE["orange"], padx=12, pady=8,
            font=("Segoe UI", 10, "bold"), cursor="hand2",
        ).pack(side="right", fill="x", expand=True, padx=(5, 0))

    def _delete_voice_calibration(self, commander: str, parent, refresh) -> None:
        if not commander:
            messagebox.showwarning(
                "ODIN", self._t("calibration.no_commander"), parent=parent
            )
            return
        if not messagebox.askyesno(
            "ODIN",
            self._t("calibration.delete"),
            parent=parent,
        ):
            return
        removed = self.voice_calibration.delete(commander)
        refresh()
        print(self._t("calibration.deleted_log", count=removed))

    def _restore_binding_snapshot(self, snapshot, parent) -> None:
        if snapshot is None:
            messagebox.showwarning(
                "ODIN", self._t("settings.no_snapshots"), parent=parent
            )
            return
        if not messagebox.askyesno(
            self._t("settings.restore_bindings"),
            self._t("settings.restore_bindings_confirm", snapshot=snapshot.name),
            parent=parent,
        ):
            return
        try:
            result = self.odin.binding_custodian.restore_snapshot(
                snapshot, confirmation="RESTORE_BINDINGS"
            )
        except (OSError, ValueError, RuntimeError, PermissionError) as error:
            messagebox.showerror("ODIN", str(error), parent=parent)
            return
        messagebox.showinfo(
            "ODIN",
            self._t(
                "settings.restore_bindings_done",
                count=len(result.restored_files),
            ),
            parent=parent,
        )

    def _open_voice_calibration(self, commander: str, parent, refresh) -> None:
        if not commander:
            messagebox.showwarning(
                "ODIN", self._t("calibration.no_commander"), parent=parent
            )
            return
        status = self.voice_calibration.status(commander)
        if not status.get("consented") and not messagebox.askyesno(
            self._t("calibration.consent_title"),
            self._t("calibration.consent"),
            parent=parent,
        ):
            return
        self.voice_calibration.begin(commander)
        listener = self.odin.wake_listener
        listener.enable_passive_listening(False)
        listener.pause()

        window = tk.Toplevel(parent)
        window.title(self._t("calibration.title"))
        window.geometry("540x360")
        window.resizable(False, False)
        window.configure(bg=ELITE["background"])
        window.transient(parent)
        window.grab_set()
        index = {"value": 0}
        current_acoustics = {"duration": None, "rms": None}
        current_transcript = {"value": ""}
        prompt = tk.StringVar()
        heard = tk.StringVar(value=self._t("calibration.ready"))
        progress = tk.StringVar()

        body = tk.Frame(window, bg=ELITE["background"], padx=20, pady=18)
        body.pack(fill="both", expand=True)
        tk.Label(
            body, text=self._t("calibration.heading"), bg=ELITE["background"],
            fg=ELITE["orange"], font=("Segoe UI", 14, "bold"), anchor="w",
        ).pack(fill="x")
        tk.Label(
            body, textvariable=progress, bg=ELITE["background"],
            fg=ELITE["muted"], font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x", pady=(2, 18))
        tk.Label(
            body, text=self._t("calibration.say"), bg=ELITE["background"],
            fg=ELITE["muted"], font=("Segoe UI", 9), anchor="w",
        ).pack(fill="x")
        tk.Label(
            body, textvariable=prompt, bg=ELITE["surface"], fg=ELITE["amber"],
            font=("Segoe UI", 15, "bold"), pady=18,
        ).pack(fill="x", pady=(5, 12))
        tk.Label(
            body, textvariable=heard, bg=ELITE["background"], fg=ELITE["text"],
            font=("Segoe UI", 10), justify="left", wraplength=490, anchor="w",
        ).pack(fill="x")
        actions = tk.Frame(body, bg=ELITE["background"])
        actions.pack(fill="x", side="bottom")

        def close() -> None:
            listener.enable_passive_listening(self.odin.config.wake_word_enabled)
            listener.resume()
            refresh()
            window.destroy()

        def render() -> None:
            position = index["value"]
            if position >= len(CALIBRATION_COMMANDS):
                prompt.set(self._t("calibration.finished"))
                progress.set(f"{len(CALIBRATION_COMMANDS)} de {len(CALIBRATION_COMMANDS)}")
                heard.set(self._t("calibration.saved"))
                record_button.configure(state="disabled")
                accept_button.configure(state="disabled")
                return
            command = CALIBRATION_COMMANDS[position]
            progress.set(self._t(
                "calibration.order_progress", current=position + 1,
                total=len(CALIBRATION_COMMANDS),
            ))
            prompt.set(self._t(f"calibration.command.{command.key}"))
            heard.set(self._t("calibration.speak"))
            current_transcript["value"] = ""
            current_acoustics.update(duration=None, rms=None)
            record_button.configure(state="normal", text=self._t("calibration.record"))
            accept_button.configure(state="disabled")

        def recording_finished(text: str = "", error: str = "") -> None:
            record_button.configure(state="normal", text=self._t("calibration.retry"))
            if error:
                heard.set(self._t("calibration.failed", error=error))
                accept_button.configure(state="disabled")
                return
            current_transcript["value"] = text
            heard.set(self._t("calibration.heard", text=text))
            accept_button.configure(state="normal")

        def record() -> None:
            record_button.configure(state="disabled", text=self._t("calibration.listening"))
            accept_button.configure(state="disabled")
            heard.set(self._t("calibration.capture"))
            command = CALIBRATION_COMMANDS[index["value"]]
            audio = self.odin.config.data_root / "speech" / f"calibration-{command.key}.wav"

            def worker() -> None:
                try:
                    captured = listener.recorder.record_utterance(
                        audio, silence_seconds=1.0, max_seconds=12.0
                    )
                    if captured is None:
                        raise MicrophoneError("No se detectó voz.")
                    text, _confidence = listener.transcriber.transcribe_with_confidence(
                        captured
                    )
                    duration, rms = analyze_calibration_wav(captured)
                    current_acoustics.update(duration=duration, rms=rms)
                    window.after(0, lambda: recording_finished(text=text))
                except (MicrophoneError, TranscriptionError, OSError) as error:
                    message = str(error)
                    window.after(
                        0, lambda message=message: recording_finished(error=message)
                    )
                finally:
                    audio.unlink(missing_ok=True)

            threading.Thread(
                target=worker, name="odin-voice-calibration", daemon=True
            ).start()

        def accept() -> None:
            transcript = current_transcript["value"].strip()
            if not transcript:
                return
            command = CALIBRATION_COMMANDS[index["value"]]
            self.voice_calibration.enroll(
                commander, transcript, command.key,
                duration=current_acoustics["duration"], rms=current_acoustics["rms"],
            )
            listener.recorder.apply_acoustic_profile(
                self.voice_calibration.status(commander)
            )
            listener.command_silence_seconds = listener.recorder.command_silence_seconds
            index["value"] += 1
            render()

        record_button = tk.Button(
            actions, text=self._t("calibration.record"), command=record,
            bg=ELITE["orange_soft"], fg=ELITE["background"], relief="flat",
            font=("Segoe UI", 9, "bold"), padx=12, pady=8,
        )
        record_button.pack(side="left")
        accept_button = tk.Button(
            actions, text=self._t("calibration.accept_sample"), command=accept, state="disabled",
            bg=ELITE["surface_alt"], fg=ELITE["amber"], relief="flat",
            font=("Segoe UI", 9, "bold"), padx=12, pady=8,
        )
        accept_button.pack(side="left", padx=8)
        tk.Button(
            actions, text=self._t("common.close"), command=close,
            bg=ELITE["surface_alt"], fg=ELITE["text"], relief="flat",
            font=("Segoe UI", 9, "bold"), padx=12, pady=8,
        ).pack(side="right")
        window.protocol("WM_DELETE_WINDOW", close)
        render()

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
            modes.append(self._t("footer.ptt"))
        if self.odin.config.wake_word_enabled:
            modes.append(self._t("footer.wake"))
        if self.odin.config.heimdall_auto_docking_enabled:
            modes.append(self._t("footer.docking"))
        modes.append(self._t("footer.journal"))
        return "    ·    ".join(modes)

    @staticmethod
    def _credits(value, approximate: bool = False) -> str:
        prefix = "≈ " if approximate else ""
        return f"{prefix}{int(value or 0):,} CR".replace(",", ".")

    @staticmethod
    def _mining_prospect_text(prospect: dict, language: str = "es-419") -> str:
        if not prospect:
            return localized_text("brokk.no_prospects", language)
        lines = []
        content = str(prospect.get("content", "") or "").strip()
        remaining = float(prospect.get("remaining", 0) or 0)
        if content:
            lines.append(content)
        lines.append(localized_text("brokk.reserve_remaining", language, value=remaining))
        materials = sorted(
            prospect.get("materials", ()) or (),
            key=lambda item: float(item.get("proportion", 0) or 0),
            reverse=True,
        )
        lines.extend(
            f"◆ {item.get('name', localized_text('common.unknown', language))} · "
            f"{float(item.get('proportion', 0) or 0):.1f}%"
            for item in materials
        )
        return "\n".join(lines)

    @staticmethod
    def _mining_inventory_text(items: dict, empty: str, unit: str) -> str:
        if not items:
            return empty
        return "\n".join(
            f"◆ {name} · {int(count)} {unit}"
            for name, count in sorted(
                items.items(), key=lambda item: (-int(item[1]), item[0].casefold())
            )
        )

    @staticmethod
    def _mining_equipment_text(equipment: dict, language: str = "es-419") -> str:
        if not equipment:
            return localized_text("brokk.waiting_equipment", language)
        labels = {
            "laser": localized_text("brokk.technique.laser", language),
            "abrasion": localized_text("brokk.technique.abrasion", language),
            "subsurface": localized_text("brokk.technique.subsurface", language),
            "core": localized_text("brokk.technique.core", language),
        }
        ship = str(equipment.get("ship", localized_text("brokk.unknown_ship", language)))
        cargo = int(equipment.get("cargo_capacity", 0) or 0)
        lines = [localized_text("brokk.ship_hold", language, ship=ship, cargo=cargo)]
        for technique in ("laser", "abrasion", "subsurface", "core"):
            state = equipment.get("techniques", {}).get(technique, {})
            if state.get("ready"):
                lines.append(localized_text("brokk.equipment_ready", language, technique=labels[technique]))
            else:
                missing = ", ".join(state.get("missing", ())) or localized_text("common.no_data", language)
                lines.append(localized_text("brokk.equipment_missing", language, technique=labels[technique], missing=missing))
        return "\n".join(lines)

    def _biology_details_text(self, biology: dict) -> str:
        lines = []
        for item in biology.get("details", ()):
            signals = int(item.get("signals", 0) or 0)
            signal_text = f" · {self._t('mimir.signals', count=signals)}" if signals else ""
            lines.append(f"◆ {item.get('body', self._t('mimir.unknown_body'))}{signal_text}")
            for species in item.get("confirmed", ()):
                source = item.get("confirmation")
                suffix = f" · {self._t('mimir.confirmed_by', source=source)}" if source else ""
                lines.append(f"  ✓ {species}{suffix}")
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
                reward_type = self._t("mimir.reward_first") if first_footfall else self._t("mimir.reward_normal")
                value_text = (
                    f" — {reward_type}: {OdinDesktopApp._credits(value, True)}"
                    if value else ""
                )
                lines.append(f"  ◇ {species}{value_text}")
            if not item.get("confirmed") and not item.get("probable"):
                lines.append(f"  ○ {self._t('mimir.unidentified')}")
            lines.append("")
        return "\n".join(lines).rstrip() or self._t("mimir.no_biology")

    def _sampling_details_text(self, biology: dict) -> str:
        lines = []
        for item in biology.get("details", ()):
            sampling = item.get("sampling", ())
            if not sampling:
                continue
            lines.append(f"◆ {item.get('body', self._t('mimir.unknown_body'))}")
            for sample in sampling:
                progress = int(sample.get("progress", 0) or 0)
                species = sample.get("species", self._t("mimir.biology"))
                if progress >= 3:
                    lines.append(f"  ✓ {species} · 3/3 {self._t('mimir.completed')}")
                    continue
                lines.append(f"  ◇ {species} · {progress}/3")
                distance = sample.get("distance_m")
                required = sample.get("required_distance_m")
                if distance is not None and required:
                    remaining = max(0, round(float(required) - float(distance)))
                    if sample.get("ready"):
                        lines.append(f"    {self._t('mimir.ready_next')}")
                    else:
                        lines.append(
                            f"    {round(float(distance))}/{round(float(required))} m"
                            f" · {self._t('mimir.remaining', distance=remaining)}"
                        )
            lines.append("")
        return "\n".join(lines).rstrip() or self._t("mimir.no_samples")


def run_desktop(odin) -> None:
    OdinDesktopApp(odin).run()
