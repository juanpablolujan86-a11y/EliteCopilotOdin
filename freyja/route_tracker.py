"""Seguimiento persistente de una ruta comercial calculada por FREYJA."""
from __future__ import annotations
import json
from pathlib import Path

from core.internal_events import InternalEvent
from models.events.voice_message_ready import VoiceMessageReady


class ActiveTradeRoute:
    def __init__(self, path: Path, event_bus) -> None:
        self.path = path
        self.event_bus = event_bus
        self.state = self._load()

    def activate(self, plan) -> None:
        trades = tuple(getattr(plan, "legs", ()) or ())
        if not trades:
            trade = getattr(plan, "trade", plan)
            trades = (trade,)
        legs = []
        for trade in trades:
            item = trade.opportunity
            legs.append({
                "commodity": item.commodity,
                "units": trade.units,
                "buy_system": item.buy_system,
                "buy_station": item.buy_station,
                "sell_system": item.sell_system,
                "sell_station": item.sell_station,
            })
        self.state = {"index": 0, "legs": legs}
        self._save()

    def handle_market_sell(self, event: dict) -> None:
        if not self.state:
            return
        legs = self.state["legs"]
        index = int(self.state["index"])
        if index >= len(legs):
            return
        sold = self._commodity(event.get("Type", ""))
        if sold != self._commodity(legs[index]["commodity"]):
            return
        index += 1
        if index >= len(legs):
            self.state = None
            self.path.unlink(missing_ok=True)
            message = "Ruta comercial completada, comandante."
        else:
            self.state["index"] = index
            self._save()
            leg = legs[index]
            message = (
                f"Siguiente tramo: compre {leg['units']} toneladas de "
                f"{leg['commodity']} en {leg['buy_station']}, sistema "
                f"{leg['buy_system']}, y véndalas en {leg['sell_station']}, "
                f"sistema {leg['sell_system']}."
            )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady("FREYJA", message, "progreso comercial"),
        )

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8"
        )

    def _load(self):
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("legs"), list):
                return payload
        except (OSError, ValueError, TypeError):
            pass
        return None

    @staticmethod
    def _commodity(value: str) -> str:
        return str(value).strip("$").removesuffix("_name;").casefold()
