"""
ODIN - Orbital Data Intelligence Nexus

internal_events.py

Define los nombres de los eventos internos generados por ODIN.
"""


class InternalEvent:
    """
    Catálogo central de eventos internos.

    Evita usar textos escritos a mano por todo el proyecto.
    """

    SYSTEM_ENTERED = "SystemEntered"

    EXPLORATION_CONTEXT_READY = "ExplorationContextReady"

    EXPLORATION_REPORT_READY = "ExplorationReportReady"

    RECOMMENDATION_READY = "RecommendationReady"

    COMMANDER_STATE_UPDATED = "CommanderStateUpdated"

    MISSION_STARTED = "MissionStarted"

    MISSION_COMPLETED = "MissionCompleted"

    VOICE_MESSAGE_READY = "VoiceMessageReady"

    BIOLOGY_DETECTED = "BiologyDetected"

    DOCKING_REQUESTED = "DockingRequested"