from pathlib import Path
from unittest.mock import Mock
import tempfile,unittest
from core.database import DatabaseManager
from freyja.market_source import MarketCache,SpanshMarketClient
from freyja.planner import QuickRouteOptimizer,TradeProfile

class FreyjaMarketSourceTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(); self.db=DatabaseManager(Path(self.temp.name))
        self.db.connect(); self.db.create_tables(); self.cache=MarketCache(self.db)
    def tearDown(self): self.db.disconnect(); self.temp.cleanup()
    def test_ingests_local_market_file(self):
        path=Path(self.temp.name)/"Market.json"
        path.write_text('{"timestamp":"2026-01-01T00:00:00Z","MarketID":7,'
          '"StarSystem":"Sol","StationName":"Galileo","Items":[{"Name":"gold",'
          '"BuyPrice":100,"SellPrice":90,"Stock":50,"Demand":20}]}',encoding="utf-8")
        self.assertEqual(self.cache.ingest_market_file(path),1)
        row=self.db.query("SELECT * FROM freyja_market_commodities")[0]
        self.assertEqual((row["commodity"],row["stock"]),("gold",50))
    def test_spansh_client_uses_station_endpoint(self):
        response=Mock(); response.json.return_value={"record":{"market_id":7,"name":"Galileo"}}
        session=Mock(); session.get.return_value=response
        record=SpanshMarketClient(session).station(7)
        session.get.assert_called_once_with("https://spansh.co.uk/api/station/7",timeout=20)
        self.assertEqual(record["name"],"Galileo")
    def test_builds_realistic_opportunity_between_cached_markets(self):
        self.cache.ingest_spansh_station({"market_id":1,"system_name":"A","name":"Uno",
          "system_x":0,"system_y":0,"system_z":0,"distance_to_arrival":100,
          "market_updated_at":"2099-01-01T00:00:00+00:00",
          "market":[{"commodity":"gold","buy_price":100,"sell_price":90,
                     "supply":100,"demand":0}]})
        self.cache.ingest_spansh_station({"market_id":2,"system_name":"B","name":"Dos",
          "system_x":20,"system_y":0,"system_z":0,"distance_to_arrival":200,
          "market_updated_at":"2099-01-01T00:00:00+00:00",
          "market":[{"commodity":"gold","buy_price":0,"sell_price":200,
                     "supply":0,"demand":50}]})
        profile=TradeProfile("Origen",10000,1000,100,0,10,(0,0,0))
        opportunities=self.cache.opportunities(profile)
        self.assertEqual((len(opportunities),opportunities[0].jumps),(1,2))
        plan=QuickRouteOptimizer().choose(profile,opportunities)
        self.assertEqual(plan.units,15)
        self.assertEqual(plan.recommended_sale_tons,15)

if __name__=="__main__": unittest.main()
