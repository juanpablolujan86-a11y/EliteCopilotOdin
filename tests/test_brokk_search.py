import unittest
from unittest.mock import Mock

from brokk.search import (
    SpanshMiningSearchClient, normalize_mineral_query,
    select_mining_distance_tiers,
)


class Session:
    def __init__(self, payload):
        self.payload = payload
        self.last_json = None

    def post(self, _url, **kwargs):
        self.last_json = kwargs["json"]
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = self.payload
        return response


class BrokkSearchTests(unittest.TestCase):
    def test_normalizes_spanish_mineral_names_for_community_sources(self):
        self.assertEqual(normalize_mineral_query("platino"), "Platinum")
        self.assertEqual(normalize_mineral_query("  ópalos del vacío "), "Void Opal")
        self.assertEqual(normalize_mineral_query("Samarium"), "Samarium")

    def test_filters_hotspot_reserves_and_reference_system(self):
        session = Session({"results": []})
        SpanshMiningSearchClient(session).locations("Sol", "Platinum")
        payload = session.last_json
        self.assertEqual(payload["reference_system"], "Sol")
        self.assertEqual(
            payload["filters"]["ring_signals"][0]["name"], "Platinum"
        )
        self.assertEqual(
            payload["filters"]["reserve_level"]["value"],
            ["Pristine", "Major"],
        )

    def test_parses_only_ring_containing_requested_hotspot(self):
        session = Session({"results": [{
            "system_name": "Omicron Capricorni B", "name": "B 1",
            "distance": 42.0, "distance_to_arrival": 1200,
            "reserve_level": "Pristine", "signals_updated_at": "2026-08-01",
            "rings": [
                {"name": "A Ring", "type": "Metallic", "signals": {"Platinum": 2}},
                {"name": "B Ring", "type": "Rocky", "signals": {"Alexandrite": 1}},
            ],
        }]})
        result = SpanshMiningSearchClient(session).locations("Sol", "Platinum")
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0].ring, "A Ring")
        self.assertEqual(result[0].hotspot_count, 2)

    def test_selects_short_medium_and_long_options(self):
        payload = {"results": [
            _body("Corta", 50, "Major", 3),
            _body("Media", 180, "Pristine", 1),
            _body("Larga", 450, "Pristine", 2),
        ]}
        locations = SpanshMiningSearchClient(Session(payload)).locations(
            "Sol", "Platinum"
        )
        tiers = select_mining_distance_tiers(locations)
        self.assertEqual(tiers["short"].system, "Corta")
        self.assertEqual(tiers["medium"].system, "Media")
        self.assertEqual(tiers["long"].system, "Larga")


def _body(system, distance, reserves, count):
    return {
        "system_name": system, "name": f"{system} 1",
        "distance": distance, "distance_to_arrival": 100,
        "reserve_level": reserves,
        "rings": [{
            "name": f"{system} 1 A Ring", "type": "Metallic",
            "signals": [{"name": "Platinum", "count": count}],
        }],
    }


if __name__ == "__main__":
    unittest.main()
