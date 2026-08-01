"""Textos compartidos de presentación para ODIN."""


PRIORITY_LABELS = {
    "LOW": "Baja",
    "MEDIUM": "Media",
    "HIGH": "Alta",
    "CRITICAL": "Crítica",
}


def priority_label(priority: str) -> str:
    """Traduce una prioridad interna para presentarla al comandante."""

    return PRIORITY_LABELS.get(priority, priority)
