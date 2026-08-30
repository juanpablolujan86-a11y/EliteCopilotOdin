import unittest
from datetime import datetime, timezone

from brokk.valuation import (
    SpanshMiningValuationClient, select_permanent_options,
    select_distance_tiers, select_recommended_destination,
)


class Response:
    def raise_for_status(self): pass
    def json(self):
        return {"results": [
            {"system_name": "A", "name": "Carrier", "type": "Drake-Class Carrier",
             "has_large_pad": True, "distance": 1, "distance_to_arrival": 10,
             "market_updated_at": "2026-08-15", "market": [
                 {"commodity": "Painite", "sell_price": 200000, "demand": 1000}]},
            {"system_name": "B", "name": "Orbital", "type": "Orbis Starport",
             "has_large_pad": True, "distance": 4, "distance_to_arrival": 500,
             "market_updated_at": "2026-08-15", "market": [
                 {"commodity": "Painite", "sell_price": 100000, "demand": 1500}]},
            {"system_name": "C", "name": "Low demand", "type": "Coriolis Starport",
             "has_large_pad": True, "market": [
                 {"commodity": "Painite", "sell_price": 300000, "demand": 20}]},
        ]}


class Session:
    def get(self, *args, **kwargs): return Response()
    def post(self, *args, **kwargs): return Response()


class MiningValuationTests(unittest.TestCase):
    def test_permanent_station_precedes_carrier_and_demand_covers_load(self):
        result = SpanshMiningValuationClient(Session()).destinations(
            "GCRV 1568", "Painite", 208
        )
        self.assertEqual([item.station for item in result], ["Orbital", "Carrier"])
        self.assertEqual(result[0].estimated_value, 20_800_000)

    def test_recommendation_requires_large_pad_and_prefers_five_loads_demand(self):
        result = SpanshMiningValuationClient(Session()).destinations(
            "GCRV 1568", "Painite", 208
        )
        selected = select_recommended_destination(
            result, now=datetime(2026, 8, 15, tzinfo=timezone.utc)
        )
        self.assertEqual(selected.station, "Orbital")

    def test_global_search_uses_five_loads_as_minimum_demand(self):
        session = Session()
        SpanshMiningValuationClient(session).global_destinations(
            "Painite", 208, (1.0, 2.0, 3.0)
        )

    def test_global_options_exclude_destinations_beyond_nine_hundred_ly(self):
        result = SpanshMiningValuationClient(Session()).destinations(
            "GCRV 1568", "Painite", 208
        )
        options = select_permanent_options(
            result, max_distance_ly=3.0,
            now=datetime(2026, 8, 15, tzinfo=timezone.utc),
        )
        self.assertEqual(options, ())

    def test_distance_tiers_choose_one_safe_station_per_range(self):
        result = SpanshMiningValuationClient(Session()).destinations(
            "GCRV 1568", "Painite", 208
        )
        tiers = select_distance_tiers(
            result, now=datetime(2026, 8, 15, tzinfo=timezone.utc)
        )
        self.assertEqual(tiers["short"].station, "Orbital")
        self.assertNotIn("medium", tiers)
        self.assertNotIn("long", tiers)


if __name__ == "__main__":
    unittest.main()
