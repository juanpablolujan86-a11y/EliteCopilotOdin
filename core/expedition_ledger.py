"""Libro persistente y aproximado de recompensas de exploración."""

from __future__ import annotations

import json
import math
from pathlib import Path

from core.database import DatabaseManager
from core.event_bus import EventBus
from core.internal_events import InternalEvent
from models.events.expedition_balance_updated import ExpeditionBalanceUpdated


class ExpeditionLedger:
    """Registra actividad, estimaciones pendientes y ventas confirmadas."""

    PLANET_VALUES = {
        "Ammonia world": 96_932,
        "Earthlike body": 64_831,
        "Water world": 64_831,
        "High metal content body": 9_654,
        "Metal rich body": 21_790,
        "Sudarsky class II gas giant": 9_654,
        "Gas giant with water based life": 64_831,
        "Gas giant with ammonia based life": 96_932,
    }

    def __init__(
        self,
        database: DatabaseManager,
        event_bus: EventBus,
        species_file: Path,
    ) -> None:
        self.database = database
        self.event_bus = event_bus
        payload = json.loads(species_file.read_text(encoding="utf-8"))
        self.species_values = {
            item["codex_id"]: int(item.get("value", 0))
            for item in payload.get("species", [])
        }

    def bootstrap(self) -> None:
        """Reconstruye estimaciones desde la memoria que ODIN ya posee."""

        for row in self.database.query("SELECT * FROM stellar_bodies"):
            event = json.loads(row["raw_json"])
            self._upsert_item(
                f"system:{row['system_address']}", "system",
                row["system_address"], row["system_name"], None,
                row["system_name"], 0, 0, row["scanned_at"],
            )
            mapped = bool(
                self.database.query(
                    "SELECT 1 FROM mapped_bodies WHERE system_address=? AND body_id=?",
                    (row["system_address"], row["body_id"]),
                )
            )
            self._store_scan(event, mapped=mapped)

        completed = self.database.query(
            """
            SELECT raw_json FROM biological_signals
            WHERE source_event='ScanOrganic' AND scan_type='Analyse'
            """
        )
        for row in completed:
            self._store_organic(json.loads(row["raw_json"]))

    def handle_fsd_jump(self, event: dict) -> None:
        address = event.get("SystemAddress")
        if address is None:
            return
        self._upsert_item(
            f"system:{address}", "system", address,
            event.get("StarSystem", ""), None, event.get("StarSystem", ""), 0, 0,
            event.get("timestamp", ""),
        )

    def handle_scan(self, event: dict) -> None:
        if "Belt Cluster" in str(event.get("BodyName", "")):
            return
        self._store_scan(event, mapped=False)

    def handle_mapping(self, event: dict) -> None:
        address = event.get("SystemAddress")
        body_id = event.get("BodyID")
        rows = self.database.query(
            "SELECT raw_json FROM stellar_bodies WHERE system_address=? AND body_id=?",
            (address, body_id),
        )
        if rows:
            scan = json.loads(rows[0]["raw_json"])
            scan["EfficiencyBonus"] = (
                int(event.get("ProbesUsed", 0))
                <= int(event.get("EfficiencyTarget", -1))
            )
            self._store_scan(scan, mapped=True)
            self.publish("DSS")

    def handle_organic(self, event: dict) -> None:
        if event.get("ScanType") != "Analyse":
            return
        self._store_organic(event)
        self.publish("Exobiología 3/3")

    def handle_fss_complete(self, _event: dict) -> None:
        self.publish("FSS completo")

    def handle_exploration_sale(self, event: dict) -> None:
        value = int(event.get("TotalEarnings", event.get("BaseValue", 0)) or 0)
        if not self._store_sale("exploration", event, value):
            return
        systems = {
            item.get("SystemName")
            for item in event.get("Discovered", [])
            if item.get("SystemName")
        }
        if systems:
            placeholders = ",".join("?" for _ in systems)
            self.database.execute(
                f"UPDATE expedition_items SET status='sold' "
                f"WHERE category='scan' AND system_name IN ({placeholders})",
                tuple(systems),
            )
        else:
            self.database.execute(
                "UPDATE expedition_items SET status='sold' WHERE category='scan' AND status='pending'"
            )
        self.publish("Venta cartográfica")

    def handle_organic_sale(self, event: dict) -> None:
        value = sum(
            int(item.get("Value", 0) or 0) + int(item.get("Bonus", 0) or 0)
            for item in event.get("BioData", [])
        )
        if not self._store_sale("exobiology", event, value):
            return
        for item in event.get("BioData", []):
            description = item.get("Variant_Localised", item.get("Species_Localised", ""))
            self.database.execute(
                """
                UPDATE expedition_items SET status='sold'
                WHERE event_key = (
                    SELECT event_key FROM expedition_items
                    WHERE category='organic' AND status='pending' AND description=?
                    ORDER BY recorded_at LIMIT 1
                )
                """,
                (description,),
            )
        self.publish("Venta exobiológica")

    def publish(self, reason: str) -> None:
        summary = self.summary(reason)
        self.event_bus.publish_internal(InternalEvent.EXPEDITION_BALANCE_UPDATED, summary)

    def summary(self, reason: str = "") -> ExpeditionBalanceUpdated:
        def scalar(sql: str, parameters: tuple = ()) -> int:
            rows = self.database.query(sql, parameters)
            return int(rows[0][0] or 0) if rows else 0

        return ExpeditionBalanceUpdated(
            systems_visited=scalar("SELECT COUNT(*) FROM expedition_items WHERE category='system'"),
            bodies_scanned=scalar("SELECT COUNT(*) FROM expedition_items WHERE category='scan'"),
            bodies_mapped=scalar("SELECT COUNT(*) FROM mapped_bodies"),
            species_completed=scalar("SELECT COUNT(*) FROM expedition_items WHERE category='organic'"),
            cartography_estimated=scalar("SELECT SUM(base_value) FROM expedition_items WHERE category='scan' AND status='pending'"),
            exobiology_base=scalar("SELECT SUM(base_value) FROM expedition_items WHERE category='organic' AND status='pending'"),
            exobiology_potential=scalar("SELECT SUM(potential_value) FROM expedition_items WHERE category='organic' AND status='pending'"),
            exploration_sold=scalar("SELECT SUM(value) FROM expedition_sales WHERE category='exploration'"),
            exobiology_sold=scalar("SELECT SUM(value) FROM expedition_sales WHERE category='exobiology'"),
            reason=reason,
        )

    def _store_scan(self, event: dict, *, mapped: bool) -> None:
        address = event.get("SystemAddress")
        body_id = event.get("BodyID")
        if address is None or body_id is None:
            return
        value = self.estimate_scan_value(event, mapped=mapped)
        self._upsert_item(
            f"scan:{address}:{body_id}", "scan", address,
            event.get("StarSystem", ""), body_id, event.get("BodyName", ""),
            value, value, event.get("timestamp", ""),
        )

    def _store_organic(self, event: dict) -> None:
        address = event.get("SystemAddress")
        body_id = event.get("Body")
        species_id = str(event.get("Species", ""))
        variant_id = str(event.get("Variant", ""))
        if address is None or body_id is None or not species_id:
            return
        base = self.species_values.get(species_id, 0)
        body_rows = self.database.query(
            "SELECT was_footfalled FROM stellar_bodies WHERE system_address=? AND body_id=?",
            (address, body_id),
        )
        first_logged = bool(body_rows) and not bool(body_rows[0]["was_footfalled"])
        potential = base * 5 if first_logged else base
        self._upsert_item(
            f"organic:{address}:{body_id}:{species_id}:{variant_id}",
            "organic", address, "", body_id,
            event.get("Variant_Localised", event.get("Species_Localised", species_id)),
            base, potential, event.get("timestamp", ""),
        )

    def _upsert_item(
        self, key: str, category: str, address, system_name: str,
        body_id, description: str, base: int, potential: int, timestamp: str,
    ) -> None:
        self.database.execute(
            """
            INSERT INTO expedition_items
            (event_key, category, system_address, system_name, body_id,
             description, base_value, potential_value, recorded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(event_key) DO UPDATE SET
                description=excluded.description,
                base_value=MAX(expedition_items.base_value, excluded.base_value),
                potential_value=MAX(expedition_items.potential_value, excluded.potential_value)
            """,
            (key, category, address, system_name, body_id, description, base, potential, timestamp),
        )

    def _store_sale(self, category: str, event: dict, value: int) -> bool:
        key = f"{category}:{event.get('timestamp', '')}:{event.get('MarketID', '')}"
        if self.database.query(
            "SELECT 1 FROM expedition_sales WHERE event_key=?", (key,)
        ):
            return False
        self.database.execute(
            """
            INSERT OR IGNORE INTO expedition_sales
            (event_key, category, value, recorded_at, raw_json)
            VALUES (?, ?, ?, ?, ?)
            """,
            (key, category, value, event.get("timestamp", ""), json.dumps(event, ensure_ascii=False)),
        )
        return True

    @classmethod
    def estimate_scan_value(cls, event: dict, *, mapped: bool) -> int:
        """Estimación comunitaria; la venta del juego es la cifra definitiva."""

        if event.get("StarType"):
            return 1_200
        planet_class = str(event.get("PlanetClass", ""))
        coefficient = cls.PLANET_VALUES.get(planet_class, 300)
        mass = max(float(event.get("MassEM", 0) or 0), 0.0001)
        value = max(500.0, coefficient + coefficient * 0.56591828 * mass ** 0.2)
        if event.get("TerraformState"):
            value *= 3.0
        if mapped:
            value *= 3.699622554 if not event.get("WasDiscovered", True) else 3.333333333
            if event.get("EfficiencyBonus"):
                value *= 1.25
        elif not event.get("WasDiscovered", True):
            value *= 2.6
        return int(round(value))
