"""Contexto vivo y verificable que ODIN puede usar al conversar."""

from __future__ import annotations

from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from state.commander_state import CommanderState
from heimdall.navigation import NavigationContext


def build_live_context(
    commander: CommanderState,
    navigation: NavigationContext | None,
    balance: ExpeditionBalanceUpdated | None,
) -> str:
    lines = [
        f"Comandante: {commander.commander_name or 'desconocido'}",
        f"Sistema actual: {commander.current_system or 'desconocido'}",
        f"Cuerpo actual: {commander.current_body or commander.last_scanned_body or 'sin datos'}",
        (
            "Exploración del sistema: "
            f"{commander.discovered_body_count}/{commander.expected_body_count or '?'} cuerpos, "
            f"{commander.mapped_body_count} mapeados, "
            f"{commander.biology_signal_count} señales biológicas, "
            f"{commander.organic_sample_count} muestras orgánicas"
        ),
    ]
    if navigation is not None:
        progress = navigation.route_progress()
        lines.extend((
            f"Nave: {navigation.ship_name or navigation.ship_type or 'desconocida'}",
            f"Combustible: {navigation.fuel_main:.1f}/{navigation.fuel_capacity:.1f} toneladas",
            f"Destino: {navigation.target_system or 'sin destino fijado'}",
            (
                "Ruta: sin datos"
                if progress.remaining_jumps is None
                else f"{progress.completed_jumps} saltos realizados y {progress.remaining_jumps} restantes"
            ),
            f"Carga de cono activa: {'sí' if navigation.boost_charged else 'no'}",
        ))
    if balance is not None:
        lines.extend((
            f"Cartografía pendiente estimada: {balance.cartography_estimated} créditos",
            f"Exobiología pendiente base: {balance.exobiology_base} créditos",
            f"Exobiología potencial: {balance.exobiology_potential} créditos",
        ))
    return "\n".join(lines)
