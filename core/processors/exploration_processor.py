# ============================================================
# ODIN
#
# Versión : 0.2.0
#
# Sprint  : 4 - MÍMIR
# ============================================================

"""
ODIN - Orbital Data Intelligence Nexus

exploration_processor.py

Procesa la exploración científica:
- Scan
- FSSDiscoveryScan
- FSSAllBodiesFound
- SAAScanComplete
- SAASignalsFound
- ScanOrganic
"""

import json
import unicodedata

from core.database import DatabaseManager
from core.event_bus import EventBus
from core.internal_events import InternalEvent
from models.events.exploration_report_ready import (
    ExplorationReportReady,
)
from models.events.planet_scan_ready import (
    PlanetScanReady,
)
from models.events.organic_scan_updated import OrganicScanUpdated
from models.events.voice_message_ready import VoiceMessageReady
from state.commander_state import CommanderState
from mimir.surface_navigation import SurfaceNavigationTracker


class ExplorationProcessor:
    """
    Capacidad central de exploración de ODIN.
    """

    def __init__(
        self,
        database: DatabaseManager,
        commander_state: CommanderState,
        event_bus: EventBus,
        surface_navigation: SurfaceNavigationTracker | None = None,
    ) -> None:
        self.database = database
        self.commander_state = commander_state
        self.event_bus = event_bus
        self.surface_navigation = surface_navigation
        self._confirmed_genus_ids: dict[
            tuple[int, int],
            tuple[str, ...],
        ] = {}
        self._confirmed_genus_names: dict[
            tuple[int, int],
            tuple[str, ...],
        ] = {}
        self._completed_system_reports: set[int] = set()
        self._star_only_announced: set[int] = set()
        self._organic_scan_progress: dict[
            tuple[int, int | None, str, str],
            int,
        ] = {}
        self._biological_body_ids: set[tuple[int, int]] = set()

    def handle_fsd_jump(self, event: dict) -> None:
        """
        Inicializa el estado de exploración del nuevo sistema.
        """

        system_address = event.get("SystemAddress")
        system_name = event.get("StarSystem")
        timestamp = event.get("timestamp", "")

        if system_address is None or not system_name:
            return

        self.commander_state.expected_body_count = 0
        self.commander_state.discovered_body_count = 0
        self.commander_state.mapped_body_count = 0
        self.commander_state.biology_signal_count = 0
        self.commander_state.organic_sample_count = 0
        self.commander_state.last_scanned_body = ""
        self._confirmed_genus_ids.clear()
        self._confirmed_genus_names.clear()
        self._biological_body_ids.clear()
        self._organic_scan_progress.clear()
        self._completed_system_reports.discard(system_address)
        self._star_only_announced.discard(system_address)

        self.database.execute(
            """
            INSERT INTO system_exploration
            (
                system_address,
                system_name,
                updated_at
            )
            VALUES (?, ?, ?)
            ON CONFLICT(system_address)
            DO UPDATE SET
                system_name = excluded.system_name,
                updated_at = excluded.updated_at
            """,
            (
                system_address,
                system_name,
                timestamp,
            ),
        )

    def handle_scan(self, event: dict) -> None:
        """
        Guarda una estrella, planeta o luna escaneada.
        """

        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        system_name = event.get(
            "StarSystem",
            self.commander_state.current_system,
        )

        body_id = event.get("BodyID")
        body_name = event.get("BodyName")
        timestamp = event.get("timestamp", "")

        if (
            not system_address
            or body_id is None
            or not body_name
        ):
            return

        if self._is_belt_cluster(event):
            print(
                "Exploración           : "
                f"Belt Cluster ignorado — {body_name}"
            )
            return

        body_type, subtype, is_moon = self._classify_body(event)

        if body_type == "Estrella":
            star = {
                "type": event.get("StarType", ""),
                "luminosity": event.get("Luminosity", ""),
            }
            existing_index = next(
                (
                    index
                    for index, item in enumerate(
                        self.commander_state.system_stars
                    )
                    if item.get("type") == star["type"]
                    and item.get("luminosity") == star["luminosity"]
                ),
                None,
            )

            if existing_index is None:
                self.commander_state.system_stars.append(star)
        elif subtype and subtype not in self.commander_state.system_body_types:
            self.commander_state.system_body_types.append(subtype)

        terraform_state = str(
            event.get("TerraformState", "")
        ).lower()

        terraformable = int(
            terraform_state == "terraformable"
        )

        raw_json = json.dumps(
            event,
            ensure_ascii=False,
        )

        self.database.execute(
            """
            INSERT INTO stellar_bodies
            (
                system_address,
                system_name,
                body_id,
                body_name,
                body_type,
                subtype,
                is_moon,
                terraformable,
                atmosphere,
                volcanism,
                gravity,
                radius,
                distance_from_arrival,
                was_discovered,
                was_mapped,
                was_footfalled,
                landable,
                raw_json,
                scanned_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(system_address, body_id)
            DO UPDATE SET
                body_name = excluded.body_name,
                body_type = excluded.body_type,
                subtype = excluded.subtype,
                is_moon = excluded.is_moon,
                terraformable = excluded.terraformable,
                atmosphere = excluded.atmosphere,
                volcanism = excluded.volcanism,
                gravity = excluded.gravity,
                radius = excluded.radius,
                distance_from_arrival = excluded.distance_from_arrival,
                was_discovered = excluded.was_discovered,
                was_mapped = excluded.was_mapped,
                was_footfalled = excluded.was_footfalled,
                landable = excluded.landable,
                raw_json = excluded.raw_json,
                scanned_at = excluded.scanned_at
            """,
            (
                system_address,
                system_name,
                body_id,
                body_name,
                body_type,
                subtype,
                is_moon,
                terraformable,
                event.get(
                    "Atmosphere_Localised",
                    event.get("Atmosphere"),
                ),
                event.get(
                    "Volcanism_Localised",
                    event.get("Volcanism"),
                ),
                event.get("SurfaceGravity"),
                event.get("Radius"),
                event.get("DistanceFromArrivalLS"),
                int(bool(event.get("WasDiscovered", False))),
                int(bool(event.get("WasMapped", False))),
                int(bool(event.get("WasFootfalled", False))),
                int(bool(event.get("Landable", False))),
                raw_json,
                timestamp,
            ),
        )

        self.commander_state.last_scanned_body = body_name

        self._refresh_system_totals(
            system_address,
            system_name,
            timestamp,
        )

        planet_scan = PlanetScanReady(
            event=event,
            confirmed_genus_ids=self._confirmed_genus_ids.get(
                (system_address, body_id),
                (),
            ),
            confirmed_genus_names=self._confirmed_genus_names.get(
                (system_address, body_id),
                (),
            ),
            has_biological_signal=(
                (system_address, body_id) in self._biological_body_ids
            ),
            system_population=self.commander_state.population,
            scientific_context={
                "region_id": self.commander_state.galactic_region_id,
                "region_name": self.commander_state.galactic_region_name,
                "stars": list(self.commander_state.system_stars),
                "system_position": self.commander_state.star_position,
                "body_types": list(self.commander_state.system_body_types),
                "system_name": self.commander_state.current_system,
            },
        )

        self.event_bus.publish_internal(
            InternalEvent.PLANET_SCAN_READY,
            planet_scan,
        )

        print(
            "Exploración           : "
            f"Cuerpo registrado — {body_name} "
            f"({body_type})"
        )

        if terraformable:
            print(
                "Interés científico    : "
                "Cuerpo terraformable detectado"
            )

    def handle_disembark(self, event: dict) -> None:
        """Confirma y anuncia una primera pisada conocida por ODIN."""

        if not event.get("OnPlanet", False):
            return
        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )
        body_id = event.get("BodyID")
        if system_address is None or body_id is None:
            return
        rows = self.database.query(
            """
            SELECT body_name FROM stellar_bodies
            WHERE system_address=? AND body_id=?
              AND landable=1 AND was_footfalled=0
            """,
            (system_address, body_id),
        )
        if not rows or self.database.query(
            "SELECT 1 FROM mimir_first_footfalls WHERE system_address=? AND body_id=?",
            (system_address, body_id),
        ):
            return
        body_name = str(event.get("Body") or rows[0]["body_name"])
        self.database.execute(
            """
            INSERT INTO mimir_first_footfalls
            (system_address, body_id, body_name, confirmed_at)
            VALUES (?, ?, ?, ?)
            """,
            (system_address, body_id, body_name, event.get("timestamp", "")),
        )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady(
                officer="MÍMIR",
                message=(
                    "Felicidades, sos el primer descendiente de un mono "
                    "pulgoso en pisar este planeta. Darwin estaría "
                    "orgulloso de vos."
                ),
                reason="Primera pisada confirmada",
                body_name=body_name,
            ),
        )

    def handle_fss_discovery_scan(self, event: dict) -> None:
        """
        Registra el número esperado de cuerpos del sistema.
        """

        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        system_name = event.get(
            "SystemName",
            self.commander_state.current_system,
        )

        body_count = int(event.get("BodyCount", 0))
        timestamp = event.get("timestamp", "")

        if not system_address:
            return

        self.commander_state.expected_body_count = body_count

        self.database.execute(
            """
            INSERT INTO system_exploration
            (
                system_address,
                system_name,
                expected_body_count,
                updated_at
            )
            VALUES (?, ?, ?, ?)
            ON CONFLICT(system_address)
            DO UPDATE SET
                system_name = excluded.system_name,
                expected_body_count = excluded.expected_body_count,
                updated_at = excluded.updated_at
            """,
            (
                system_address,
                system_name,
                body_count,
                timestamp,
            ),
        )

        print(
            "FSS                   : "
            f"{body_count} cuerpos esperados"
        )

    def handle_fss_all_bodies_found(self, event: dict) -> None:
        """
        Marca el sistema como completamente identificado.
        """

        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        system_name = event.get(
            "SystemName",
            self.commander_state.current_system,
        )

        body_count = int(event.get("Count", 0))
        timestamp = event.get("timestamp", "")

        if not system_address:
            return

        if system_address in self._completed_system_reports:
            print(
                "FSS                   : "
                "Informe completo duplicado ignorado"
            )
            return

        if body_count:
            self.commander_state.expected_body_count = body_count

        self._refresh_system_totals(
            system_address,
            system_name,
            timestamp,
        )

        self.database.execute(
            """
            UPDATE system_exploration
            SET
                expected_body_count =
                    CASE
                        WHEN ? > 0 THEN ?
                        ELSE expected_body_count
                    END,
                all_bodies_found = 1,
                updated_at = ?
            WHERE system_address = ?
            """,
            (
                body_count,
                body_count,
                timestamp,
                system_address,
            ),
        )

        print(
            "FSS                   : "
            "Todos los cuerpos fueron identificados"
        )

        self._completed_system_reports.add(system_address)

        self._announce_star_only_system(system_address, system_name)

        self._publish_report(
            system_address,
            system_name,
        )

    def handle_saa_scan_complete(self, event: dict) -> None:
        """
        Registra un cuerpo cartografiado con DSS.
        """

        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        body_id = event.get("BodyID")
        body_name = event.get("BodyName")
        timestamp = event.get("timestamp", "")

        if not system_address or body_id is None:
            return

        probes_used = event.get("ProbesUsed")
        efficiency_target = event.get("EfficiencyTarget")

        efficiency_bonus = int(
            probes_used is not None
            and efficiency_target is not None
            and probes_used <= efficiency_target
        )

        self.database.execute(
            """
            INSERT INTO mapped_bodies
            (
                system_address,
                body_id,
                body_name,
                probes_used,
                efficiency_target,
                efficiency_bonus,
                mapped_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(system_address, body_id)
            DO UPDATE SET
                body_name = excluded.body_name,
                probes_used = excluded.probes_used,
                efficiency_target = excluded.efficiency_target,
                efficiency_bonus = excluded.efficiency_bonus,
                mapped_at = excluded.mapped_at
            """,
            (
                system_address,
                body_id,
                body_name,
                probes_used,
                efficiency_target,
                efficiency_bonus,
                timestamp,
            ),
        )

        self.database.execute(
            """
            UPDATE stellar_bodies
            SET was_mapped = 1
            WHERE system_address = ?
              AND body_id = ?
            """,
            (
                system_address,
                body_id,
            ),
        )

        system_name = self.commander_state.current_system

        self._refresh_system_totals(
            system_address,
            system_name,
            timestamp,
        )

        print(
            "DSS                   : "
            f"Cuerpo cartografiado — {body_name or body_id}"
        )

        if efficiency_bonus:
            print(
                "DSS                   : "
                "Bonificación de eficiencia obtenida"
            )

        self._publish_report(
            system_address,
            system_name,
        )

    def handle_saa_signals_found(self, event: dict) -> None:
        """
        Registra señales detectadas mediante DSS.
        """

        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        body_id = event.get("BodyID")
        body_name = event.get("BodyName")
        timestamp = event.get("timestamp", "")
        signals = event.get("Signals", [])
        genuses = event.get("Genuses", [])

        if not system_address:
            return

        source_event = event.get("event", "SAASignalsFound")

        if body_id is not None:
            self.database.execute(
                """
                DELETE FROM biological_signals
                WHERE system_address = ?
                  AND body_id = ?
                  AND source_event IN (
                      'FSSBodySignals',
                      'SAASignalsFound'
                  )
                """,
                (system_address, body_id),
            )

        biology_total = 0
        confirmed_genus_ids = tuple(
            dict.fromkeys(
                genus.get("Genus")
                for genus in genuses
                if genus.get("Genus")
            )
        )
        confirmed_genus_names = tuple(
            dict.fromkeys(
                genus.get("Genus_Localised", genus.get("Genus"))
                for genus in genuses
                if genus.get("Genus_Localised", genus.get("Genus"))
            )
        )

        if body_id is not None and confirmed_genus_ids:
            self._confirmed_genus_ids[
                (system_address, body_id)
            ] = confirmed_genus_ids
            self._confirmed_genus_names[
                (system_address, body_id)
            ] = confirmed_genus_names

        for signal in signals:
            localized_signal_type = signal.get(
                "Type_Localised",
                signal.get("Type", ""),
            )

            is_biological = self._is_biological_signal(signal)
            signal_type = (
                "Biological"
                if is_biological
                else localized_signal_type
            )

            signal_count = int(signal.get("Count", 0))

            if is_biological:
                biology_total += signal_count

            self.database.execute(
                """
                INSERT INTO biological_signals
                (
                    system_address,
                    body_id,
                    body_name,
                    source_event,
                    signal_type,
                    signal_count,
                    genus,
                    recorded_at,
                    raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    system_address,
                    body_id,
                    body_name,
                    source_event,
                    signal_type,
                    signal_count,
                    ", ".join(confirmed_genus_names) or None,
                    timestamp,
                    json.dumps(
                        event,
                        ensure_ascii=False,
                    ),
                ),
            )

        if body_id is not None and biology_total:
            self._biological_body_ids.add((system_address, body_id))

        system_name = self.commander_state.current_system

        self._refresh_system_totals(
            system_address,
            system_name,
            timestamp,
        )

        if biology_total:
            print(
                "Exobiología           : "
                f"{biology_total} señales biológicas detectadas"
            )

        if confirmed_genus_names:
            print(
                "Género confirmado     : "
                + ", ".join(confirmed_genus_names)
            )

        self._publish_report(
            system_address,
            system_name,
        )

    def handle_scan_organic(self, event: dict) -> None:
        """
        Registra una muestra orgánica real.
        """

        system_address = event.get(
            "SystemAddress",
            self.commander_state.system_address,
        )

        body_id = event.get("Body")
        timestamp = event.get("timestamp", "")

        if not system_address:
            return

        genus = event.get(
            "Genus_Localised",
            event.get("Genus"),
        )

        species = event.get(
            "Species_Localised",
            event.get("Species"),
        )

        variant = event.get(
            "Variant_Localised",
            event.get("Variant"),
        )

        scan_type = event.get("ScanType")
        was_logged = event.get("WasLogged")

        self.database.execute(
            """
            INSERT INTO biological_signals
            (
                system_address,
                body_id,
                source_event,
                genus,
                species,
                variant,
                scan_type,
                was_logged,
                signal_count,
                recorded_at,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                system_address,
                body_id,
                "ScanOrganic",
                genus,
                species,
                variant,
                scan_type,
                None if was_logged is None else int(bool(was_logged)),
                timestamp,
                json.dumps(
                    event,
                    ensure_ascii=False,
                ),
            ),
        )

        progress_by_type = {
            "Log": 1,
            "Sample": 2,
            "Analyse": 3,
        }
        progress = progress_by_type.get(scan_type, 0)
        navigation_update = (
            self.surface_navigation.record_sample(event)
            if self.surface_navigation is not None
            else None
        )
        progress_key = (
            system_address,
            body_id,
            str(event.get("Species", species or "")),
            str(event.get("Variant", variant or "")),
        )
        previous_progress = self._organic_scan_progress.get(
            progress_key,
            0,
        )

        if progress <= previous_progress:
            return

        self._organic_scan_progress[progress_key] = progress

        self.event_bus.publish_internal(
            InternalEvent.ORGANIC_SCAN_UPDATED,
            OrganicScanUpdated(
                body_id=body_id,
                genus=genus or "",
                species=species or "",
                variant=variant or "",
                scan_type=scan_type or "",
                progress=progress,
                completed=scan_type == "Analyse",
                was_logged=(
                    None if was_logged is None else bool(was_logged)
                ),
                required_distance_m=(
                    navigation_update.required_distance_m
                    if navigation_update is not None
                    else None
                ),
            ),
        )

        if progress in (1, 2) and navigation_update is not None:
            ordinal = "primera" if progress == 1 else "segunda"
            next_ordinal = "segunda" if progress == 1 else "tercera"
            self.event_bus.publish_internal(
                InternalEvent.VOICE_MESSAGE_READY,
                VoiceMessageReady(
                    officer="MÍMIR",
                    message=(
                        f"{ordinal.capitalize()} muestra registrada. Para la "
                        f"{next_ordinal} muestra de {species or genus or 'esta especie'}, "
                        f"alejate al menos {navigation_update.required_distance_m:.0f} metros."
                    ),
                    reason=f"Distancia requerida después de muestra {progress}/3",
                ),
            )

        if progress == 3:
            self._announce_organic_completion(
                system_address,
                body_id,
                species or genus or "esta especie",
            )

        if scan_type != "Analyse":
            return

        system_name = self.commander_state.current_system

        self._refresh_system_totals(
            system_address,
            system_name,
            timestamp,
        )

        print(
            "Exobiología           : "
            f"{species or genus or 'Muestra orgánica'} registrada"
        )

        self._publish_report(
            system_address,
            system_name,
        )

    def _announce_organic_completion(
        self,
        system_address: int,
        body_id: int | None,
        species_name: str,
    ) -> None:
        expected_rows = self.database.query(
            """
            SELECT COALESCE(MAX(signal_count), 0)
            FROM biological_signals
            WHERE system_address=? AND body_id=?
              AND source_event IN ('FSSBodySignals', 'SAASignalsFound')
              AND LOWER(COALESCE(signal_type, '')) LIKE 'biol%'
            """,
            (system_address, body_id),
        )
        completed_rows = self.database.query(
            """
            SELECT COUNT(DISTINCT COALESCE(NULLIF(species, ''), genus))
            FROM biological_signals
            WHERE system_address=? AND body_id=?
              AND source_event='ScanOrganic' AND scan_type='Analyse'
            """,
            (system_address, body_id),
        )
        expected = int(expected_rows[0][0] or 0) if expected_rows else 0
        completed = int(completed_rows[0][0] or 0) if completed_rows else 0
        remaining = max(0, expected - completed)
        message = f"Las tres muestras de {species_name} fueron recolectadas. "
        if expected > 1 and remaining > 0:
            noun = "especie" if remaining == 1 else "especies"
            message += f"Quedan {remaining} {noun} por completar en este planeta."
        elif expected > 0 and remaining == 0:
            message += "Completaste todas las especies de este planeta."
        else:
            message += "Muestreo biológico completado."
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady(
                officer="MÍMIR",
                message=message,
                reason="Especie exobiológica completada",
            ),
        )

    def _announce_star_only_system(
        self, system_address: int, system_name: str
    ) -> None:
        """Avisa una vez cuando el FSS confirma que no existen planetas."""

        if system_address in self._star_only_announced:
            return
        rows = self.database.query(
            """
            SELECT expected_body_count, discovered_body_count,
                   star_count, planet_count, moon_count, all_bodies_found
            FROM system_exploration WHERE system_address=?
            """,
            (system_address,),
        )
        if not rows:
            return
        data = rows[0]
        expected = int(data["expected_body_count"] or 0)
        stars = int(data["star_count"] or 0)
        planets = int(data["planet_count"] or 0)
        moons = int(data["moon_count"] or 0)
        if not data["all_bodies_found"] or expected <= 0:
            return
        if stars != expected or planets or moons:
            return
        self._star_only_announced.add(system_address)
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady(
                officer="MÍMIR",
                message=(
                    f"Comandante, el sistema {system_name} contiene solamente "
                    "estrellas. No hay planetas para escanear."
                ),
                reason="Sistema compuesto solamente por estrellas",
            ),
        )

    @staticmethod
    def _is_belt_cluster(event: dict) -> bool:
        """Identifica agregados de asteroides que FSS no cuenta como cuerpos."""

        body_name = str(event.get("BodyName", ""))
        return "Belt Cluster" in body_name

    @staticmethod
    def _is_biological_signal(signal: dict) -> bool:
        """Reconoce biología con código interno o cualquier localización."""

        values = (
            str(signal.get("Type", "")),
            str(signal.get("Type_Localised", "")),
        )
        for value in values:
            normalized = "".join(
                character
                for character in unicodedata.normalize("NFKD", value.lower())
                if not unicodedata.combining(character)
            )
            if "biolog" in normalized:
                return True

        return False

    @staticmethod
    def _classify_body(
        event: dict,
    ) -> tuple[str, str, int]:
        """
        Determina si el cuerpo es estrella, planeta o luna.
        """

        if event.get("StarType"):
            return (
                "Estrella",
                event.get("StarType", ""),
                0,
            )

        parents = event.get("Parents", [])

        is_moon = any(
            "Planet" in parent
            for parent in parents
            if isinstance(parent, dict)
        )

        if is_moon:
            return (
                "Luna",
                event.get("PlanetClass", ""),
                1,
            )

        return (
            "Planeta",
            event.get("PlanetClass", ""),
            0,
        )

    def _refresh_system_totals(
        self,
        system_address: int,
        system_name: str,
        timestamp: str,
    ) -> None:
        """
        Recalcula el resumen del sistema usando SQLite.
        """

        body_rows = self.database.query(
            """
            SELECT
                COUNT(*) AS discovered,
                SUM(
                    CASE WHEN body_type = 'Estrella'
                    THEN 1 ELSE 0 END
                ) AS stars,
                SUM(
                    CASE WHEN body_type = 'Planeta'
                    THEN 1 ELSE 0 END
                ) AS planets,
                SUM(
                    CASE WHEN body_type = 'Luna'
                    THEN 1 ELSE 0 END
                ) AS moons,
                SUM(terraformable) AS terraformables
            FROM stellar_bodies
            WHERE system_address = ?
              AND body_name NOT LIKE '% Belt Cluster %'
            """,
            (system_address,),
        )

        mapped_rows = self.database.query(
            """
            SELECT COUNT(*) AS mapped
            FROM mapped_bodies
            WHERE system_address = ?
            """,
            (system_address,),
        )

        biology_rows = self.database.query(
            """
            SELECT
                COALESCE(
                    SUM(
                        CASE
                            WHEN source_event IN (
                                'FSSBodySignals',
                                'SAASignalsFound'
                            )
                             AND LOWER(COALESCE(signal_type, '')) LIKE 'biol%'
                            THEN signal_count
                            ELSE 0
                        END
                    ),
                    0
                ) AS biology_signals,

                COALESCE(
                    SUM(
                        CASE
                            WHEN source_event = 'ScanOrganic'
                             AND scan_type = 'Analyse'
                            THEN 1
                            ELSE 0
                        END
                    ),
                    0
                ) AS organic_samples
            FROM biological_signals
            WHERE system_address = ?
            """,
            (system_address,),
        )

        body = body_rows[0]
        mapped = mapped_rows[0]
        biology = biology_rows[0]

        discovered = int(body["discovered"] or 0)
        stars = int(body["stars"] or 0)
        planets = int(body["planets"] or 0)
        moons = int(body["moons"] or 0)
        terraformables = int(body["terraformables"] or 0)
        mapped_count = int(mapped["mapped"] or 0)
        biology_signals = int(
            biology["biology_signals"] or 0
        )
        organic_samples = int(
            biology["organic_samples"] or 0
        )

        self.database.execute(
            """
            INSERT INTO system_exploration
            (
                system_address,
                system_name,
                discovered_body_count,
                star_count,
                planet_count,
                moon_count,
                terraformable_count,
                mapped_count,
                biology_signal_count,
                organic_sample_count,
                updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(system_address)
            DO UPDATE SET
                system_name = excluded.system_name,
                discovered_body_count =
                    excluded.discovered_body_count,
                star_count = excluded.star_count,
                planet_count = excluded.planet_count,
                moon_count = excluded.moon_count,
                terraformable_count =
                    excluded.terraformable_count,
                mapped_count = excluded.mapped_count,
                biology_signal_count =
                    excluded.biology_signal_count,
                organic_sample_count =
                    excluded.organic_sample_count,
                updated_at = excluded.updated_at
            """,
            (
                system_address,
                system_name,
                discovered,
                stars,
                planets,
                moons,
                terraformables,
                mapped_count,
                biology_signals,
                organic_samples,
                timestamp,
            ),
        )

        self.commander_state.discovered_body_count = discovered
        self.commander_state.mapped_body_count = mapped_count
        self.commander_state.biology_signal_count = biology_signals
        self.commander_state.organic_sample_count = organic_samples

    def _publish_report(
        self,
        system_address: int,
        system_name: str,
    ) -> None:
        """
        Construye y publica el informe actual del sistema.
        """

        rows = self.database.query(
            """
            SELECT *
            FROM system_exploration
            WHERE system_address = ?
            """,
            (system_address,),
        )

        if not rows:
            return

        data = rows[0]

        expected = int(
            data["expected_body_count"] or 0
        )

        discovered = int(
            data["discovered_body_count"] or 0
        )

        terraformables = int(
            data["terraformable_count"] or 0
        )

        mapped = int(
            data["mapped_count"] or 0
        )

        biological = int(
            data["biology_signal_count"] or 0
        )

        all_found = bool(
            data["all_bodies_found"]
        )

        biology_body_rows = self.database.query(
            """
            SELECT DISTINCT body_name
            FROM biological_signals
            WHERE system_address = ?
              AND body_name IS NOT NULL
              AND body_name != ''
              AND signal_count > 0
              AND LOWER(COALESCE(signal_type, '')) LIKE 'biol%'
            ORDER BY body_name
            """,
            (system_address,),
        )
        biological_bodies = tuple(
            str(row["body_name"])
            for row in biology_body_rows
        )

        reasons: list[str] = []

        if biological:
            reasons.append(
                f"{biological} señales biológicas detectadas"
            )

        if terraformables:
            reasons.append(
                f"{terraformables} cuerpos terraformables"
            )

        if all_found:
            reasons.append(
                "Todos los cuerpos fueron identificados"
            )

        if biological:
            priority = "HIGH"
            recommendation = (
                "Comandante, hay señales biológicas. "
                "Recomiendo revisar los cuerpos candidatos "
                "y realizar escaneos DSS."
            )

        elif terraformables and mapped < terraformables:
            priority = "MEDIUM"
            recommendation = (
                "Comandante, se detectaron cuerpos "
                "terraformables aún no cartografiados. "
                "Recomiendo realizar DSS."
            )

        elif all_found:
            priority = "LOW"

            if expected and discovered < expected:
                missing_records = expected - discovered

                recommendation = (
                    "Comandante, Elite confirma que todos los "
                    "cuerpos fueron identificados. "
                    f"ODIN no recibió {missing_records} "
                    "registro de escaneo durante esta sesión."
                )

                reasons.append(
                    "El estado FSS completo tiene prioridad "
                    "sobre el conteo local"
                )

            else:
                recommendation = (
                    "Comandante, la identificación del sistema "
                    "está completa."
                )

        elif expected and discovered < expected:
            priority = "MEDIUM"
            recommendation = (
                f"Comandante, quedan "
                f"{expected - discovered} cuerpos "
                "por identificar. Recomiendo continuar el FSS."
            )

        else:
            priority = "LOW"
            recommendation = (
                "Información de exploración actualizada."
            )

        report = ExplorationReportReady(
            system_name=system_name,
            expected_body_count=expected,
            discovered_body_count=discovered,
            star_count=int(data["star_count"] or 0),
            planet_count=int(data["planet_count"] or 0),
            moon_count=int(data["moon_count"] or 0),
            terraformable_count=terraformables,
            mapped_count=mapped,
            biology_signal_count=biological,
            organic_sample_count=int(
                data["organic_sample_count"] or 0
            ),
            all_bodies_found=all_found,
            priority=priority,
            recommendation=recommendation,
            reasons=reasons,
            biological_bodies=biological_bodies,
        )

        self.event_bus.publish_internal(
            InternalEvent.EXPLORATION_REPORT_READY,
            report,
        )
