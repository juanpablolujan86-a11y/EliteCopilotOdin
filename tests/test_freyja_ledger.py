from pathlib import Path
import tempfile, unittest
from core.database import DatabaseManager
from freyja.ledger import TradeLedger

class TradeLedgerTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.database=DatabaseManager(Path(self.temp.name))
        self.database.connect(); self.database.create_tables()
        self.ledger=TradeLedger(self.database)
    def tearDown(self):
        self.database.disconnect(); self.temp.cleanup()
    def test_purchase_and_sale_track_profit(self):
        self.ledger.handle({"timestamp":"1","event":"MarketBuy","MarketID":1,
          "Type":"gold","Count":10,"BuyPrice":100,"TotalCost":1000})
        self.ledger.handle({"timestamp":"2","event":"MarketSell","MarketID":2,
          "Type":"gold","Count":6,"SellPrice":160,"TotalSale":960,"AvgPricePaid":100})
        summary=self.ledger.summary()
        self.assertEqual((summary.realized_profit,summary.cargo_units),(360,4))
    def test_mined_sale_and_duplicates(self):
        event={"timestamp":"1","event":"MiningRefined","Type":"$painite_name;"}
        self.ledger.handle(event); self.ledger.handle(event)
        self.ledger.handle({"timestamp":"2","event":"MarketSell","MarketID":2,
          "Type":"painite","Count":1,"SellPrice":500,"TotalSale":500,"AvgPricePaid":0})
        summary=self.ledger.summary()
        self.assertEqual((summary.realized_profit,summary.cargo_units),(500,0))

if __name__=="__main__": unittest.main()
