"""
DATA FETCHER MODULE
Fetches daily prices from FMP (Financial Modeling Prep) and calculates regime factors.
"""

import pandas as pd
import numpy as np
import requests
from datetime import datetime, timedelta
import os
import warnings
warnings.filterwarnings('ignore')

# FMP API Configuration
# Get your free API key at: https://site.financialmodelingprep.com/developer/docs/
FMP_API_KEY = os.environ.get('FMP_API_KEY', 'YOUR_FMP_API_KEY_HERE')
FMP_BASE_URL = 'https://financialmodelingprep.com/api/v3'

# Tickers needed for regime detection and trading
REGIME_TICKERS = ['SPY', 'TLT', 'IAU', 'DBC']
VIX_TICKER = '^VIX'  # FMP uses ^VIX for VIX index
SIGNAL_TICKERS = ['JNK', 'ANGL', 'HYG', 'IWM', 'COPX', 'MDY', 'UUP', 'PLTM']
ALL_TICKERS = list(set(REGIME_TICKERS + SIGNAL_TICKERS))


def fetch_fmp_prices(ticker, days_back=150):
    """
    Fetch historical prices from FMP API.
    
    Args:
        ticker: Ticker symbol
        days_back: Number of calendar days to fetch
        
    Returns:
        DataFrame with Date index and Adj Close column
    """
    # Handle VIX specially
    if ticker == '^VIX':
        url = f"{FMP_BASE_URL}/historical-price-full/%5EVIX"
    else:
        url = f"{FMP_BASE_URL}/historical-price-full/{ticker}"
    
    params = {
        'apikey': FMP_API_KEY,
        'from': (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
        'to': datetime.now().strftime('%Y-%m-%d'),
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'historical' not in data:
            print(f"  Warning: No data for {ticker}")
            return None
        
        df = pd.DataFrame(data['historical'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df = df.sort_index()
        
        # Use adjClose if available, otherwise close
        if 'adjClose' in df.columns:
            return df['adjClose']
        else:
            return df['close']
            
    except Exception as e:
        print(f"  Warning: Failed to fetch {ticker}: {e}")
        return None


def fetch_vix(days_back=150):
    """
    Fetch VIX data from FMP.
    
    Returns:
        Series with VIX values
    """
    url = f"{FMP_BASE_URL}/historical-price-full/%5EVIX"
    
    params = {
        'apikey': FMP_API_KEY,
        'from': (datetime.now() - timedelta(days=days_back)).strftime('%Y-%m-%d'),
        'to': datetime.now().strftime('%Y-%m-%d'),
    }
    
    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        data = response.json()
        
        if 'historical' not in data:
            print(f"  Warning: No VIX data")
            return None
        
        df = pd.DataFrame(data['historical'])
        df['date'] = pd.to_datetime(df['date'])
        df = df.set_index('date')
        df = df.sort_index()
        
        return df['close']
        
    except Exception as e:
        print(f"  Warning: Failed to fetch VIX: {e}")
        return None


def fetch_prices(days_back=150):
    """
    Fetch historical prices for all needed tickers.
    
    Args:
        days_back: Number of calendar days to fetch
        
    Returns:
        DataFrame with adjusted close prices, indexed by date
    """
    print(f"  Fetching prices from FMP (API key: {'set' if FMP_API_KEY != 'YOUR_FMP_API_KEY_HERE' else 'NOT SET'})...")
    
    if FMP_API_KEY == 'YOUR_FMP_API_KEY_HERE':
        print("  ⚠️  WARNING: FMP_API_KEY not set!")
        print("  Get a free key at: https://site.financialmodelingprep.com/developer/docs/")
        print("  Set it: export FMP_API_KEY='your_key_here'")
    
    prices = {}
    
    # Fetch regular tickers
    for ticker in ALL_TICKERS:
        print(f"    {ticker}...", end=" ")
        series = fetch_fmp_prices(ticker, days_back)
        if series is not None and len(series) > 0:
            prices[ticker] = series
            print(f"ok ({len(series)} days)")
        else:
            print("failed")
    
    # Fetch VIX
    print(f"    VIX...", end=" ")
    vix = fetch_vix(days_back)
    if vix is not None and len(vix) > 0:
        prices['VIX'] = vix
        print(f"ok ({len(vix)} days)")
    else:
        print("failed")
    
    if not prices:
        raise ValueError("No prices fetched - check your FMP_API_KEY")
    
    df = pd.DataFrame(prices)
    df = df.dropna()
    
    print(f"  Aligned: {len(df)} days of complete data")
    
    return df


def calculate_factors(prices):
    """
    Calculate the 10 regime factors from price data.
    
    Args:
        prices: DataFrame with columns SPY, TLT, IAU, DBC, VIX
        
    Returns:
        Dict with factor values for current day
    """
    if len(prices) < 60:
        raise ValueError(f"Need at least 60 days of data, got {len(prices)}")
    
    # 50-day rate of change (momentum)
    spy_roc_50 = (prices['SPY'].iloc[-1] / prices['SPY'].iloc[-50] - 1) * 100
    tlt_roc_50 = (prices['TLT'].iloc[-1] / prices['TLT'].iloc[-50] - 1) * 100
    iau_roc_50 = (prices['IAU'].iloc[-1] / prices['IAU'].iloc[-50] - 1) * 100
    dbc_roc_50 = (prices['DBC'].iloc[-1] / prices['DBC'].iloc[-50] - 1) * 100
    
    # VIX level and changes
    vix_level = prices['VIX'].iloc[-1]
    vix_5d_ago = prices['VIX'].iloc[-5] if len(prices) >= 5 else prices['VIX'].iloc[0]
    vix_20d_ago = prices['VIX'].iloc[-20] if len(prices) >= 20 else prices['VIX'].iloc[0]
    vix_change_5 = (vix_level / vix_5d_ago - 1) * 100
    vix_change_20 = (vix_level / vix_20d_ago - 1) * 100
    
    # Correlations (20-day rolling)
    returns = prices.pct_change().dropna()
    recent_returns = returns.iloc[-20:]
    
    spy_tlt_corr = recent_returns['SPY'].corr(recent_returns['TLT'])
    iau_spy_corr = recent_returns['IAU'].corr(recent_returns['SPY'])
    
    # SPY vs 200 EMA
    spy_200_ema = prices['SPY'].ewm(span=200, adjust=False).mean().iloc[-1]
    spy_vs_200ema = (prices['SPY'].iloc[-1] / spy_200_ema - 1) * 100
    
    factors = {
        'spy_roc_50': spy_roc_50,
        'tlt_roc_50': tlt_roc_50,
        'iau_roc_50': iau_roc_50,
        'dbc_roc_50': dbc_roc_50,
        'vix_level': vix_level,
        'vix_change_5': vix_change_5,
        'vix_change_20': vix_change_20,
        'spy_tlt_corr': spy_tlt_corr,
        'iau_spy_corr': iau_spy_corr,
        'spy_vs_200ema': spy_vs_200ema,
    }
    
    return factors


def calculate_momentum(prices, ticker, lookback=10):
    """
    Calculate momentum (rate of change) for a ticker.
    
    Args:
        prices: DataFrame with price data
        ticker: Ticker symbol
        lookback: Number of days for momentum calculation
        
    Returns:
        Float: momentum as decimal (0.015 = 1.5%)
    """
    if ticker not in prices.columns:
        return None
    
    if len(prices) < lookback + 1:
        return None
    
    current = prices[ticker].iloc[-1]
    past = prices[ticker].iloc[-(lookback + 1)]
    
    return (current / past) - 1


def get_current_prices(prices):
    """
    Get the most recent closing prices for all tickers.
    
    Args:
        prices: DataFrame with price data
        
    Returns:
        Dict with ticker: price
    """
    latest = prices.iloc[-1]
    return latest.to_dict()


if __name__ == "__main__":
    # Test the data fetcher
    print("Testing FMP Data Fetcher")
    print("=" * 50)
    
    print("\nFetching prices...")
    prices = fetch_prices(days_back=100)
    print(f"\nFetched {len(prices)} days of data")
    print(f"Tickers: {prices.columns.tolist()}")
    print(f"Date range: {prices.index[0].date()} to {prices.index[-1].date()}")
    
    print("\nCalculating factors...")
    factors = calculate_factors(prices)
    for k, v in factors.items():
        print(f"  {k}: {v:.2f}")
    
    print("\nCalculating momentum (10-day)...")
    for ticker in ['JNK', 'ANGL', 'HYG', 'UUP', 'PLTM']:
        mom = calculate_momentum(prices, ticker)
        if mom:
            fired = "🔥 SIGNAL" if mom > 0.015 else ""
            print(f"  {ticker}: {mom*100:+.2f}% {fired}")
