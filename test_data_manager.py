import unittest
from data_manager import DataManager

class TestDataManager(unittest.TestCase):
    def test_resolve_ticker_known(self):
        """Test resolving popular Indian company tickers"""
        tcs_res = DataManager.resolve_ticker("TCS")
        self.assertIn("symbol", tcs_res)
        self.assertTrue(tcs_res["symbol"].endswith(".NS") or tcs_res["symbol"].endswith(".BO"))
        print(f"Resolved TCS successfully: {tcs_res}")

        reliance_res = DataManager.resolve_ticker("Reliance")
        self.assertIn("symbol", reliance_res)
        self.assertTrue(reliance_res["symbol"].endswith(".NS") or reliance_res["symbol"].endswith(".BO"))
        print(f"Resolved Reliance successfully: {reliance_res}")

    def test_screener_documents_structure(self):
        """Test fetching documents dictionary from Screener.in"""
        docs = DataManager.fetch_screener_documents("TCS.NS")
        self.assertIn("presentations", docs)
        self.assertIn("transcripts", docs)
        self.assertIn("credit_ratings", docs)
        self.assertIn("annual_reports", docs)
        print("Screener documents parsed successfully.")

if __name__ == "__main__":
    unittest.main()
