import unittest

from services.eddn_journal import EDDNJournalMessageBuilder


class EDDNJournalMessageBuilderTests(unittest.TestCase):
    def setUp(self):
        self.builder=EDDNJournalMessageBuilder("anonymous-test","0.9.0")

    def location(self):
        return {
            "timestamp":"2026-08-09T00:00:00Z","event":"Location",
            "StarSystem":"Sol","StarPos":[0.0,0.0,0.0],"SystemAddress":10477373803,
        }

    def test_builds_official_journal_envelope_without_network(self):
        self.builder.prepare({
            "event":"Fileheader","gameversion":"4.1.3.0","build":"r312345",
        })

        envelope=self.builder.prepare(self.location())

        self.assertEqual(
            envelope["$schemaRef"],"https://eddn.edcd.io/schemas/journal/1"
        )
        self.assertEqual(envelope["header"]["uploaderID"],"anonymous-test")
        self.assertEqual(envelope["header"]["softwareName"],"ODIN")
        self.assertEqual(envelope["header"]["gameversion"],"4.1.3.0")
        self.assertEqual(envelope["header"]["gamebuild"],"r312345")
        self.assertEqual(envelope["message"]["StarSystem"],"Sol")

    def test_enriches_scan_from_last_valid_system_context(self):
        self.builder.prepare(self.location())

        envelope=self.builder.prepare({
            "timestamp":"2026-08-09T00:01:00Z","event":"Scan",
            "BodyName":"Sol A","BodyID":1,"StarType":"G",
        })

        self.assertEqual(envelope["message"]["StarSystem"],"Sol")
        self.assertEqual(envelope["message"]["StarPos"],[0.0,0.0,0.0])
        self.assertEqual(envelope["message"]["SystemAddress"],10477373803)

    def test_removes_localised_and_private_fields_recursively(self):
        event=self.location() | {
            "FuelLevel":24.5,"StationName_Localised":"Galileo",
            "Factions":[{
                "Name":"Federation","MyReputation":100,
                "Allegiance_Localised":"Federacion",
            }],
        }

        message=self.builder.prepare(event)["message"]

        self.assertNotIn("FuelLevel",message)
        self.assertNotIn("StationName_Localised",message)
        self.assertNotIn("MyReputation",message["Factions"][0])
        self.assertNotIn("Allegiance_Localised",message["Factions"][0])

    def test_rejects_unsupported_or_incomplete_events(self):
        self.assertIsNone(self.builder.prepare({"event":"Music"}))
        self.assertIsNone(self.builder.prepare({
            "timestamp":"2026-08-09T00:00:00Z","event":"Scan",
        }))

    def test_invalid_location_does_not_replace_last_context(self):
        self.builder.prepare(self.location())
        self.assertIsNone(self.builder.prepare({
            "timestamp":"2026-08-09T00:00:01Z","event":"FSDJump",
            "StarSystem":"Broken","StarPos":[1,2],"SystemAddress":7,
        }))

        scan=self.builder.prepare({
            "timestamp":"2026-08-09T00:02:00Z","event":"Scan","BodyID":1,
        })
        self.assertEqual(scan["message"]["StarSystem"],"Sol")

    def test_rejects_augmentation_when_event_conflicts_with_context(self):
        self.builder.prepare(self.location())
        self.assertIsNone(self.builder.prepare({
            "timestamp":"2026-08-09T00:02:00Z","event":"Scan",
            "SystemAddress":999,"BodyID":1,
        }))

    def test_load_game_flags_are_added_only_when_known(self):
        self.builder.prepare({
            "event":"LoadGame","Horizons":True,"Odyssey":False,
        })
        envelope=self.builder.prepare(self.location())
        self.assertTrue(envelope["message"]["horizons"])
        self.assertFalse(envelope["message"]["odyssey"])


if __name__=="__main__":
    unittest.main()
