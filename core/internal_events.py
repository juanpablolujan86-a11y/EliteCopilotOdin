# ============================================================
# ODIN
#
# Versión : 0.3.0
#
# Sprint  : 4 - CORE
# ============================================================

"""
ODIN - Orbital Data Intelligence Nexus

internal_events.py

Define los nombres de los eventos internos generados por ODIN.
"""


class InternalEvent:
    """
    Catálogo central de eventos internos.

    Evita usar textos escritos manualmente
    en diferentes partes del proyecto.
    """

    SYSTEM_ENTERED = "SystemEntered"

    EXPLORATION_CONTEXT_READY = "ExplorationContextReady"

    EXPLORATION_REPORT_READY = "ExplorationReportReady"

    PLANET_SCAN_READY = "PlanetScanReady"

    SCIENTIFIC_ANALYSIS_READY = "ScientificAnalysisReady"

    RECOMMENDATION_READY = "RecommendationReady"

    COMMANDER_STATE_UPDATED = "CommanderStateUpdated"

    MISSION_STARTED = "MissionStarted"

    MISSION_COMPLETED = "MissionCompleted"

    VOICE_MESSAGE_READY = "VoiceMessageReady"

    BIOLOGY_DETECTED = "BiologyDetected"

    ORGANIC_SCAN_UPDATED = "OrganicScanUpdated"

    DOCKING_REQUESTED = "DockingRequested"
