"""
SIGNAL GENERATOR MODULE
Generates trading signals based on momentum thresholds and regime filtering.
"""

from dataclasses import dataclass
from typing import Optional, List
from data_fetcher import calculate_momentum


# Configuration
MOMENTUM_THRESHOLD = 0.015  # 1.5%

# Signal definitions
SIGNALS = {
    'JNK_IWM': {
        'trigger': 'JNK',
        'target': 'IWM',
        'kill_switch': 'UUP',
        'booster': 'PLTM',
        'base_size': 1.0,
        'boosted_size': 1.5,
    },
    'ANGL_COPX': {
        'trigger': 'ANGL',
        'target': 'COPX',
        'kill_switch': None,
        'booster': None,
        'base_size': 1.0,
        'boosted_size': 1.0,
    },
    'HYG_MDY': {
        'trigger': 'HYG',
        'target': 'MDY',
        'kill_switch': 'UUP',
        'booster': None,
        'base_size': 1.0,
        'boosted_size': 1.0,
    },
}


@dataclass
class Signal:
    """Represents a trading signal."""
    name: str
    trigger_ticker: str
    target_ticker: str
    trigger_momentum: float
    position_size: float  # As percentage of portfolio (1.0 = 1%)
    is_boosted: bool
    is_killed: bool
    kill_reason: Optional[str]
    regime: str
    regime_confidence: float
    entry_price: float


class SignalGenerator:
    """Generates trading signals based on momentum and regime."""
    
    def __init__(self):
        self.momentum_threshold = MOMENTUM_THRESHOLD
    
    def generate_signals(self, prices, regime_info) -> List[Signal]:
        """
        Generate all active signals for current market conditions.
        
        Args:
            prices: DataFrame with price data
            regime_info: Dict with regime detection results
            
        Returns:
            List of Signal objects
        """
        signals = []
        
        for signal_name, config in SIGNALS.items():
            signal = self._check_signal(
                signal_name, config, prices, regime_info
            )
            if signal:
                signals.append(signal)
        
        return signals
    
    def _check_signal(self, signal_name, config, prices, regime_info) -> Optional[Signal]:
        """Check if a specific signal fires."""
        
        trigger = config['trigger']
        target = config['target']
        
        # Calculate trigger momentum
        trigger_mom = calculate_momentum(prices, trigger)
        if trigger_mom is None:
            return None
        
        # Check if signal fires
        if trigger_mom <= self.momentum_threshold:
            return None
        
        # Check kill switch
        is_killed = False
        kill_reason = None
        
        if config['kill_switch']:
            kill_mom = calculate_momentum(prices, config['kill_switch'])
            if kill_mom is not None and kill_mom > self.momentum_threshold:
                is_killed = True
                kill_reason = f"{config['kill_switch']} momentum {kill_mom*100:.2f}% > threshold"
        
        # Check booster
        is_boosted = False
        position_size = config['base_size']
        
        if config['booster']:
            booster_mom = calculate_momentum(prices, config['booster'])
            if booster_mom is not None and booster_mom > self.momentum_threshold:
                is_boosted = True
                position_size = config['boosted_size']
        
        # Get entry price (latest close)
        entry_price = prices[target].iloc[-1]
        
        return Signal(
            name=signal_name,
            trigger_ticker=trigger,
            target_ticker=target,
            trigger_momentum=trigger_mom,
            position_size=position_size,
            is_boosted=is_boosted,
            is_killed=is_killed,
            kill_reason=kill_reason,
            regime=regime_info['regime'],
            regime_confidence=regime_info['confidence'],
            entry_price=entry_price,
        )
    
    def filter_by_regime(self, signals: List[Signal], regime_group: str) -> List[Signal]:
        """
        Filter signals based on regime (optional advanced filtering).
        
        Args:
            signals: List of signals
            regime_group: Current regime group (RISK_OFF, RISK_ON, TRANSITIONAL)
            
        Returns:
            Filtered list of signals
        """
        # For now, we don't filter by regime - we trade all signals
        # But we track regime for analysis
        # Advanced users can add regime-based filtering here
        return signals


def format_signal_summary(signals: List[Signal]) -> str:
    """Format signals for display/logging."""
    if not signals:
        return "No signals fired today."
    
    lines = ["SIGNALS GENERATED:", "-" * 50]
    
    for s in signals:
        status = "🚫 KILLED" if s.is_killed else ("🚀 BOOSTED" if s.is_boosted else "✅ ACTIVE")
        
        lines.append(f"\n{s.name} - {status}")
        lines.append(f"  Trigger: {s.trigger_ticker} momentum = {s.trigger_momentum*100:.2f}%")
        lines.append(f"  Target: {s.target_ticker} @ ${s.entry_price:.2f}")
        lines.append(f"  Position Size: {s.position_size}%")
        lines.append(f"  Regime: {s.regime} ({s.regime_confidence}% confidence)")
        
        if s.is_killed:
            lines.append(f"  Kill Reason: {s.kill_reason}")
    
    return "\n".join(lines)


if __name__ == "__main__":
    # Test signal generation
    from data_fetcher import fetch_prices, calculate_factors
    from regime_detector import RegimeDetector
    
    print("Fetching prices...")
    prices = fetch_prices()
    
    print("Calculating factors...")
    factors = calculate_factors(prices)
    
    print("Detecting regime...")
    detector = RegimeDetector()
    regime_info = detector.detect_regime(factors)
    print(f"Current regime: {regime_info['regime']} ({regime_info['confidence']}%)")
    
    print("\nGenerating signals...")
    generator = SignalGenerator()
    signals = generator.generate_signals(prices, regime_info)
    
    print(format_signal_summary(signals))
