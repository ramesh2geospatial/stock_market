"""
Unit tests for the Vahan EV Sales data provider.
"""
from providers.vahan_provider import VahanProvider


def test_vahan_provider_mapping():
    provider = VahanProvider()
    
    # Test exact mapping
    assert provider.get_maker_by_symbol("TVSMOTOR.NS") == "TVS Motor Company"
    assert provider.get_maker_by_symbol("BAJAJ-AUTO.NS") == "Bajaj Auto"
    assert provider.get_maker_by_symbol("OLAELEC") == "Ola Electric"
    
    # Test case insensitivity / strip
    assert provider.get_maker_by_symbol(" tvsmotor ") == "TVS Motor Company"
    
    # Test invalid mapping
    assert provider.get_maker_by_symbol("RELIANCE.NS") is None


def test_vahan_provider_data_extraction():
    provider = VahanProvider()
    
    # Check makers list
    makers = provider.get_makers()
    assert "TVS Motor Company" in makers
    assert "Bajaj Auto" in makers
    assert "Ola Electric" in makers
    assert "Ather Energy" in makers
    
    # Test dataframe format
    df = provider.get_monthly_sales_df()
    assert not df.empty
    assert set(df.columns) == {"Maker", "Year", "Month", "Registrations"}
    
    # Test June 2026 actual registrations
    june_2026_tvs = df[(df["Maker"] == "TVS Motor Company") & (df["Year"] == 2026) & (df["Month"] == "Jun")].iloc[0]["Registrations"]
    assert june_2026_tvs == 46999
    
    # Test pivot structure
    pivot = provider.get_comparison_data(2026)
    assert not pivot.empty
    assert "TVS Motor Company" in pivot.columns
    assert "Bajaj Auto" in pivot.columns


def test_vahan_provider_daily_data():
    provider = VahanProvider()
    
    # Check flat daily data
    df_daily = provider.get_daily_sales_df()
    assert not df_daily.empty
    assert set(df_daily.columns) == {"Maker", "Date", "Registrations"}
    
    # Check pivoted daily data
    df_daily_pivot = provider.get_daily_comparison_df()
    assert not df_daily_pivot.empty
    assert "Date" in df_daily_pivot.columns
    assert "TVS Motor Company" in df_daily_pivot.columns
    assert len(df_daily_pivot) >= 35

