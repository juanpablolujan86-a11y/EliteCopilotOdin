"""Contexto vivo y verificable que ODIN puede usar al conversar."""

from __future__ import annotations

from models.events.expedition_balance_updated import ExpeditionBalanceUpdated
from state.commander_state import CommanderState
from heimdall.navigation import NavigationContext
from core.body_names import planet_reference
from core.localization import normalize_language

_CONTEXT = {
    "es": {
        "unknown": "desconocido", "no_data": "sin datos", "no_base": "sin base registrada",
        "commander": "Comandante", "credits": "Créditos disponibles", "loan": "Préstamo pendiente",
        "wealth": "Patrimonio registrado", "base": "Base del comandante", "system": "Sistema actual",
        "body": "Cuerpo actual", "exploration": "Exploración del sistema", "bodies": "cuerpos",
        "mapped": "mapeados", "signals": "señales biológicas", "samples": "muestras orgánicas",
        "ship": "Nave", "ident": "Matrícula", "range": "Alcance máximo", "light_years": "años luz",
        "fuel": "Combustible", "tons": "toneladas", "hull": "Casco", "cargo": "Carga máxima",
        "rebuy": "Coste de recompra", "fsd": "Integridad del FSD", "destination": "Destino",
        "no_destination": "sin destino fijado", "route_none": "Ruta: sin datos", "route": "Ruta",
        "jumps_done": "saltos realizados", "remaining": "restantes", "boost": "Carga de cono activa",
        "yes": "sí", "no": "no", "cartography": "MÍMIR, cartografía disponible para vender",
        "and": "y", "credits_unit": "créditos",
        "exo_base": "MÍMIR, exobiología disponible para vender, valor base",
        "exo_potential": "MÍMIR, exobiología disponible para vender, potencial con bonificaciones",
        "biology": "Biologías probables conocidas en el sistema, sin precios:",
        "no_biology": "- No hay predicciones biológicas disponibles.",
    },
    "en": {
        "unknown": "unknown", "no_data": "no data", "no_base": "no registered base",
        "commander": "Commander", "credits": "Available credits", "loan": "Outstanding loan",
        "wealth": "Recorded wealth", "base": "Commander base", "system": "Current system",
        "body": "Current body", "exploration": "System exploration", "bodies": "bodies",
        "mapped": "mapped", "signals": "biological signals", "samples": "organic samples",
        "ship": "Ship", "ident": "Registration", "range": "Maximum range", "light_years": "light-years",
        "fuel": "Fuel", "tons": "tons", "hull": "Hull", "cargo": "Cargo capacity",
        "rebuy": "Rebuy cost", "fsd": "FSD integrity", "destination": "Destination",
        "no_destination": "no destination set", "route_none": "Route: no data", "route": "Route",
        "jumps_done": "jumps completed", "remaining": "remaining", "boost": "Jet-cone boost charged",
        "yes": "yes", "no": "no", "cartography": "MÍMIR, cartography available for sale",
        "and": "and", "credits_unit": "credits",
        "exo_base": "MÍMIR, exobiology available for sale, base value",
        "exo_potential": "MÍMIR, exobiology available for sale, potential with bonuses",
        "biology": "Known probable biology in this system, without prices:",
        "no_biology": "- No biological predictions are available.",
    },
    "pt": {
        "unknown": "desconhecido", "no_data": "sem dados", "no_base": "sem base registrada",
        "commander": "Comandante", "credits": "Créditos disponíveis", "loan": "Empréstimo pendente",
        "wealth": "Patrimônio registrado", "base": "Base do comandante", "system": "Sistema atual",
        "body": "Corpo atual", "exploration": "Exploração do sistema", "bodies": "corpos",
        "mapped": "mapeados", "signals": "sinais biológicos", "samples": "amostras orgânicas",
        "ship": "Nave", "ident": "Matrícula", "range": "Alcance máximo", "light_years": "anos-luz",
        "fuel": "Combustível", "tons": "toneladas", "hull": "Casco", "cargo": "Capacidade de carga",
        "rebuy": "Custo de recompra", "fsd": "Integridade do FSD", "destination": "Destino",
        "no_destination": "sem destino definido", "route_none": "Rota: sem dados", "route": "Rota",
        "jumps_done": "saltos concluídos", "remaining": "restantes", "boost": "Carga de cone ativa",
        "yes": "sim", "no": "não", "cartography": "MÍMIR, cartografia disponível para venda",
        "and": "e", "credits_unit": "créditos",
        "exo_base": "MÍMIR, exobiologia disponível para venda, valor base",
        "exo_potential": "MÍMIR, exobiologia disponível para venda, potencial com bônus",
        "biology": "Biologias prováveis conhecidas neste sistema, sem preços:",
        "no_biology": "- Não há previsões biológicas disponíveis.",
    },
}


