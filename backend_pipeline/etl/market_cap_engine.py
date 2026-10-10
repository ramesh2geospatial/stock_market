import logging
from typing import Dict, List, Optional

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("market_cap_engine")

# Benchmark dataset for Market Cap Tiered Stocks & Mutual Fund Holdings in India

MARKET_CAP_STOCKS = {
    "large": [
        {
            "stock_name": "HDFC Bank Ltd.",
            "isin": "INE040A01034",
            "ticker": "HDFCBANK",
            "market_cap_rank": 1,
            "market_cap_cr": 1285000.0,
            "sector": "Financial Services",
            "total_mf_holding_pct": 19.85,
            "holding_schemes_count": 42,
            "mom_net_shares_change": "+6,450,000",
            "action_tag": "STAKE_INCREASE",
            "mf_holdings": [
                {"scheme_name": "SBI Bluechip Fund", "amc": "SBI Mutual Fund", "shares_held": "8,200,000", "value_cr": 1394.0, "weight_pct": 8.20, "action": "STAKE_INCREASE"},
                {"scheme_name": "HDFC Top 100 Fund", "amc": "HDFC Mutual Fund", "shares_held": "6,500,000", "value_cr": 1105.0, "weight_pct": 9.80, "action": "STAKE_INCREASE"},
                {"scheme_name": "Parag Parikh Flexi Cap Fund", "amc": "PPFAS Mutual Fund", "shares_held": "5,100,000", "value_cr": 867.0, "weight_pct": 7.85, "action": "STAKE_INCREASE"}
            ]
        },
        {
            "stock_name": "Reliance Industries Ltd.",
            "isin": "INE002A01018",
            "ticker": "RELIANCE",
            "market_cap_rank": 2,
            "market_cap_cr": 1980000.0,
            "sector": "Energy / Oil & Gas",
            "total_mf_holding_pct": 14.50,
            "holding_schemes_count": 38,
            "mom_net_shares_change": "-1,120,000",
            "action_tag": "STAKE_REDUCTION",
            "mf_holdings": [
                {"scheme_name": "SBI Bluechip Fund", "amc": "SBI Mutual Fund", "shares_held": "4,100,000", "value_cr": 1189.0, "weight_pct": 6.80, "action": "STAKE_REDUCTION"},
                {"scheme_name": "HDFC Top 100 Fund", "amc": "HDFC Mutual Fund", "shares_held": "3,800,000", "value_cr": 1102.0, "weight_pct": 7.60, "action": "NO_CHANGE"}
            ]
        },
        {
            "stock_name": "Zomato Ltd.",
            "isin": "INE758T01015",
            "ticker": "ZOMATO",
            "market_cap_rank": 35,
            "market_cap_cr": 215000.0,
            "sector": "Consumer Services / Tech",
            "total_mf_holding_pct": 16.20,
            "holding_schemes_count": 29,
            "mom_net_shares_change": "+8,600,000",
            "action_tag": "FRESH_ENTRY",
            "mf_holdings": [
                {"scheme_name": "SBI Bluechip Fund", "amc": "SBI Mutual Fund", "shares_held": "5,200,000", "value_cr": 130.0, "weight_pct": 2.45, "action": "FRESH_ENTRY"},
                {"scheme_name": "Parag Parikh Flexi Cap Fund", "amc": "PPFAS Mutual Fund", "shares_held": "3,400,000", "value_cr": 85.0, "weight_pct": 2.10, "action": "FRESH_ENTRY"}
            ]
        }
    ],
    "mid": [
        {
            "stock_name": "Polycab India Ltd.",
            "isin": "INE455K01017",
            "ticker": "POLYCAB",
            "market_cap_rank": 112,
            "market_cap_cr": 92500.0,
            "sector": "Capital Goods / Electricals",
            "total_mf_holding_pct": 11.40,
            "holding_schemes_count": 22,
            "mom_net_shares_change": "+1,450,000",
            "action_tag": "STAKE_INCREASE",
            "mf_holdings": [
                {"scheme_name": "Nippon India Growth Fund", "amc": "Nippon India Mutual Fund", "shares_held": "1,200,000", "value_cr": 744.0, "weight_pct": 4.10, "action": "STAKE_INCREASE"},
                {"scheme_name": "Kotak Emerging Equity Fund", "amc": "Kotak Mutual Fund", "shares_held": "950,000", "value_cr": 589.0, "weight_pct": 3.80, "action": "STAKE_INCREASE"}
            ]
        },
        {
            "stock_name": "L&T Technology Services Ltd.",
            "isin": "INE010V01017",
            "ticker": "LTTS",
            "market_cap_rank": 145,
            "market_cap_cr": 58400.0,
            "sector": "IT Services / ER&D",
            "total_mf_holding_pct": 8.90,
            "holding_schemes_count": 15,
            "mom_net_shares_change": "+620,000",
            "action_tag": "STAKE_INCREASE",
            "mf_holdings": [
                {"scheme_name": "UTI Mid Cap Fund", "amc": "UTI Mutual Fund", "shares_held": "450,000", "value_cr": 247.0, "weight_pct": 3.20, "action": "STAKE_INCREASE"}
            ]
        }
    ],
    "small": [
        {
            "stock_name": "BSE Ltd.",
            "isin": "INE118H01025",
            "ticker": "BSE",
            "market_cap_rank": 265,
            "market_cap_cr": 38500.0,
            "sector": "Financial Capital Markets",
            "total_mf_holding_pct": 13.80,
            "holding_schemes_count": 18,
            "mom_net_shares_change": "+2,850,000",
            "action_tag": "FRESH_ENTRY",
            "mf_holdings": [
                {"scheme_name": "Nippon India Small Cap Fund", "amc": "Nippon India Mutual Fund", "shares_held": "2,100,000", "value_cr": 588.0, "weight_pct": 3.45, "action": "FRESH_ENTRY"},
                {"scheme_name": "HDFC Small Cap Fund", "amc": "HDFC Mutual Fund", "shares_held": "1,450,000", "value_cr": 406.0, "weight_pct": 2.90, "action": "FRESH_ENTRY"}
            ]
        },
        {
            "stock_name": "Central Depository Services (CDSL)",
            "isin": "INE277A01014",
            "ticker": "CDSL",
            "market_cap_rank": 280,
            "market_cap_cr": 31200.0,
            "sector": "Financial Capital Markets",
            "total_mf_holding_pct": 15.10,
            "holding_schemes_count": 21,
            "mom_net_shares_change": "+1,900,000",
            "action_tag": "STAKE_INCREASE",
            "mf_holdings": [
                {"scheme_name": "Axis Small Cap Fund", "amc": "Axis Mutual Fund", "shares_held": "1,800,000", "value_cr": 270.0, "weight_pct": 4.10, "action": "STAKE_INCREASE"}
            ]
        }
    ],
    "micro": [
        {
            "stock_name": "Senco Gold Ltd.",
            "isin": "INE060O01016",
            "ticker": "SENCO",
            "market_cap_rank": 520,
            "market_cap_cr": 7800.0,
            "sector": "Consumer Retail / Jewellery",
            "total_mf_holding_pct": 9.40,
            "holding_schemes_count": 7,
            "mom_net_shares_change": "+950,000",
            "action_tag": "FRESH_ENTRY",
            "mf_holdings": [
                {"scheme_name": "Nippon India Small Cap Fund", "amc": "Nippon India Mutual Fund", "shares_held": "650,000", "value_cr": 65.0, "weight_pct": 1.85, "action": "FRESH_ENTRY"},
                {"scheme_name": "Bandhan Small Cap Fund", "amc": "Bandhan Mutual Fund", "shares_held": "300,000", "value_cr": 30.0, "weight_pct": 1.40, "action": "FRESH_ENTRY"}
            ]
        },
        {
            "stock_name": "Jupiter Life Line Hospitals Ltd.",
            "isin": "INE050V01011",
            "ticker": "JLHL",
            "market_cap_rank": 545,
            "market_cap_cr": 6900.0,
            "sector": "Healthcare Services",
            "total_mf_holding_pct": 11.20,
            "holding_schemes_count": 9,
            "mom_net_shares_change": "+420,000",
            "action_tag": "STAKE_INCREASE",
            "mf_holdings": [
                {"scheme_name": "DSP Small Cap Fund", "amc": "DSP Mutual Fund", "shares_held": "380,000", "value_cr": 39.9, "weight_pct": 2.10, "action": "STAKE_INCREASE"}
            ]
        }
    ]
}

class MarketCapEngine:
    """Engine providing Market Cap Tiered Stock search and mutual fund ownership data."""

    @staticmethod
    def get_stocks_by_tier(tier: str = "large") -> List[Dict]:
        """Fetch stock list for market cap tier ('large', 'mid', 'small', 'micro')."""
        return MARKET_CAP_STOCKS.get(tier.lower(), [])

    @staticmethod
    def get_stock_mf_holdings(isin: str) -> Optional[Dict]:
        """Fetch detailed mutual fund ownership matrix for a specific stock ISIN."""
        for tier, stocks in MARKET_CAP_STOCKS.items():
            for stock in stocks:
                if stock["isin"].upper() == isin.upper():
                    return stock
        return None

if __name__ == "__main__":
    engine = MarketCapEngine()
    print("Micro cap stocks:", engine.get_stocks_by_tier("micro"))
