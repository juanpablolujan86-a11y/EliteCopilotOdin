"""Presentación mínima de ODIN durante el vuelo."""

from models.events.exploration_report_ready import ExplorationReportReady
from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from models.events.organic_scan_updated import OrganicScanUpdated
from models.events.recommendation_ready import RecommendationReady
from models.officer_report import OfficerReport
from models.events.surface_navigation_updated import SurfaceNavigationUpdated
from core.localization import text as localized_text


class ConsolePresenter:
    """Muestra sólo información inmediata para el comandante."""

    def __init__(self, language: str = "es-419") -> None:
        self.language = language
        self._shown_biology_states: set[tuple] = set()

    def _t(self, key: str, **values) -> str:
        return localized_text(key, self.language, **values)

    def show_organic_scan(self, scan: OrganicScanUpdated) -> None:
        """Muestra el conteo de la recolección activa."""

        print()
        print("-" * 50)
        print(self._t("console.sample", progress=scan.progress))
        print(self._t("console.species", species=scan.species or scan.genus))
        if scan.completed:
            print(self._t("console.sample_complete"))
        elif scan.required_distance_m is not None:
            print(self._t("console.next_sample", distance=scan.required_distance_m))
        print("-" * 50)

    def show_surface_navigation(self, update: SurfaceNavigationUpdated) -> None:
        """Informa el avance hacia una posición válida de muestreo."""

        state = self._t("console.ready") if update.ready_for_sample else self._t("console.too_close")
        print(self._t("console.sample_distance", distance=update.distance_m,
                      required=update.required_distance_m, state=state))

    def show_route_progress(self, update) -> None:
        """Muestra un contador compacto después de cada salto de HEIMDALL."""

        if update.route_abandoned or update.total_jumps <= 0:
            return
        print(self._t("console.route_progress", completed=update.jumps_completed,
                      total=update.total_jumps, remaining=update.jumps_remaining))

    def show_expedition_balance(
        self,
        balance: ExpeditionBalanceUpdated,
    ) -> None:
        """Presenta un resumen compacto al completar o vender datos."""

        print()
        print("=" * 50)
        print(self._t("console.balance", reason=balance.reason))
        print(self._t("console.activity", systems=balance.systems_visited,
                      bodies=balance.bodies_scanned, mapped=balance.bodies_mapped,
                      species=balance.species_completed))
        print(self._t("console.cartography", value=f"{balance.cartography_estimated:,}"))
        print(self._t("console.exobiology_base", value=f"{balance.exobiology_base:,}"))
        if balance.exobiology_potential != balance.exobiology_base:
            print(self._t("console.exobiology_potential", value=f"{balance.exobiology_potential:,}"))
        print(self._t("console.total_base", value=f"{balance.total_base:,}"))
        print(self._t("console.total_potential", value=f"{balance.total_potential:,}"))
        if balance.exploration_sold or balance.exobiology_sold:
            print(self._t("console.confirmed_paid", value=f"{balance.exploration_sold + balance.exobiology_sold:,}"))
        print("=" * 50)

    def show_recommendation(
        self,
        recommendation: RecommendationReady,
    ) -> None:
        if not recommendation.message:
            return

        # Cada salto reemplaza el sistema anterior en lugar de acumularlo.
        self._shown_biology_states.clear()
        print("\033[2J\033[H", end="")
        print("-" * 50)
        print(self._t("console.discovery_status"))
        print(recommendation.message)
        print("-" * 50)

    def show_exploration_report(
        self,
        report: ExplorationReportReady,
    ) -> None:
        """Avisa únicamente qué planetas poseen señales biológicas."""

        if not report.biological_bodies:
            return

        new_bodies = [
            body_name
            for body_name in report.biological_bodies
            if (body_name, "pendiente_dss")
            not in self._shown_biology_states
        ]
        if not new_bodies:
            return

        print()
        print("=" * 50)
        print(self._t("console.biology_detected"))
        for body_name in new_bodies:
            state = (body_name, "pendiente_dss")
            self._shown_biology_states.add(state)
            print(self._t("console.planet", body=body_name))
            print(self._t("console.pending_dss"))
        print("=" * 50)

    def show_scientific_report(
        self,
        report: OfficerReport,
    ) -> None:
        """Muestra planeta, géneros DSS y especies probables."""

        if not report.has_biological_signal:
            return

        state = (
            report.body_name,
            report.confirmed_genus_names,
            report.probable_species,
            report.probable_species_values,
        )
        if state in self._shown_biology_states:
            return
        self._shown_biology_states.add(state)

        print()
        print("=" * 50)
        print(self._t("console.biology_detected"))
        print(self._t("console.planet", body=report.body_name or self._t("console.unknown")))

        if report.confirmed_genus_names:
            print(self._t("console.dss_genera", genera=", ".join(report.confirmed_genus_names)))

        if report.probable_species:
            print(self._t("console.probable_species"))
            values = {
                name: (base, potential)
                for name, base, potential in report.probable_species_values
            }
            for species in report.probable_species:
                base, potential = values.get(species, (0, 0))
                if not base:
                    print(f"  - {species}")
                elif potential != base:
                    print(
                        self._t("console.species_first", species=species,
                                base=f"{base:,}", potential=f"{potential:,}")
                    )
                else:
                    print(f"  - {species}: {base:,} CR")

        print("=" * 50)
