from pathlib import Path
from unittest.mock import Mock
import tempfile,unittest
from datetime import datetime, timedelta, timezone
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
    def test_spansh_client_searches_market_stations_near_power_center(self):
        response=Mock(); response.json.return_value={"results":[{"market_id":8}]}
        session=Mock(); session.post.return_value=response
        records=SpanshMarketClient(session).stations_near((-43.25,-64.34375,-77.6875))
        self.assertEqual(records,({"market_id":8},))
        request=session.post.call_args
        self.assertEqual(request.args[0],"https://spansh.co.uk/api/stations/search")
        self.assertEqual(request.kwargs["json"]["reference_coords"]["x"],-43.25)
        self.assertTrue(request.kwargs["json"]["filters"]["has_market"]["value"])
    def test_builds_realistic_opportunity_between_cached_markets(self):
        current=datetime.now(timezone.utc).isoformat()
        self.cache.ingest_spansh_station({"market_id":1,"system_name":"A","name":"Uno",
          "system_x":0,"system_y":0,"system_z":0,"distance_to_arrival":100,
          "market_updated_at":current,
          "market":[{"commodity":"gold","buy_price":100,"sell_price":90,
                     "supply":100,"demand":0}]})
        self.cache.ingest_spansh_station({"market_id":2,"system_name":"B","name":"Dos",
          "system_x":20,"system_y":0,"system_z":0,"distance_to_arrival":200,
          "market_updated_at":current,
          "system_controlling_power":"Li Yong-Rui","system_power_state":"Stronghold",
          "market":[{"commodity":"gold","buy_price":0,"sell_price":200,
                     "supply":0,"demand":50}]})
        profile=TradeProfile("Origen",10000,1000,100,0,10,(0,0,0))
        opportunities=self.cache.opportunities(profile)
        self.assertEqual((len(opportunities),opportunities[0].jumps),(1,2))
        self.assertEqual(opportunities[0].sell_power,"Li Yong-Rui")
        self.assertEqual(opportunities[0].sell_power_state,"Stronghold")
        plan=QuickRouteOptimizer().choose(profile,opportunities)
        self.assertEqual(plan.units,15)
        self.assertEqual(plan.recommended_sale_tons,15)

    def test_local_market_update_preserves_community_navigation_metadata(self):
        self.cache.ingest_spansh_station({
          "market_id":7,"system_name":"Sol","name":"Galileo",
          "system_x":1,"system_y":2,"system_z":3,"distance_to_arrival":450,
          "has_large_pad":True,"is_planetary":False,"type":"Coriolis Starport",
          "power":{"name":"Li Yong-Rui"},"power_state":"Fortified",
          "market_updated_at":"2026-01-01T00:00:00Z","market":[],
        })
        path=Path(self.temp.name)/"Market.json"
        path.write_text('{"timestamp":"2026-01-02T00:00:00Z","MarketID":7,'
          '"StarSystem":"Sol","StationName":"Galileo","Items":[]}',encoding="utf-8")

        self.cache.ingest_market_file(path)

        row=self.db.query("SELECT * FROM freyja_markets WHERE market_id=7")[0]
        self.assertEqual((row["x"],row["y"],row["z"]),(1.0,2.0,3.0))
        self.assertEqual(row["distance_to_arrival"],450.0)
        self.assertEqual(row["has_large_pad"],1)
        self.assertEqual(row["power_name"],"Li Yong-Rui")
        self.assertEqual(row["station_type"],"Coriolis Starport")

    def test_opportunity_uses_actual_oldest_timestamp_not_text_order(self):
        older="2026-01-01T01:00:00+02:00"
        newer="2026-01-01T00:30:00+00:00"
        self.assertEqual(self.cache._oldest_update(older,newer),older)

    def test_far_future_market_timestamp_is_rejected(self):
        future=(datetime.now(timezone.utc)+timedelta(days=2)).isoformat()
        self.cache.ingest_spansh_station({"market_id":1,"system_name":"A","name":"Uno",
          "system_x":0,"system_y":0,"system_z":0,"market_updated_at":future,
          "market":[{"commodity":"gold","buy_price":100,"supply":100}]})
        self.cache.ingest_spansh_station({"market_id":2,"system_name":"B","name":"Dos",
          "system_x":10,"system_y":0,"system_z":0,"market_updated_at":future,
          "market":[{"commodity":"gold","sell_price":200,"demand":100}]})
        profile=TradeProfile("A",10000,1000,100,0,10,(0,0,0))

        plan=QuickRouteOptimizer().choose(profile,self.cache.opportunities(profile))

        self.assertIsNone(plan)

if __name__=="__main__": unittest.main()
