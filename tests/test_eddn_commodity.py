import unittest

from services.eddn_commodity import EDDNCommodityMessageBuilder
from services.eddn_journal import EDDNJournalMessageBuilder


class EDDNCommodityMessageBuilderTests(unittest.TestCase):
    def setUp(self):
        journal=EDDNJournalMessageBuilder("anonymous","0.9.0")
        journal.prepare({"event":"Fileheader","gameversion":"4.1","build":"r1"})
        journal.prepare({"event":"LoadGame","Horizons":True,"Odyssey":True})
        self.builder=EDDNCommodityMessageBuilder(journal)
        self.event={"event":"Market","MarketID":7,"StarSystem":"Sol",
                    "StationName":"Galileo"}
        self.payload={
            "timestamp":"2026-08-09T12:00:00Z","MarketID":7,
            "StarSystem":"Sol","StationName":"Galileo","Items":[{
                "Name":"$gold_name;","Category":"$MARKET_category_metals;",
                "MeanPrice":9000,"BuyPrice":10000,"Stock":50,"StockBracket":2,
                "SellPrice":8000,"Demand":20,"DemandBracket":1,"Producer":True,
                "Name_Localised":"Oro","Category_Localised":"Metales",
            }],
        }

    def test_builds_test_commodity_envelope_with_required_renames(self):
        envelope=self.builder.prepare(self.event,self.payload)
        self.assertEqual(envelope["$schemaRef"],
                         "https://eddn.edcd.io/schemas/commodity/3/test")
        message=envelope["message"]
        self.assertEqual(message["systemName"],"Sol")
        self.assertEqual(message["marketId"],7)
        self.assertTrue(message["odyssey"])
        commodity=message["commodities"][0]
        self.assertEqual(commodity["name"],"gold")
        self.assertEqual(commodity["buyPrice"],10000)
        self.assertEqual(commodity["statusFlags"],["Producer"])
        self.assertNotIn("Name_Localised",commodity)
        self.assertNotIn("Category",commodity)

    def test_rejects_stale_market_file_from_another_station(self):
        self.assertIsNone(self.builder.prepare(
            self.event,dict(self.payload,StationName="Daedalus")
        ))

    def test_filters_nonmarketable_illegal_and_malformed_items(self):
        valid=self.payload["Items"][0]
        self.payload["Items"]=[
            dict(valid,Name="limpet",Category="$MARKET_category_nonmarketable;"),
            dict(valid,Name="narcotics",Legality="Illegal"),
            {"Name":"broken"},valid,
        ]
        envelope=self.builder.prepare(self.event,self.payload)
        self.assertEqual(len(envelope["message"]["commodities"]),1)
        self.assertEqual(envelope["message"]["commodities"][0]["name"],"gold")

    def test_rejects_empty_or_incomplete_market(self):
        self.payload["Items"]=[]
        self.assertIsNone(self.builder.prepare(self.event,self.payload))
        self.assertIsNone(self.builder.prepare({},self.payload))


if __name__=="__main__": unittest.main()
