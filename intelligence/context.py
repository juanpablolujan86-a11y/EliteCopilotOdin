"""Contexto vivo y verificable que ODIN puede usar al conversar."""

from __future__ import annotations

from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from state.commander_state import CommanderState
from heimdall.navigation import NavigationContext
from core.body_names import planet_reference


def build_live_context(
    commander: CommanderState,
    navigation: NavigationContext | None,
    balance: ExpeditionBalanceUpdated | None,
    biology_by_body: dict[str, tuple[str, ...]] | None = None,
    home_base: str = "",
) -> str:
    current_body = commander.current_body or commander.last_scanned_body
    lines = [
        f"Comandante: {commander.commander_name or 'desconocido'}",
        f"Créditos disponibles: {commander.credits}",
        f"Préstamo pendiente: {commander.loan}",
        f"Patrimonio registrado: {commander.current_wealth or 'sin datos'}",
        f"Base del comandante: {home_base or 'sin base registrada'}",
        f"Sistema actual: {commander.current_system or 'desconocido'}",
        (
            f"Cuerpo actual: {planet_reference(commander.current_system, current_body)}"
            if current_body else "Cuerpo actual: sin datos"
        ),
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
            f"Matrícula: {navigation.ship_ident or 'sin datos'}",
            f"Alcance máximo: {navigation.max_jump_range:.2f} años luz",
            f"Combustible: {navigation.fuel_main:.1f}/{navigation.fuel_capacity:.1f} toneladas",
            f"Casco: {navigation.hull_health * 100:.1f}%" if navigation.hull_health is not None else "Casco: sin datos",
            f"Carga máxima: {navigation.cargo_capacity} toneladas",
            f"Coste de recompra: {navigation.rebuy_cost} créditos",
            f"Integridad del FSD: {navigation.fsd_health * 100:.1f}%" if navigation.fsd_health is not None else "Integridad del FSD: sin datos",
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
            f"MÍMIR, cartografía disponible para vender: {balance.cartography_estimated} créditos",
            f"MÍMIR, exobiología disponible para vender, valor base: {balance.exobiology_base} créditos",
            f"MÍMIR, exobiología disponible para vender, potencial con bonificaciones: {balance.exobiology_potential} créditos",
        ))
    lines.append("Biologías probables conocidas en el sistema, sin precios:")
    if biology_by_body:
        for body, species in sorted(biology_by_body.items()):
            lines.append(
                f"- {planet_reference(commander.current_system, body)}: "
                f"{', '.join(species)}"
            )
    else:
        lines.append("- No hay predicciones biológicas disponibles.")
    return "\n".join(lines)
