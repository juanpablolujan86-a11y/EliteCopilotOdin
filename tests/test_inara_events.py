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
        loadout_events=self.mapper.map({"timestamp":self.timestamp,"event":"Loadout",
                                 "Ship":"anaconda","ShipID":7,"ShipName":"ODIN",
                                 "ShipIdent":"NOR-1","Rebuy":123,"CargoCapacity":64,
                                 "Modules":[]})
        loadout=loadout_events[0]
        self.assertEqual(loadout["eventName"],"setCommanderShip")
        self.assertEqual(loadout["eventData"]["shipGameID"],7)
        self.assertEqual(loadout["eventData"]["shipRebuyCost"],123)
        renamed=self.mapper.map({"timestamp":self.timestamp,
                                 "event":"SetUserShipName","Ship":"anaconda",
                                 "ShipID":7,"UserShipName":"Yggdrasil",
                                 "UserShipId":"TREE"})[0]
        self.assertEqual(renamed["eventData"]["shipName"],"Yggdrasil")
        self.assertEqual(renamed["eventData"]["shipIdent"],"TREE")

    def test_loadout_maps_modules_ammunition_and_engineering(self):
        mapped=self.mapper.map({
            "timestamp":self.timestamp,"event":"Loadout",
            "Ship":"anaconda","ShipID":7,
            "Modules":[{
                "Slot":"HugeHardpoint1","Item":"hpt_multicannon_gimbal_huge",
                "Health":0.98,"On":True,"Priority":2,
                "AmmoInClip":69,"AmmoInHopper":2100,
                "Engineering":{
                    "BlueprintName":"Weapon_Overcharged","Level":5,"Quality":1.0,
                    "ExperimentalEffect":"special_incendiary_rounds",
                    "Modifiers":[{"Label":"Damage","Value":4.95,
                                  "OriginalValue":3.46,"LessIsGood":False}],
                },
            }],
        })
        self.assertEqual(len(mapped),2)
        loadout=mapped[1]
        self.assertEqual(loadout["eventName"],"setCommanderShipLoadout")
        module=loadout["eventData"]["shipLoadout"][0]
        self.assertEqual(module["slotName"],"HugeHardpoint1")
        self.assertTrue(module["isOn"])
        self.assertEqual(module["itemAmmoHopper"],2100)
        self.assertEqual(module["engineering"]["blueprintLevel"],5)
        self.assertFalse(module["engineering"]["modifiers"][0]["lessIsGood"])

    def test_loadout_skips_malformed_modules_without_dropping_ship(self):
        mapped=self.mapper.map({"timestamp":self.timestamp,"event":"Loadout",
                                "Ship":"sidewinder","ShipID":1,
                                "Modules":[{"Slot":"PowerPlant"}]})
        self.assertEqual(len(mapped),1)
        self.assertEqual(mapped[0]["eventName"],"setCommanderShip")

    def test_cargo_snapshot_splits_legal_stolen_and_mission_items(self):
        mapped=self.mapper.map({
            "timestamp":self.timestamp,"event":"Cargo","Inventory":[
                {"Name":"gold","Count":5,"Stolen":2},
                {"Name":"cobalt","Count":3,"Stolen":0,"MissionID":123},
            ],
        })[0]
        self.assertEqual(mapped["eventName"],"setCommanderInventoryCargo")
        self.assertEqual(mapped["eventData"],[
            {"itemName":"gold","itemCount":3},
            {"itemName":"gold","itemCount":2,"isStolen":True},
            {"itemName":"cobalt","itemCount":3,"missionGameID":123},
        ])

    def test_empty_cargo_snapshot_is_an_explicit_inventory_reset(self):
        mapped=self.mapper.map({"timestamp":self.timestamp,"event":"Cargo",
                                "Inventory":[]})[0]
        self.assertEqual(mapped["eventData"],[])

    def test_materials_merge_all_complete_journal_categories(self):
        mapped=self.mapper.map({
            "timestamp":self.timestamp,"event":"Materials",
            "Raw":[{"Name":"iron","Count":10}],
            "Manufactured":[{"Name":"chemicalprocessors","Count":4}],
            "Encoded":[{"Name":"wakeexceptions","Count":2}],
        })[0]
        self.assertEqual(mapped["eventName"],"setCommanderInventoryMaterials")
        self.assertEqual(len(mapped["eventData"]),3)

    def test_incomplete_inventory_snapshots_are_ignored(self):
        self.assertEqual(self.mapper.map({"timestamp":self.timestamp,"event":"Cargo"}),())
        self.assertEqual(self.mapper.map({"timestamp":self.timestamp,"event":"Materials",
                                          "Raw":[],"Manufactured":[]}),())

    def test_touchdown_maps_body_and_surface_coordinates(self):
        mapped=self.mapper.map({
            "timestamp":self.timestamp,"event":"Touchdown","StarSystem":"Sol",
            "Body":"Earth","Latitude":51.5,"Longitude":-0.1,"Taxi":False,
        })[0]
        self.assertEqual(mapped["eventName"],"addCommanderTravelLand")
        self.assertEqual(mapped["eventData"],{
            "starsystemName":"Sol","starsystemBodyName":"Earth",
            "starsystemBodyCoords":[51.5,-0.1],
        })

    def test_dropship_deploy_is_identified_as_frontline_transport(self):
        mapped=self.mapper.map({
            "timestamp":self.timestamp,"event":"DropShipDeploy",
            "StarSystem":"Sol","BodyName":"Earth",
        })[0]
        self.assertTrue(mapped["eventData"]["isTaxiDropship"])

    def test_carrier_jump_maps_destination_without_inventing_distance(self):
        mapped=self.mapper.map({
            "timestamp":self.timestamp,"event":"CarrierJump",
            "StarSystem":"Colonia","StarPos":[-9530.5,-910.3,19808.1],
            "StationName":"ABC-123","MarketID":123456,
        })[0]
        self.assertEqual(mapped["eventName"],"addCommanderTravelCarrierJump")
        self.assertNotIn("jumpDistance",mapped["eventData"])
        self.assertEqual(mapped["eventData"]["stationName"],"ABC-123")


if __name__=="__main__": unittest.main()
