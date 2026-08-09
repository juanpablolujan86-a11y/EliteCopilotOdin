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


if __name__=="__main__": unittest.main()
