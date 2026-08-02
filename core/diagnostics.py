"""Registro persistente de funcionamiento y actividad científica."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from core.version import CAPABILITY, VERSION
from models.events.exploration_report_ready import ExplorationReportReady
from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from models.events.organic_scan_updated import OrganicScanUpdated
from models.events.recommendation_ready import RecommendationReady
from models.events.surface_navigation_updated import SurfaceNavigationUpdated
from models.officer_report import OfficerReport
from heimdall.bindings import BindingAudit


def _handler(path: Path) -> RotatingFileHandler:
    handler = RotatingFileHandler(
        path,
        maxBytes=2_000_000,
        backupCount=3,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter(
            "%(asctime)s | PID=%(process)d | %(levelname)s | %(message)s"
        )
    )
    return handler


def configure_diagnostics(data_root: Path) -> None:
    """Configura los archivos de diagnóstico una sola vez."""

    logs = data_root / "logs"
    logs.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    if not any(getattr(item, "baseFilename", None) for item in root.handlers):
        root.addHandler(_handler(logs / "odin.log"))

    logging.getLogger("odin").info(
        "Inicio de ODIN v%s - %s", VERSION, CAPABILITY
    )


def log_fatal_error() -> None:
    logging.getLogger("odin").exception("Fallo fatal no controlado")


class OdinDiagnostics:
    """Conserva informes ocultos para diagnóstico y futura salida por voz."""

    def __init__(self) -> None:
        self.logger = logging.getLogger("odin.reports")

    def record_recommendation(self, report: RecommendationReady) -> None:
        self.logger.info(
            "DESCUBRIMIENTO | prioridad=%s | mensaje=%s | motivos=%s",
            report.priority,
            report.message.replace("\n", " | "),
            " | ".join(report.reasons) or "Sin motivos",
        )

    def record_exploration_report(self, report: ExplorationReportReady) -> None:
        self.logger.info(
            "FSS | sistema=%s | cuerpos=%s/%s | estrellas=%s | planetas=%s "
            "| lunas=%s | terraformables=%s | cartografiados=%s | biología=%s "
            "| muestras=%s | completo=%s | cuerpos_biológicos=%s "
            "| recomendación=%s | motivos=%s",
            report.system_name,
            report.discovered_body_count,
            report.expected_body_count,
            report.star_count,
            report.planet_count,
            report.moon_count,
            report.terraformable_count,
            report.mapped_count,
            report.biology_signal_count,
            report.organic_sample_count,
            report.all_bodies_found,
            ", ".join(report.biological_bodies) or "ninguno",
            report.recommendation,
            " | ".join(report.reasons) or "Sin motivos",
        )

    def record_expedition_balance(
        self,
        balance: ExpeditionBalanceUpdated,
    ) -> None:
        self.logger.info(
            "BALANCE | motivo=%s | sistemas=%s | cuerpos=%s | DSS=%s "
            "| especies=%s | cartografia_estimada=%s | exobiologia_base=%s "
            "| exobiologia_potencial=%s | cartografia_cobrada=%s "
            "| exobiologia_cobrada=%s",
            balance.reason,
            balance.systems_visited,
            balance.bodies_scanned,
            balance.bodies_mapped,
            balance.species_completed,
            balance.cartography_estimated,
            balance.exobiology_base,
            balance.exobiology_potential,
            balance.exploration_sold,
            balance.exobiology_sold,
        )


class MimirDiagnostics:
    """Guarda un historial humano de lo que MÍMIR decidió y observó."""

    def __init__(self, data_root: Path) -> None:
        logs = data_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("mimir.activity")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            self.logger.addHandler(_handler(logs / "mimir.log"))

    def record_scientific_report(self, report: OfficerReport) -> None:
        details = " | ".join(report.details) if report.details else "Sin detalles"
        self.logger.info(
            "ANÁLISIS | prioridad=%s | título=%s | mensaje=%s | %s",
            report.priority,
            report.title,
            report.message,
            details,
        )

    def record_organic_scan(self, scan: OrganicScanUpdated) -> None:
        self.logger.info(
            "MUESTREO | body_id=%s | género=%s | especie=%s "
            "| variante=%s | progreso=%s/3 | completado=%s | was_logged=%s",
            scan.body_id,
            scan.genus or "",
            scan.species or "",
            scan.variant or "",
            scan.progress,
            scan.completed,
            scan.was_logged,
        )

    def record_surface_navigation(
        self,
        update: SurfaceNavigationUpdated,
    ) -> None:
        self.logger.info(
            "DISTANCIA | especie=%s | progreso=%s/3 | actual=%.1f m "
            "| requerida=%.1f m | muestra_disponible=%s",
            update.species or update.genus,
            update.progress,
            update.distance_m,
            update.required_distance_m,
            update.ready_for_sample,
        )

    def close(self) -> None:
        """Cierra los archivos; se usa en pruebas y apagados controlados."""

        for handler in list(self.logger.handlers):
            handler.close()
            self.logger.removeHandler(handler)


class HeimdallDiagnostics:
    """Registro propio del oficial de navegación HEIMDALL."""

    def __init__(self, data_root: Path) -> None:
        logs = data_root / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        self.logger = logging.getLogger("heimdall.activity")
        self.logger.setLevel(logging.INFO)
        self.logger.propagate = False
        if not self.logger.handlers:
            self.logger.addHandler(_handler(logs / "heimdall.log"))

    def record_binding_audit(self, audit: BindingAudit) -> None:
        self.logger.info(
            "BINDINGS | perfiles=%s | activos=%s | snapshot=%s | errores=%s",
            ", ".join(
                f"{profile.preset_name} {profile.major_version}.{profile.minor_version} "
                f"({profile.keyboard_layout})"
                for profile in audit.profiles
            ) or "ninguno",
            ", ".join(audit.active_presets) or "ninguno",
            audit.snapshot_path or "sin snapshot",
            " | ".join(audit.loading_errors) or "ninguno",
        )

    def record_navigation_context(self, context, *, reason: str) -> None:
        progress = context.route_progress()
        fuel = context.fuel_assessment()
        high_energy = context.high_energy_assessment()
        self.logger.info(
            "NAVIGATION | motivo=%s | nave=%s | identificador=%s | "
            "rango=%.2f ly | combustible=%.2f/%.2f t | sistema=%s | "
            "destino=%s | clase=%s | saltos_journal=%s | puntos_ruta=%s | "
            "saltos_ruta=%s | distancia_ruta=%s | fuera_ruta=%s | "
            "autonomia_conservadora=%s | saltos_hasta_repostaje=%s | "
            "proximo_repostaje=%s | margen_combustible=%s | inseguro=%s | "
            "fsd_salud=%s | cono_cargado=%s | valor_boost=%s | "
            "boost_usado=%s | exposiciones_sesion=%s | saltos_boost_sesion=%s | "
            "proximo_neutron=%s | saltos_hasta_neutron=%s | neutrones_ruta=%s | "
            "enanas_blancas_ruta=%s",
            reason,
            context.ship_name or context.ship_type or "desconocida",
            context.ship_ident or "sin identificador",
            context.max_jump_range,
            context.fuel_main,
            context.fuel_capacity,
            context.current_system or "desconocido",
            context.target_system or "sin destino",
            context.target_star_class or "desconocida",
            context.remaining_jumps if context.remaining_jumps is not None else "?",
            len(context.route),
            progress.remaining_jumps if progress.remaining_jumps is not None else "?",
            (
                f"{progress.remaining_distance_ly:.2f} ly"
                if progress.remaining_distance_ly is not None else "?"
            ),
            progress.off_route,
            fuel.jumps_available if fuel.jumps_available is not None else "?",
            fuel.jumps_to_refuel if fuel.jumps_to_refuel is not None else "?",
            (
                fuel.refuel_waypoint.system
                if fuel.refuel_waypoint is not None
                else ("destino" if fuel.destination_before_refuel else "?")
            ),
            (
                f"{fuel.fuel_margin_t:.2f} t"
                if fuel.fuel_margin_t is not None else "?"
            ),
            fuel.unsafe if fuel.unsafe is not None else "?",
            (
                f"{high_energy.fsd_health * 100:.1f}%"
                if high_energy.fsd_health is not None else "?"
            ),
            high_energy.charged,
            high_energy.boost_value if high_energy.boost_value is not None else "?",
            high_energy.last_boost_used if high_energy.last_boost_used is not None else "?",
            high_energy.cone_exposures_session,
            high_energy.boosted_jumps_session,
            high_energy.next_neutron.system if high_energy.next_neutron else "ninguno",
            (
                high_energy.jumps_to_next_neutron
                if high_energy.jumps_to_next_neutron is not None else "?"
            ),
            high_energy.remaining_neutrons,
            high_energy.remaining_white_dwarfs,
        )
