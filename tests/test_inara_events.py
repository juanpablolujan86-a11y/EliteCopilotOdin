import unittest

from services.inara_events import InaraEventMapper


class InaraEventMapperTests(unittest.TestCase):
    def setUp(self):
        self.mapper=InaraEventMapper(); self.timestamp="2026-08-09T12:00:00Z"

    def test_load_game_maps_authoritative_credit_snapshot(self):
        mapped=self.mapper.map({"timestamp":self.timestamp,"event":"LoadGame",
                                "Credits":123456,"Loan":500})
        self.assertEqual(mapped[0]["eventName"],"setCommanderCredits")
        self.assertEqual(mapped[0]["eventData"],{
            "commanderCredits":123456,"commanderLoan":500
        })

    def test_statistics_preserve_complete_journal_sections(self):
        mapped=self.mapper.map({"timestamp":self.timestamp,"event":"Statistics",
                                "Bank_Account":{"Current_Wealth":10},
                                "Combat":{"Kills":2}})
        self.assertEqual(mapped[0]["eventName"],"setCommanderGameStatistics")
        self.assertNotIn("event",mapped[0]["eventData"])
        self.assertEqual(mapped[0]["eventData"]["Combat"],{"Kills":2})

    def test_rank_and_progress_use_documented_names_and_scale(self):
        rank=self.mapper.map({"timestamp":self.timestamp,"event":"Rank",
                              "Combat":3,"Explore":5})[0]
        self.assertEqual(rank["eventData"],[
            {"rankName":"combat","rankValue":3},
            {"rankName":"explore","rankValue":5},
        ])
        progress=self.mapper.map({"timestamp":self.timestamp,"event":"Progress",
                                  "Combat":42,"Exobiologist":100})[0]
        self.assertEqual(progress["eventData"],[
            {"rankName":"combat","rankProgress":0.42},
            {"rankName":"exobiologist","rankProgress":1.0},
        ])

    def test_unknown_or_incomplete_events_are_ignored(self):
        self.assertEqual(self.mapper.map({"event":"Music"}),())
        self.assertEqual(self.mapper.map({"timestamp":self.timestamp,"event":"Music"}),())

    def test_fsd_jump_maps_location_coordinates_and_distance(self):
        mapped=self.mapper.map({"timestamp":self.timestamp,"event":"FSDJump",
                                "StarSystem":"Sol","StarPos":[0,0,0],
                                "JumpDist":12.5})[0]
        self.assertEqual(mapped["eventName"],"addCommanderTravelFSDJump")
        self.assertEqual(mapped["eventData"],{
            "starsystemName":"Sol","starsystemCoords":[0,0,0],
            "jumpDistance":12.5,
        })

    def test_docked_maps_station_and_market_without_session_location_duplication(self):
        docked=self.mapper.map({"timestamp":self.timestamp,"event":"Docked",
                                "StarSystem":"Sol","StationName":"Galileo",
                                "MarketID":128})[0]
        self.assertEqual(docked["eventName"],"addCommanderTravelDock")
        location=self.mapper.map({"timestamp":self.timestamp,"event":"Location",
                                  "StarSystem":"Sol","Docked":True,
                                  "StationName":"Galileo","MarketID":128})[0]
        self.assertEqual(location["eventName"],"setCommanderTravelLocation")

    def test_location_maps_body_coordinates_when_known(self):
        mapped=self.mapper.map({"timestamp":self.timestamp,"event":"Location",
                                "StarSystem":"Sol","Body":"Earth",
                                "Latitude":10.5,"Longitude":-20.25})[0]
        self.assertEqual(mapped["eventData"]["starsystemBodyCoords"],[10.5,-20.25])

    def test_loadout_and_ship_name_update_current_ship(self):
        loadout=self.mapper.map({"timestamp":self.timestamp,"event":"Loadout",
                                 "Ship":"anaconda","ShipID":7,"ShipName":"ODIN",
                                 "ShipIdent":"NOR-1","Rebuy":123,"CargoCapacity":64})[0]
        self.assertEqual(loadout["eventName"],"setCommanderShip")
        self.assertEqual(loadout["eventData"]["shipGameID"],7)
        self.assertEqual(loadout["eventData"]["shipRebuyCost"],123)
        renamed=self.mapper.map({"timestamp":self.timestamp,
                                 "event":"SetUserShipName","Ship":"anaconda",
                                 "ShipID":7,"UserShipName":"Yggdrasil",
                                 "UserShipId":"TREE"})[0]
        self.assertEqual(renamed["eventData"]["shipName"],"Yggdrasil")
        self.assertEqual(renamed["eventData"]["shipIdent"],"TREE")


if __name__=="__main__": unittest.main()
