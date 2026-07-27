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

from core.database import DatabaseManager
from core.event_bus import EventBus
from core.internal_events import InternalEvent
from models.events.exploration_report_ready import (
    ExplorationReportReady,
)
from state.commander_state import CommanderState


class ExplorationProcessor:
    """
    Capacidad central de exploración de ODIN.
    """

    def __init__(
        self,
        database: DatabaseManager,
        commander_state: CommanderState,
        event_bus: EventBus,
    ) -> None:
        self.database = database
        self.commander_state = commander_state
        self.event_bus = event_bus

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

        body_type, subtype, is_moon = self._classify_body(event)

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
                raw_json,
                scanned_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

        if body_count:
            self.commander_state.expected_body_count = body_count

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

        if not system_address:
            return

        biology_total = 0

        for signal in signals:
            signal_type = signal.get(
                "Type_Localised",
                signal.get("Type", ""),
            )

            signal_count = int(signal.get("Count", 0))

            if "biolog" in signal_type.lower():
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
                    recorded_at,
                    raw_json
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    system_address,
                    body_id,
                    body_name,
                    "SAASignalsFound",
                    signal_type,
                    signal_count,
                    timestamp,
                    json.dumps(
                        event,
                        ensure_ascii=False,
                    ),
                ),
            )

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
                signal_count,
                recorded_at,
                raw_json
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 1, ?, ?)
            """,
            (
                system_address,
                body_id,
                "ScanOrganic",
                genus,
                species,
                variant,
                scan_type,
                timestamp,
                json.dumps(
                    event,
                    ensure_ascii=False,
                ),
            ),
        )

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
                            WHEN source_event = 'SAASignalsFound'
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
        )

        self.event_bus.publish_internal(
            InternalEvent.EXPLORATION_REPORT_READY,
            report,
        )