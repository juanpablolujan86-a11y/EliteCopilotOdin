"""Catálogo visible de ejemplos de órdenes de voz admitidas por ODIN."""

from __future__ import annotations

from core.localization import normalize_language


_SPANISH = (
    ("ODIN · CONSULTAS", (
        "¿Estás activo?",
        "¿Cuántos créditos tengo?",
        "¿Cuánto combustible tengo?",
        "¿Qué nave estoy usando?",
        "¿Cuáles son los datos de mi nave?",
        "¿Hay exobiología en este sistema?",
        "¿Cuáles son las biologías probables?",
        "¿Hay geología en este sistema?",
        "Confirma esta orden",
        "Olvida esta orden",
    )),
    ("MÍMIR · CIENCIA", (
        "¿Qué biologías probables hay en este sistema?",
        "¿En qué planetas hay biología?",
        "¿Cuántas muestras faltan?",
        "¿Ya puedo tomar la siguiente muestra?",
        "¿Cuál es el valor estimado de la expedición?",
    )),
    ("NJÖRÐR · NAVEGACIÓN", (
        "Llévame a casa",
        "Calcula una ruta de neutrones a [sistema]",
        "¿Cuántos saltos faltan?",
        "Solicita atraque",
        "Enciende las luces",
        "Activa la visión nocturna",
        "Colector de carga",
        "Tren de aterrizaje",
        "Hipersalto",
        "Enciende las luces del SRV",
        "Activa la visión nocturna del SRV",
        "Colector de carga del Scarab",
        "¿Cuántas inyecciones FSD puedo fabricar?",
        "¿Puedo saltar [distancia] años luz con una inyección?",
        "¿Necesito alguna inyección en esta ruta?",
        "Autorizo la inyección FSD",
    )),
    ("FREYJA · COMERCIO", (
        "Quiero comerciar",
        "Opción uno · ruta rápida",
        "Opción dos · tres estaciones",
        "Opción tres · expedición comercial",
        "Opción cuatro · territorio Powerplay",
        "¿Cuál es el estado de la ruta comercial?",
        "¿Cuál es la ganancia comercial acumulada?",
        "Recalcula la ruta comercial",
        "Cancela la ruta comercial",
    )),
    ("BROKK · MINERÍA", (
        "Quiero minar [mineral]",
        "¿Cuál es mi estado de minería?",
        "¿Cuánto mineral llevo?",
        "¿Dónde puedo vender la carga minera?",
    )),
)

_ENGLISH = (
    ("ODIN · QUERIES", (
        "Are you active?", "How many credits do I have?", "How much fuel do I have?",
        "What ship am I flying?", "What are my ship details?",
        "Is there exobiology in this system?", "What biology is probable?",
        "Is there geology in this system?", "Confirm this command", "Forget this command",
    )),
    ("MÍMIR · SCIENCE", (
        "What probable biology is in this system?", "Which planets have biology?",
        "How many samples remain?", "Can I take the next sample?",
        "What is the estimated expedition value?",
    )),
    ("NJÖRÐR · NAVIGATION", (
        "Take me home", "Calculate a neutron route to [system]", "How many jumps remain?",
        "Request docking", "Turn on the lights", "Turn on night vision", "Cargo scoop",
        "Landing gear", "Hyperspace jump", "Turn on the SRV lights",
        "Turn on SRV night vision", "Scarab cargo scoop",
        "How many FSD injections can I craft?",
        "Can I jump [distance] light-years with an injection?",
        "Do I need an injection on this route?", "Authorize FSD injection",
    )),
    ("FREYJA · TRADING", (
        "I want to trade", "Option one · quick route", "Option two · three stations",
        "Option three · trade expedition", "Option four · Powerplay territory",
        "What is the trade route status?", "What is my accumulated trading profit?",
        "Recalculate the trade route", "Cancel the trade route",
    )),
    ("BROKK · MINING", (
        "I want to mine [mineral]", "What is my mining status?",
        "How much mineral am I carrying?", "Where can I sell my mining cargo?",
    )),
)

_PORTUGUESE = (
    ("ODIN · CONSULTAS", (
        "Você está ativo?", "Quantos créditos eu tenho?", "Quanto combustível eu tenho?",
        "Qual nave estou usando?", "Quais são os dados da minha nave?",
        "Há exobiologia neste sistema?", "Quais biologias são prováveis?",
        "Há geologia neste sistema?", "Confirme este comando", "Esqueça este comando",
    )),
    ("MÍMIR · CIÊNCIA", (
        "Quais biologias prováveis existem neste sistema?", "Quais planetas têm biologia?",
        "Quantas amostras faltam?", "Já posso coletar a próxima amostra?",
        "Qual é o valor estimado da expedição?",
    )),
    ("NJÖRÐR · NAVEGAÇÃO", (
        "Leve-me para casa", "Calcule uma rota de nêutrons para [sistema]",
        "Quantos saltos faltam?", "Solicite atracação", "Acenda as luzes",
        "Ative a visão noturna", "Coletor de carga", "Trem de pouso", "Hipersalto",
        "Acenda as luzes do SRV", "Ative a visão noturna do SRV",
        "Coletor de carga do Scarab", "Quantas injeções FSD posso fabricar?",
        "Posso saltar [distância] anos-luz com uma injeção?",
        "Preciso de uma injeção nesta rota?", "Autorizo a injeção FSD",
    )),
    ("FREYJA · COMÉRCIO", (
        "Quero comerciar", "Opção um · rota rápida", "Opção dois · três estações",
        "Opção três · expedição comercial", "Opção quatro · território Powerplay",
        "Qual é o estado da rota comercial?", "Qual é o lucro comercial acumulado?",
        "Recalcule a rota comercial", "Cancele a rota comercial",
    )),
    ("BROKK · MINERAÇÃO", (
        "Quero minerar [mineral]", "Qual é o meu estado de mineração?",
        "Quanto mineral estou carregando?", "Onde posso vender a carga de mineração?",
    )),
)


def voice_command_catalog(language: str) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Devuelve ejemplos localizados sin mezclar textos con la lógica de voz."""

    selected = normalize_language(language)
    if selected.startswith("en-"):
        return _ENGLISH
    if selected == "pt-BR":
        return _PORTUGUESE
    return _SPANISH
