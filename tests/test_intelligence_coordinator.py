import unittest

from intelligence.coordinator import IntelligenceCoordinator


class Reply:
    text = ('{"summary":"Preparar viaje científico","steps":['
            '{"officer":"HEIMDALL","action":"calcular_ruta",'
            '"reason":"Evaluar el trayecto","requires_authorization":false},'
            '{"officer":"MÍMIR","action":"analizar",'
            '"reason":"Revisar objetivos biológicos"}]}')


class Assistant:
    def ask(self, question, context=""):
        assert "exobiología" in question
        assert context == "contexto vivo"
        return Reply()


def test_coordinator_builds_advisory_plan():
    coordinator = IntelligenceCoordinator(Assistant())
    plan = coordinator.propose("viaje de exobiología", "contexto vivo")
    assert plan.advisory_only is True
    assert [step.officer for step in plan.steps] == ["HEIMDALL", "MÍMIR"]
    assert coordinator.snapshot()["objective"] == "viaje de exobiología"


def test_coordinator_discards_unknown_or_unsafe_steps():
    response = ('{"summary":"x","steps":['
                '{"officer":"LOKI","action":"borrar","reason":"no"},'
                '{"officer":"ODIN","action":"informar","reason":"sí"}]}')
    plan = IntelligenceCoordinator.parse("consulta", response)
    assert len(plan.steps) == 1
    assert plan.steps[0].action == "informar"


def test_coordinator_rejects_plan_without_safe_steps():
    with unittest.TestCase().assertRaises(ValueError):
        IntelligenceCoordinator.parse(
            "consulta", '{"summary":"x","steps":[{"officer":"ODIN",'
            '"action":"vender","reason":"acción externa"}]}'
        )


def test_last_safe_plan_is_restored(tmp_path):
    path = tmp_path / "intelligence" / "last_plan.json"
    first = IntelligenceCoordinator(Assistant(), path)
    first.propose("viaje de exobiología", "contexto vivo")

    restored = IntelligenceCoordinator(plan_path=path)
    assert restored.snapshot()["objective"] == "viaje de exobiología"
    assert len(restored.snapshot()["steps"]) == 2
