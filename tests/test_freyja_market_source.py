from pathlib import Path
from unittest.mock import Mock
import tempfile,unittest
from core.database import DatabaseManager
from freyja.market_source import MarketCache,SpanshMarketClient

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

if __name__=="__main__": unittest.main()
