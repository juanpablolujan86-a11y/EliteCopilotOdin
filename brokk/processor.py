"""Interpreta los eventos mineros oficiales del Journal de Elite Dangerous."""

from __future__ import annotations

import re

from brokk.session import MiningSessionStore
from brokk.equipment import audit_mining_loadout


class MiningProcessor:
    EVENTS = (
        "Loadout", "Cargo", "CargoTransfer", "Location", "FSDJump",
        "SupercruiseEntry", "SupercruiseExit", "ProspectedAsteroid",
        "MiningRefined", "AsteroidCracked", "MaterialCollected",
        "MarketSell", "EjectCargo",
    )

    def __init__(self, store: MiningSessionStore) -> None:
        self.store = store
        self.session = store.load()

    def handle(self, event: dict) -> None:
        name = str(event.get("event", ""))
        handler = getattr(self, f"_handle_{name.casefold()}", None)
        if handler is None:
            return
        handler(event)
        self.store.save(self.session)

    def start(
        self, *, system: str = "", body: str = "", technique: str = "laser",
        target_mineral: str = "", technique_source: str = "commander",
    ) -> None:
        if self.session.status == "paused":
            self.session.resume()
            self.session.technique = technique or self.session.technique
            self.session.technique_source = (
                technique_source or self.session.technique_source
            )
            self.session.technique_confirmed = False
            if target_mineral:
                self.session.target_mineral = target_mineral
            self.store.save(self.session)
            return
        if self.session.status == "completed":
            self._prepare_new_session(
                system=system, body=body, technique=technique,
                target_mineral=target_mineral,
                technique_source=technique_source,
            )
        self.session.system = system or self.session.system
        self.session.body = body or self.session.body
        self.session.technique = technique or self.session.technique
        self.session.technique_source = technique_source or self.session.technique_source
        self.session.technique_confirmed = False
        if target_mineral:
            self.session.target_mineral = target_mineral
        if not self.session.active:
            self.session.status = "ready"
            self.session.touch()
        self.store.save(self.session)

    def pause(self) -> None:
        self.session.pause()
        self.store.save(self.session)

    def close(self) -> None:
        self.session.close()
        self.store.save(self.session)

    def _handle_location(self, event: dict) -> None:
        self._location(event)

    def _handle_loadout(self, event: dict) -> None:
        self.session.equipment = audit_mining_loadout(event).to_dict()
        self.session.touch()

    def _handle_cargo(self, event: dict) -> None:
        if str(event.get("Vessel", "Ship") or "Ship").casefold() != "ship":
            return
        if "Inventory" not in event:
            self.session.cargo_count = max(
                0, int(event.get("Count", self.session.cargo_count) or 0)
            )
            self.session.touch()
            return
        inventory: dict[str, int] = {}
        limpets = 0
        for item in event.get("Inventory", ()) or ():
            commodity = self._commodity(item)
            count = max(0, int(item.get("Count", 0) or 0))
            if not commodity or not count:
                continue
            inventory[commodity] = inventory.get(commodity, 0) + count
            if str(item.get("Name", "")).casefold() in {"drones", "$drones_name;"}:
                limpets += count
        self.session.cargo_inventory = inventory
        self.session.cargo_count = max(
            0, int(event.get("Count", sum(inventory.values())) or 0)
        )
        self.session.limpets = limpets
        # Cargo.json es la fuente autoritativa de lo que queda vendible. La
        # producción histórica permanece separada en ``produced``.
        for commodity in tuple(self.session.refined):
            actual = max(0, int(inventory.get(commodity, 0)))
            if actual:
                self.session.refined[commodity] = actual
            else:
                self.session.refined.pop(commodity, None)
        self.session.touch()

    def _handle_cargotransfer(self, event: dict) -> None:
        for transfer in event.get("Transfers", ()) or ():
            commodity = self._commodity(transfer)
            count = max(0, int(transfer.get("Count", 0) or 0))
            direction = re.sub(
                r"[^a-z]", "", str(transfer.get("Direction", "")).casefold()
            )
            if not commodity or not count:
                continue
            if direction == "tocarrier":
                available = max(0, self.session.cargo_inventory.get(commodity, 0))
                moved = min(available, count)
                if moved:
                    remaining = available - moved
                    if remaining:
                        self.session.cargo_inventory[commodity] = remaining
                    else:
                        self.session.cargo_inventory.pop(commodity, None)
                self.session.cargo_count = max(0, self.session.cargo_count - count)
                self.session.remove_refined(
                    commodity, count, self.session.transferred_to_carrier
                )
            elif direction in {"toship", "fromcarrier"}:
                self.session.cargo_inventory[commodity] = (
                    self.session.cargo_inventory.get(commodity, 0) + count
                )
                self.session.cargo_count += count
                self.session.transferred_from_carrier[commodity] = (
                    self.session.transferred_from_carrier.get(commodity, 0) + count
                )
        self.session.limpets = sum(
            count for name, count in self.session.cargo_inventory.items()
            if name.casefold() in {"drones", "dron", "limpet", "limpets"}
        )
        self.session.touch()

    def _handle_fsdjump(self, event: dict) -> None:
        if self.session.active:
            self.session.close()
        self._location(event)

    def _handle_supercruiseentry(self, _event: dict) -> None:
        if self.session.active:
            self.session.close()

    def _handle_supercruiseexit(self, event: dict) -> None:
        self._location(event)

    def _location(self, event: dict) -> None:
        self.session.system = str(event.get("StarSystem", self.session.system) or "")
        self.session.body = str(event.get("Body", event.get("BodyName", self.session.body)) or "")
        self.session.touch()

    def _handle_prospectedasteroid(self, event: dict) -> None:
        if self.session.status == "completed":
            self._prepare_new_session()
        materials = []
        for item in event.get("Materials", ()) or ():
            materials.append({
                "name": self._display_name(item),
                "proportion": float(item.get("Proportion", 0) or 0),
            })
        self.session.prospected_asteroids += 1
        self.session.last_prospect = {
            "content": str(event.get("Content_Localised", event.get("Content", "")) or ""),
            "remaining": float(event.get("Remaining", 0) or 0),
            "materials": materials,
        }
        self.session.status = "prospecting"
        self.session.touch()

    def _handle_miningrefined(self, event: dict) -> None:
        if self.session.status == "completed":
            self._prepare_new_session()
        if not self.session.active:
            self.session.start(
                system=self.session.system, body=self.session.body,
                technique=self.session.technique,
                technique_source=self.session.technique_source,
            )
        self.session.add_refined(self._commodity(event), 1)

    def _handle_asteroidcracked(self, _event: dict) -> None:
        self.session.technique = "core"
        self.session.technique_source = "journal"
        self.session.technique_confirmed = True
        self.session.cracked_asteroids += 1
        self.session.status = "extracting"
        self.session.touch()

    def _handle_materialcollected(self, event: dict) -> None:
        if str(event.get("Category", "")).casefold() != "raw":
            return
        material = self._display_name(event)
        count = max(0, int(event.get("Count", 1) or 0))
        if material and count:
            current = self.session.engineering_materials.get(material, 0)
            self.session.engineering_materials[material] = current + count
            self.session.touch()

    def _handle_marketsell(self, event: dict) -> None:
        commodity = self._commodity(event)
        count = max(0, int(event.get("Count", 0) or 0))
        removed = self.session.remove_refined(commodity, count, self.session.sold)
        if removed:
            price = max(0, int(event.get("SellPrice", 0) or 0))
            self.session.sale_revenue += removed * price
            if self.session.active:
                self.session.status = "selling"
            self.session.touch()

    def _handle_ejectcargo(self, event: dict) -> None:
        commodity = self._commodity(event)
        count = max(0, int(event.get("Count", 0) or 0))
        self.session.remove_refined(commodity, count, self.session.discarded)

    def _prepare_new_session(
        self, *, system: str = "", body: str = "", technique: str = "laser",
        target_mineral: str = "", technique_source: str = "commander",
    ) -> None:
        previous = self.session
        self.session = type(previous)(
            system=system or previous.system,
            body=body or previous.body,
            technique=technique or previous.technique,
            technique_source=technique_source,
            target_mineral=target_mineral or previous.target_mineral,
            cargo_inventory=dict(previous.cargo_inventory),
            cargo_count=previous.cargo_count,
            limpets=previous.limpets,
            equipment=dict(previous.equipment),
        )

    @classmethod
    def _commodity(cls, event: dict) -> str:
        return cls._clean_name(event.get(
            "Type_Localised",
            event.get("Type", event.get("Name_Localised", event.get("Name", ""))),
        ))

    @classmethod
    def _display_name(cls, event: dict) -> str:
        return cls._clean_name(event.get("Name_Localised", event.get("Name", event.get("Type", ""))))

    @staticmethod
    def _clean_name(value) -> str:
        text = str(value or "").strip()
        text = re.sub(r"^\$", "", text)
        text = re.sub(r"_name;$", "", text, flags=re.IGNORECASE)
        return text
