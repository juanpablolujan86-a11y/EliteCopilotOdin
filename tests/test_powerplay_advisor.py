import unittest
from types import SimpleNamespace

from powerplay.advisor import (
    ACTIVITIES, ACTIVITY_GUIDANCE, CombatLocation,
    SpanshPowerplaySearchClient, activity_snapshot, build_powerplay_mining_plan,
    match_mining_locations,
    match_station_locations,
)
from brokk.search import MiningLocation


class PowerplayAdvisorTests(unittest.TestCase):
    def test_exposes_requested_activity_families(self) -> None:
        self.assertEqual(set(ACTIVITIES), {
            "combat", "trade", "mining", "transport",
            "exploration", "on_foot", "salvage",
        })
        self.assertEqual(set(ACTIVITY_GUIDANCE), set(ACTIVITIES))

    def test_all_activity_searches_validate_the_activity(self) -> None:
        client = SpanshPowerplaySearchClient()
        client.combat_locations = lambda *args, **kwargs: ("candidate",)
        for activity in ACTIVITIES:
            self.assertEqual(
                client.activity_locations((0, 0, 0), "Li Yong-Rui", activity),
                ("candidate",),
            )
        with self.assertRaisesRegex(ValueError, "desconocida"):
            client.activity_locations((0, 0, 0), "Li Yong-Rui", "invalid")

    def test_matches_hotspots_only_inside_candidate_territories(self) -> None:
        territory = CombatLocation(
            "Sistema A", 12, "", "Acquisition", "acquire", "", ""
        )
        inside = MiningLocation(
            "Platinum", "Sistema A", "A 1", "A Ring", "Metallic",
            "Pristine", 2, 12, 500, ""
        )
        outside = MiningLocation(
            "Platinum", "Sistema B", "B 1", "B Ring", "Metallic",
            "Major", 1, 13, 200, ""
        )
        result = match_mining_locations((territory,), (outside, inside))
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]["ring"], "A Ring")
        self.assertEqual(result[0]["reserve_level"], "Pristine")

    def test_counts_only_confirmed_merit_delta(self) -> None:
        state = SimpleNamespace(
            powerplay_power="Li Yong-Rui", powerplay_rank=28,
            powerplay_merits=205120, current_system="Lembava",
            controlling_power="Li Yong-Rui", powerplay_state="Stronghold",
            powerplay_reinforcement=12, powerplay_undermining=4,
        )
        snapshot = activity_snapshot(state, {"key": "combat", "start_merits": 204886})
        self.assertEqual(snapshot["earned"], 234)
        self.assertEqual(snapshot["system_state"], "Stronghold")

    def test_mining_plan_separates_nearby_hotspots_from_powerplay_sale(self):
        territory = CombatLocation(
            "Sistema Venta", 40, "Li Yong-Rui", "Reinforcement",
            "reinforce", "", "",
        )
        hotspot = MiningLocation(
            "Platinum", "Sistema Mina", "A 1", "A Ring", "Metallic",
            "Pristine", 2, 12, 500, "",
        )
        sales = [{
            "system_name": "Sistema Venta", "station_name": "Puerto Grande",
            "sell_price": 250000, "demand": 5000, "has_large_pad": True,
            "updated_at": "2026-09-03",
        }]

        result = build_powerplay_mining_plan((territory,), (hotspot,), sales)

        self.assertEqual(result[0]["operation"], "mine")
        self.assertEqual(result[0]["system"], "Sistema Mina")
        self.assertEqual(result[1]["operation"], "reinforce")
        self.assertEqual(result[1]["station"], "Puerto Grande")

    def test_matches_cached_services_for_exploration_salvage_and_on_foot(self):
        territory = CombatLocation(
            "Sistema A", 12, "", "Reinforcement", "reinforce", "", ""
        )
        common = {
            "system_name": "Sistema A", "has_large_pad": 1,
            "is_planetary": 0, "distance_to_arrival": 800,
        }
        stations = [
            {**common, "station_name": "Cartográfica", "station_type": "Coriolis",
             "services_json": '["Universal Cartographics", "Refuel"]'},
            {**common, "station_name": "Rescate", "station_type": "Outpost",
             "services_json": '["Search and Rescue"]'},
            {**common, "station_name": "Asentamiento", "is_planetary": 1,
             "station_type": "Odyssey Settlement", "services_json": "[]"},
        ]

        exploration = match_station_locations((territory,), stations, "exploration")
        salvage = match_station_locations((territory,), stations, "salvage")
        on_foot = match_station_locations((territory,), stations, "on_foot")

        self.assertEqual(exploration[0]["station"], "Cartográfica")
        self.assertEqual(salvage[0]["station"], "Rescate")
        self.assertEqual(on_foot[0]["station"], "Asentamiento")
        self.assertTrue(on_foot[0]["contact_unverified"])

    def test_combat_search_returns_only_powerplay_disputes(self) -> None:
        rows = [
            {"name": "Propio", "distance": 10, "controlling_power": "Li Yong-Rui",
             "power_state": "Stronghold"},
            {"name": "HR 858", "distance": 30, "power_state": "Unoccupied",
             "power_conflict_progress": [
                 {"power": "Li Yong-Rui", "progress": 0.605},
                 {"power": "Pranav Antal", "progress": 1.264},
             ]},
            {"name": "Expansión", "distance": 20, "power_state": "Unoccupied",
             "power_conflict_progress": [
                 {"power": "Li Yong-Rui", "progress": 0.19},
                 {"power": "Pranav Antal", "progress": 0.03},
             ]},
            {"name": "Rival dominante", "distance": 15,
             "power_state": "Unoccupied", "power_conflict_progress": [
                 {"power": "Li Yong-Rui", "progress": 0.02},
                 {"power": "Felicia Winters", "progress": 0.81},
             ]},
            {"name": "Guerra BGS", "distance": 5,
             "conflicts": [{"status": "active", "war_type": "war"}]},
            {"name": "Irrelevante", "distance": 2},
        ]
        result = SpanshPowerplaySearchClient._records(rows, "Li Yong-Rui", 250)
        self.assertEqual([item.system for item in result], ["HR 858"])
        self.assertEqual(result[0].operation, "undermine")
        self.assertEqual(result[0].conflict, "Disputa Powerplay")
        self.assertEqual(result[0].power_state, "Unoccupied")


if __name__ == "__main__":
    unittest.main()
