"""Seguimiento persistente de una ruta comercial calculada por FREYJA."""
from __future__ import annotations
import json
from pathlib import Path

from core.internal_events import InternalEvent
from heimdall.clipboard import write_text
from models.events.voice_message_ready import VoiceMessageReady
from core.localization import text as localized_text


class ActiveTradeRoute:
    def __init__(
        self, path: Path, event_bus, clipboard_writer=write_text, diagnostics=None,
        language: str = "es-419",
    ) -> None:
        self.path = path
        self.event_bus = event_bus
        self.clipboard_writer = clipboard_writer
        self.diagnostics = diagnostics
        self.language = language
        self.state = self._load()
        if self.state:
            self._record(
                "recuperada",
                tramo=int(self.state.get("index", 0)) + 1,
                fase=self.state.get("phase", "to_buy"),
                total=len(self.state.get("legs", [])),
            )

    def _t(self, key: str, **values) -> str:
        return localized_text(key, self.language, **values)

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
                "planned_buy_price": int(getattr(item, "buy_price", 0) or 0),
                "planned_sell_price": int(getattr(item, "sell_price", 0) or 0),
            })
        self.state = {
            "index": 0, "phase": "to_buy", "last_arrival": "",
            "strategy": strategy,
            "estimated_profit": int(getattr(plan, "estimated_profit",
                getattr(getattr(plan, "trade", None), "estimated_profit", 0)) or 0),
            "legs": legs,
        }
        self._save()
        self._record("activada", estrategia=strategy, tramos=len(legs),
                     beneficio_estimado=self.state["estimated_profit"])
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
        actual_buy_price = int(event.get("BuyPrice", 0) or 0)
        planned_sell_price = int(leg.get("planned_sell_price", 0) or 0)
        projected_margin = (
            (planned_sell_price - actual_buy_price) / actual_buy_price
            if actual_buy_price > 0 else 0.0
        )
        self.state["actual_buy_price"] = actual_buy_price
        self.state["projected_margin"] = projected_margin
        self._save()
        self._record("compra", producto=leg["commodity"], cantidad=count,
                     objetivo=leg["units"], sistema_venta=leg["sell_system"])
        self.clipboard_writer(leg["sell_system"])
        if self.state.get("strategy") == "powerplay":
            message = self._t(
                "freyja.route.powerplay_purchase",
                margin=projected_margin * 100,
            )
        else:
            message = self._t(
                "freyja.route.purchase", system=leg["sell_system"],
                station=leg["sell_station"],
            )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady(
                "FREYJA",
                message,
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
            self._record("venta_parcial", producto=legs[index]["commodity"],
                         vendido=sold_units, restante=remaining)
            self.event_bus.publish_internal(
                InternalEvent.VOICE_MESSAGE_READY,
                VoiceMessageReady(
                    "FREYJA",
                    self._t("freyja.route.partial_sale", remaining=remaining,
                            commodity=legs[index]["commodity"]),
                    "venta comercial parcial",
                ),
            )
            return
        index += 1
        if index >= len(legs):
            completed = legs[index - 1]
            self.state = None
            self.path.unlink(missing_ok=True)
            self._record("completada", producto=completed["commodity"],
                         tramos=len(legs))
            message = self._t("freyja.route.completed")
        else:
            self.state["index"] = index
            self.state["phase"] = "to_buy"
            self.state["last_arrival"] = ""
            self.state["bought_units"] = 0
            self.state["sold_units"] = 0
            self._save()
            leg = legs[index]
            self._record("tramo_completado", tramo=index, siguiente=index + 1,
                         total=len(legs), siguiente_producto=leg["commodity"])
            self.clipboard_writer(leg["buy_system"])
            message = self._t(
                "freyja.route.next_leg", units=leg["units"],
                commodity=leg["commodity"], buy_station=leg["buy_station"],
                buy_system=leg["buy_system"], sell_station=leg["sell_station"],
                sell_system=leg["sell_system"],
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
        self._record("llegada", fase=phase, sistema=arrived,
                     producto=leg["commodity"])
        if phase == "to_buy":
            message = self._t(
                "freyja.route.arrived_buy", station=leg["buy_station"],
                units=leg["units"], commodity=leg["commodity"],
            )
        else:
            message = self._t(
                "freyja.route.arrived_sell", station=leg["sell_station"],
                units=leg["units"], commodity=leg["commodity"],
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
        self._record("atraque", fase=phase, estacion=station,
                     producto=leg["commodity"])
        message = self._t(
            "freyja.route.docked_buy" if phase == "to_buy" else
            "freyja.route.docked_sell", station=station, units=leg["units"],
            commodity=leg["commodity"],
        )
        self.event_bus.publish_internal(
            InternalEvent.VOICE_MESSAGE_READY,
            VoiceMessageReady("FREYJA", message, "atraque comercial"),
        )

    def status_message(self) -> str:
        leg = self._current_leg()
        if leg is None:
            return self._t("freyja.route.none")
        index = int(self.state.get("index", 0))
        total = len(self.state.get("legs", []))
        if self.state.get("phase", "to_buy") == "to_buy":
            action = self._t(
                "freyja.route.action_buy", units=leg["units"],
                commodity=leg["commodity"], station=leg["buy_station"],
                system=leg["buy_system"],
            )
        else:
            remaining = max(
                0,
                int(self.state.get("bought_units", leg["units"]))
                - int(self.state.get("sold_units", 0)),
            )
            action = self._t(
                "freyja.route.action_sell", units=remaining,
                commodity=leg["commodity"], station=leg["sell_station"],
                system=leg["sell_system"],
            )
        remaining_legs = max(0, total - index)
        estimated_profit = int(self.state.get("estimated_profit", 0) or 0)
        return self._t(
            "freyja.route.status", current=index + 1, total=total,
            action=action, remaining=remaining_legs, profit=estimated_profit,
        )

    def cancel(self) -> bool:
        if not self.state:
            return False
        index = int(self.state.get("index", 0))
        phase = self.state.get("phase", "to_buy")
        self.state = None
        self.path.unlink(missing_ok=True)
        self._record("cancelada", tramo=index + 1, fase=phase)
        return True

    def cancellation_warning(self) -> str | None:
        blocker = self.recalculation_blocker()
        if blocker is None:
            return None
        leg = self._current_leg()
        remaining = max(0, int(self.state.get("bought_units", leg["units"]))
                        - int(self.state.get("sold_units", 0)))
        return self._t("freyja.route.cancel_warning", remaining=remaining,
                       commodity=leg["commodity"])

    def active_strategy(self) -> str | None:
        if not self.state:
            return None
        strategy = str(self.state.get("strategy", "") or "")
        return strategy if strategy in {
            "quick", "three_station", "expedition", "powerplay"
        } else None

    def recalculation_blocker(self) -> str | None:
        if not self.state:
            return None
        if self.state.get("phase", "to_buy") == "to_sell":
            leg = self._current_leg()
            remaining = max(
                0,
                int(self.state.get("bought_units", leg["units"]))
                - int(self.state.get("sold_units", 0)),
            )
            return self._t("freyja.route.recalc_blocker", remaining=remaining,
                           commodity=leg["commodity"])
        return None

    def _save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")
        temporary_path.write_text(
            json.dumps(self.state, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        temporary_path.replace(self.path)

    def _load(self):
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if isinstance(payload, dict) and isinstance(payload.get("legs"), list):
                return payload
        except FileNotFoundError:
            pass
        except (OSError, ValueError, TypeError) as error:
            self._record(
                "recuperacion_fallida",
                tipo=type(error).__name__,
                detalle=str(error),
            )
        return None

    def _current_leg(self):
        if not self.state:
            return None
        index = int(self.state.get("index", 0))
        legs = self.state.get("legs", [])
        return legs[index] if 0 <= index < len(legs) else None

    def _record(self, action: str, **details) -> None:
        if self.diagnostics is not None:
            self.diagnostics.record_route_event(action, **details)

    @staticmethod
    def _commodity(value: str) -> str:
        return str(value).strip("$").removesuffix("_name;").casefold()