def build_live_context(
    commander: CommanderState,
    navigation: NavigationContext | None,
    balance: ExpeditionBalanceUpdated | None,
    biology_by_body: dict[str, tuple[str, ...]] | None = None,
    home_base: str = "",
    language: str = "es-419",
) -> str:
    locale = normalize_language(language).split("-", 1)[0]
    labels = _CONTEXT.get(locale, _CONTEXT["es"])
    def body_reference(value: str) -> str:
        reference = planet_reference(commander.current_system, value)
        return reference.replace("planeta ", "planet ", 1) if locale == "en" else reference
    current_body = commander.current_body or commander.last_scanned_body
    lines = [
        f"{labels['commander']}: {commander.commander_name or labels['unknown']}",
        f"{labels['credits']}: {commander.credits}", f"{labels['loan']}: {commander.loan}",
        f"{labels['wealth']}: {commander.current_wealth or labels['no_data']}",
        f"{labels['base']}: {home_base or labels['no_base']}",
        f"{labels['system']}: {commander.current_system or labels['unknown']}",
        (
            f"{labels['body']}: {body_reference(current_body)}"
            if current_body else f"{labels['body']}: {labels['no_data']}"
        ),
        (
            f"{labels['exploration']}: {commander.discovered_body_count}/"
            f"{commander.expected_body_count or '?'} {labels['bodies']}, "
            f"{commander.mapped_body_count} {labels['mapped']}, "
            f"{commander.biology_signal_count} {labels['signals']}, "
            f"{commander.organic_sample_count} {labels['samples']}"
        ),
    ]
    if navigation is not None:
        progress = navigation.route_progress()
        lines.extend((
            f"{labels['ship']}: {navigation.ship_name or navigation.ship_type or labels['unknown']}",
            f"{labels['ident']}: {navigation.ship_ident or labels['no_data']}",
            f"{labels['range']}: {navigation.max_jump_range:.2f} {labels['light_years']}",
            f"{labels['fuel']}: {navigation.fuel_main:.1f}/{navigation.fuel_capacity:.1f} {labels['tons']}",
            f"{labels['hull']}: {navigation.hull_health * 100:.1f}%" if navigation.hull_health is not None else f"{labels['hull']}: {labels['no_data']}",
            f"{labels['cargo']}: {navigation.cargo_capacity} {labels['tons']}",
            f"{labels['rebuy']}: {navigation.rebuy_cost} {labels['credits_unit']}",
            f"{labels['fsd']}: {navigation.fsd_health * 100:.1f}%" if navigation.fsd_health is not None else f"{labels['fsd']}: {labels['no_data']}",
            f"{labels['destination']}: {navigation.target_system or labels['no_destination']}",
            (
                labels["route_none"]
                if progress.remaining_jumps is None
                else f"{labels['route']}: {progress.completed_jumps} {labels['jumps_done']} {labels['and']} {progress.remaining_jumps} {labels['remaining']}"
            ),
            f"{labels['boost']}: {labels['yes'] if navigation.boost_charged else labels['no']}",
        ))
    if balance is not None:
        lines.extend((
            f"{labels['cartography']}: {balance.cartography_estimated} {labels['credits_unit']}",
            f"{labels['exo_base']}: {balance.exobiology_base} {labels['credits_unit']}",
            f"{labels['exo_potential']}: {balance.exobiology_potential} {labels['credits_unit']}",
        ))
    lines.append(labels["biology"])
    if biology_by_body:
        for body, species in sorted(biology_by_body.items()):
            lines.append(
                f"- {body_reference(body)}: "
                f"{', '.join(species)}"
            )
    else:
        lines.append(labels["no_biology"])
    return "\n".join(lines)
