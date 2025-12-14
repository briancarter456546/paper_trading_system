"""
CRON RUNNER - Daily Paper Trading Entry Point
Run this script daily at 4 PM EST (market close) via cron.

Usage:
    python cron_runner.py

Crontab entry (4 PM EST):
    0 16 * * 1-5 cd /path/to/paper_trading_system && python cron_runner.py >> logs/cron.log 2>&1
"""

import sys
from datetime import datetime
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from data_fetcher import fetch_prices, calculate_factors, get_current_prices
from regime_detector import RegimeDetector
from signal_generator import SignalGenerator, format_signal_summary
from paper_trading_engine import PaperTradingEngine, format_position_summary


def run_daily_trading():
    """Main daily trading routine."""
    
    print("=" * 70)
    print("PAPER TRADING SYSTEM - DAILY RUN")
    print("=" * 70)
    print(f"\nTime: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    current_date = datetime.now().strftime('%Y-%m-%d')
    
    # Skip weekends
    if datetime.now().weekday() >= 5:
        print("\n⚠️  Weekend - skipping trading")
        return
    
    # =========================================================================
    # STEP 1: FETCH DATA
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 1: FETCHING MARKET DATA")
    print("=" * 70)
    
    try:
        prices = fetch_prices(days_back=100)
        print(f"✓ Fetched {len(prices)} days of data")
        print(f"  Date range: {prices.index[0].date()} to {prices.index[-1].date()}")
        print(f"  Tickers: {', '.join(prices.columns.tolist())}")
    except Exception as e:
        print(f"❌ Failed to fetch prices: {e}")
        return
    
    # =========================================================================
    # STEP 2: DETECT REGIME
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 2: DETECTING MARKET REGIME")
    print("=" * 70)
    
    try:
        factors = calculate_factors(prices)
        print("Current Factors:")
        for k, v in factors.items():
            print(f"  {k}: {v:.2f}")
        
        detector = RegimeDetector()
        regime_info = detector.detect_regime(factors)
        
        print(f"\n🎯 DETECTED REGIME: {regime_info['regime']}")
        print(f"   Confidence: {regime_info['confidence']}%")
        print(f"   Group: {detector.get_regime_group(regime_info['regime'])}")
        
        print("\n   All Regime Scores:")
        for regime, score in list(regime_info['all_scores'].items())[:5]:
            print(f"     {regime}: {score:.1f}%")
            
    except Exception as e:
        print(f"❌ Failed to detect regime: {e}")
        return
    
    # =========================================================================
    # STEP 3: GENERATE SIGNALS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 3: GENERATING TRADING SIGNALS")
    print("=" * 70)
    
    generator = SignalGenerator()
    signals = generator.generate_signals(prices, regime_info)
    
    print(format_signal_summary(signals))
    
    # =========================================================================
    # STEP 4: CHECK EXITS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 4: CHECKING FOR EXITS")
    print("=" * 70)
    
    engine = PaperTradingEngine()
    current_prices = get_current_prices(prices)
    
    closed_positions = engine.check_exits(current_date, current_prices)
    
    if closed_positions:
        print(format_position_summary(closed_positions, "POSITIONS CLOSED TODAY"))
    else:
        print("No positions to close today.")
    
    # =========================================================================
    # STEP 5: ENTER NEW POSITIONS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 5: ENTERING NEW POSITIONS")
    print("=" * 70)
    
    entered_positions = []
    for signal in signals:
        position = engine.enter_position(signal, current_date)
        if position:
            entered_positions.append(position)
            print(f"✓ Entered: {position.signal_name}")
            print(f"  Ticker: {position.ticker}")
            print(f"  Shares: {position.shares} @ ${position.entry_price:.2f}")
            print(f"  Size: {position.position_size_pct}%")
            print(f"  Target Exit: {position.target_exit_date}")
        elif signal.is_killed:
            print(f"🚫 Skipped (killed): {signal.name}")
            print(f"   Reason: {signal.kill_reason}")
    
    if not entered_positions and not any(s.is_killed for s in signals):
        print("No signals fired today.")
    
    # =========================================================================
    # STEP 6: SHOW CURRENT STATE
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 6: CURRENT PORTFOLIO STATE")
    print("=" * 70)
    
    open_positions = engine.get_open_positions()
    print(format_position_summary(open_positions, "OPEN POSITIONS"))
    
    # =========================================================================
    # STEP 7: PERFORMANCE METRICS
    # =========================================================================
    print("\n" + "=" * 70)
    print("STEP 7: PERFORMANCE METRICS")
    print("=" * 70)
    
    metrics = engine.get_performance_metrics()
    
    print(f"\n📊 OVERALL PERFORMANCE:")
    print(f"   Total Trades:  {metrics['total_trades']}")
    print(f"   Wins:          {metrics['wins']}")
    print(f"   Losses:        {metrics['losses']}")
    print(f"   Win Rate:      {metrics['win_rate']}%")
    print(f"   Avg Return:    {metrics['avg_return']:+.3f}%")
    print(f"   Avg Win:       {metrics['avg_win']:+.3f}%")
    print(f"   Avg Loss:      {metrics['avg_loss']:+.3f}%")
    print(f"   Total P&L:     ${metrics['total_pnl']:,.2f}")
    
    # Expected vs Actual comparison
    if metrics['total_trades'] >= 10:
        expected_win_rate = 60.0  # Historical expectation
        delta = metrics['win_rate'] - expected_win_rate
        status = "✅ ON TRACK" if delta >= -5 else "⚠️ BELOW EXPECTED"
        print(f"\n   Expected Win Rate: {expected_win_rate}%")
        print(f"   Actual Win Rate:   {metrics['win_rate']}%")
        print(f"   Delta:             {delta:+.1f}pp {status}")
    
    # Save daily metrics
    engine.save_daily_metrics(current_date, regime_info['regime'], regime_info['confidence'])
    
    # =========================================================================
    # SUMMARY
    # =========================================================================
    print("\n" + "=" * 70)
    print("DAILY RUN COMPLETE")
    print("=" * 70)
    print(f"\nRegime: {regime_info['regime']} ({regime_info['confidence']}%)")
    print(f"Signals: {len(signals)} fired, {len(entered_positions)} entered, {len([s for s in signals if s.is_killed])} killed")
    print(f"Exits: {len(closed_positions)} closed")
    print(f"Open Positions: {len(open_positions)}")
    print(f"Win Rate: {metrics['win_rate']}% ({metrics['total_trades']} trades)")


if __name__ == "__main__":
    run_daily_trading()
