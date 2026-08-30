from datetime import datetime, timezone
from unittest.mock import Mock
import unittest

from freyja.powerplay_sale import (
    PowerplaySaleFinder, external_commodity_name,
)


class FreyjaPowerplaySaleTests(unittest.TestCase):
    def test_spanish_soontill_name_maps_to_external_market_name(self):
        self.assertEqual(
            external_commodity_name("Reliquias de Soontill"),
            "soontill relics",
        )

    def test_finder_selects_best_fresh_reinforcement_market_for_large_ship(self):
        now=datetime.now(timezone.utc).isoformat()
        client=Mock()
        client.stations_near_power.return_value=(
            {
                "system_name":"Sin plataforma","name":"Puesto",
                "system_power_state":"Exploited","distance":100,
                "has_large_pad":False,"market_updated_at":now,
                "market":[{"commodity":"Soontill Relics","sell_price":50000}],
            },
            {
                "system_name":"Destino","name":"Puerto Grande",
                "system_power_state":"Fortified","distance":180,
                "distance_to_arrival":10,"has_large_pad":True,
                "market_updated_at":now,
                "market":[{"commodity":"Soontill Relics","sell_price":39000}],
            },
            {
                "system_name":"No controlado","name":"Mercado",
                "system_power_state":"Unoccupied","distance":50,
                "has_large_pad":True,"market_updated_at":now,
                "market":[{"commodity":"Soontill Relics","sell_price":60000}],
            },
            {
                "system_name":"Planetario","name":"Base",
                "system_power_state":"Fortified","distance":10,
                "is_planetary":True,"has_large_pad":True,"market_updated_at":now,
                "market":[{"commodity":"Soontill Relics","sell_price":90000}],
            },
        )

        result=PowerplaySaleFinder(client).find(
            "Reliquias de Soontill","Li Yong-Rui",(0,0,0),
            requires_large_pad=True,pages=1,
            allow_planetary=False,
        )

        self.assertEqual(result.system,"Destino")
        self.assertEqual(result.station,"Puerto Grande")
        client.stations_near_power.assert_called_once_with(
            (0,0,0),"Li Yong-Rui",size=100,page=0
        )
