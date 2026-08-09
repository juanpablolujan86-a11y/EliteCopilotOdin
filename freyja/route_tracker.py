"""Seguimiento persistente de una ruta comercial calculada por FREYJA."""
from __future__ import annotations
import json
from pathlib import Path

from core.internal_events import InternalEvent
from heimdall.clipboard import write_text
from models.events.voice_message_ready import VoiceMessageReady


class ActiveTradeRoute:
    def __init__(self, path: Path, event_bus, clipboard_writer=write_text) -> None:
        self.path = path
        self.event_bus = event_bus
        self.clipboard_writer = clipboard_writer
        self.state = self._load()

    def activate(self, plan, strategy: str = "quick") -> None:
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
        self.state = {
            "index": 0, "phase": "to_buy", "last_arrival": "",
            "strategy": strategy, "legs": legs,
        }
        self._save()
        if legs:
            self.clipboard_writer(legs[0]["buy_system"])

    def handle_market_buy(self, event: dict) -> None:
        leg = self._current_leg()
        if leg is None or self._commodity(event.get("Type", "")) != self._commodity(
            leg["commodity"]
        ):
            return
        count = max(0, int(event.get("Count", leg["units"]) or 0))
        self.state["bought_units"] = int(self.state.get("bought_units", 0)) + count
        self.state["sold_units"] = 0
        self.state["phase"] = "to_sell"
        self.state["last_arrival"] = ""
        self._save()
        self.clipboard_writer(leg["sell_system"])
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady(
                "FREYJA",
                f"Compra confirmada. Copié {leg['sell_system']} al portapapeles "
                f"como sistema de venta para {leg['sell_station']}.",
                "compra comercial confirmada",
            ),
        )

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
        if self.state.get("phase", "to_buy") != "to_sell":
            return
        target = int(self.state.get("bought_units", legs[index]["units"]) or 0)
        sold_units = int(self.state.get("sold_units", 0)) + max(
            0, int(event.get("Count", target) or 0)
        )
        self.state["sold_units"] = sold_units
        if sold_units < target:
            self._save()
            remaining = target - sold_units
            self.event_bus.publish_internal(
                InternalEvent.VOICE_MESSAGE_READY,
                VoiceMessageReady(
                    "FREYJA",
                    f"Venta parcial confirmada. Quedan {remaining} toneladas "
                    f"de {legs[index]['commodity']} por vender.",
                    "venta comercial parcial",
                ),
            )
            return
        index += 1
        if index >= len(legs):
            self.state = None
            self.path.unlink(missing_ok=True)
            message = "Ruta comercial completada, comandante."
        else:
            self.state["index"] = index
            self.state["phase"] = "to_buy"
            self.state["last_arrival"] = ""
            self.state["bought_units"] = 0
            self.state["sold_units"] = 0
            self._save()
            leg = legs[index]
            self.clipboard_writer(leg["buy_system"])
            message = (
                f"Siguiente tramo: compre {leg['units']} toneladas de "
                f"{leg['commodity']} en {leg['buy_station']}, sistema "
                f"{leg['buy_system']}, y véndalas en {leg['sell_station']}, "
                f"sistema {leg['sell_system']}. Copié {leg['buy_system']} "
                "al portapapeles."
            )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady("FREYJA", message, "progreso comercial"),
        )

    def handle_fsd_jump(self, event: dict) -> None:
        leg = self._current_leg()
        if leg is None:
            return
        phase = self.state.get("phase", "to_buy")
        target_key = "buy_system" if phase == "to_buy" else "sell_system"
        arrived = str(event.get("StarSystem", "") or "")
        if arrived.casefold() != str(leg[target_key]).casefold():
            return
        arrival_key = f"{phase}:{arrived.casefold()}"
        if self.state.get("last_arrival") == arrival_key:
            return
        self.state["last_arrival"] = arrival_key
        self._save()
        if phase == "to_buy":
            message = (
                f"Llegamos al sistema de compra. Diríjase a {leg['buy_station']} "
                f"y compre {leg['units']} toneladas de {leg['commodity']}."
            )
        else:
            message = (
                f"Llegamos al sistema de venta. Diríjase a {leg['sell_station']} "
                f"y venda {leg['units']} toneladas de {leg['commodity']}."
            )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady("FREYJA", message, "llegada comercial"),
        )

    def handle_docked(self, event: dict) -> None:
        leg = self._current_leg()
        if leg is None:
            return
        phase = self.state.get("phase", "to_buy")
        station_key = "buy_station" if phase == "to_buy" else "sell_station"
        station = str(event.get("StationName", "") or "")
        if station.casefold() != str(leg[station_key]).casefold():
            return
        dock_key = f"docked:{phase}:{station.casefold()}"
        if self.state.get("last_docked") == dock_key:
            return
        self.state["last_docked"] = dock_key
        self._save()
        action = "Compre" if phase == "to_buy" else "Venda"
        message = (
            f"Atraque confirmado en {station}. {action} "
            f"{leg['units']} toneladas de {leg['commodity']}."
        )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady("FREYJA", message, "atraque comercial"),
        )

    def status_message(self) -> str:
        leg = self._current_leg()
        if leg is None:
            return "No hay una ruta comercial activa, comandante."
        index = int(self.state.get("index", 0))
        total = len(self.state.get("legs", []))
        if self.state.get("phase", "to_buy") == "to_buy":
            action = (
                f"compre {leg['units']} toneladas de {leg['commodity']} en "
                f"{leg['buy_station']}, sistema {leg['buy_system']}"
            )
        else:
            remaining = max(
                0,
                int(self.state.get("bought_units", leg["units"]))
                - int(self.state.get("sold_units", 0)),
            )
            action = (
                f"venda {remaining} toneladas de {leg['commodity']} en "
                f"{leg['sell_station']}, sistema {leg['sell_system']}"
            )
        return f"Tramo {index + 1} de {total}: {action}."

    def cancel(self) -> bool:
        if not self.state:
            return False
        self.state = None
        self.path.unlink(missing_ok=True)
        return True

    def active_strategy(self) -> str | None:
        if not self.state:
            return None
        strategy = str(self.state.get("strategy", "") or "")
        return strategy if strategy in {
            "quick", "three_station", "expedition", "powerplay"
        } else None

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

    def _current_leg(self):
        if not self.state:
            return None
        index = int(self.state.get("index", 0))
        legs = self.state.get("legs", [])
        return legs[index] if 0 <= index < len(legs) else None

    @staticmethod
    def _commodity(value: str) -> str:
        return str(value).strip("$").removesuffix("_name;").casefold()
