import unittest

from brokk.performance import calculate_mining_performance
from brokk.session import MiningSession


class BrokkPerformanceTests(unittest.TestCase):
    def test_calculates_estimated_and_realized_rates_separately(self):
        session = MiningSession(
            produced={"Painita": 120},
            sale_revenue=12_000_000,
            valuation={"best_permanent": {"unit_price": 250_000}},
        )

        result = calculate_mining_performance(session, 2.0)

        self.assertEqual(result.produced_tonnes, 120)
        self.assertEqual(result.tonnes_per_hour, 60.0)
        self.assertEqual(result.estimated_value, 30_000_000)
        self.assertEqual(result.estimated_credits_per_hour, 15_000_000)
        self.assertEqual(result.realized_credits_per_hour, 6_000_000)

    def test_zero_duration_never_divides_or_invents_value(self):
        session = MiningSession(produced={"Platino": 5})
        result = calculate_mining_performance(session, 0)
        self.assertEqual(result.tonnes_per_hour, 0.0)
        self.assertEqual(result.estimated_credits_per_hour, 0.0)


if __name__ == "__main__":
    unittest.main()
