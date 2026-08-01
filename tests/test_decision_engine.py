import unittest

from brain.decision_engine import DecisionEngine
from models.exploration_context import ExplorationContext


class DecisionEngineTestCase(unittest.TestCase):
    def test_edsm_system_is_reported_as_previously_registered(self) -> None:
        recommendation = DecisionEngine().evaluate_exploration(
            ExplorationContext(
                system_name="Sistema conocido",
                edsm_found=True,
            )
        )

        self.assertIn("registrado previamente en EDSM", recommendation.message)

    def test_system_absent_from_edsm_is_only_a_possible_discovery(self) -> None:
        recommendation = DecisionEngine().evaluate_exploration(
            ExplorationContext(
                system_name="Sistema desconocido",
                edsm_found=False,
            )
        )

        self.assertIn("sin registro disponible en EDSM", recommendation.message)
        self.assertIn("no es una certeza", recommendation.message)


if __name__ == "__main__":
    unittest.main()
