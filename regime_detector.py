"""
REGIME DETECTOR MODULE
Detects current market regime by comparing factors to historical fingerprints.
"""

import json
import numpy as np
from pathlib import Path


class RegimeDetector:
    """Detects market regime using fingerprint matching."""
    
    def __init__(self, fingerprints_path='data/regime_fingerprints_derived.json'):
        """
        Initialize with fingerprints file.
        
        Args:
            fingerprints_path: Path to JSON file with regime fingerprints
        """
        self.fingerprints = self._load_fingerprints(fingerprints_path)
        self.factor_names = [
            'spy_roc_50', 'tlt_roc_50', 'iau_roc_50', 'dbc_roc_50',
            'vix_level', 'vix_change_5', 'vix_change_20',
            'spy_tlt_corr', 'iau_spy_corr', 'spy_vs_200ema'
        ]
    
    def _load_fingerprints(self, path):
        """Load fingerprints from JSON file."""
        with open(path, 'r') as f:
            return json.load(f)
    
    def _score_regime(self, factors, regime_data):
        """
        Score how well current factors match a regime fingerprint.
        
        Args:
            factors: Dict with current factor values
            regime_data: Dict with regime fingerprint (percentiles)
            
        Returns:
            Float: Score from 0-100 (higher = better match)
        """
        scores = []
        
        for factor_name in self.factor_names:
            if factor_name not in factors:
                continue
            
            value = factors[factor_name]
            fingerprint = regime_data['factors'].get(factor_name)
            
            if fingerprint is None:
                continue
            
            # Fingerprint format: [p25, p50, p75]
            p25, p50, p75 = fingerprint
            
            # Score based on how close to median (p50)
            # Within IQR (p25-p75) = good match
            if p25 <= value <= p75:
                # Inside IQR - high score
                distance_from_median = abs(value - p50)
                iqr = p75 - p25
                if iqr > 0:
                    score = 100 * (1 - distance_from_median / iqr)
                else:
                    score = 100
            else:
                # Outside IQR - lower score based on distance
                if value < p25:
                    distance = p25 - value
                    iqr = p75 - p25 if p75 - p25 > 0 else 1
                    score = max(0, 50 - 50 * distance / iqr)
                else:
                    distance = value - p75
                    iqr = p75 - p25 if p75 - p25 > 0 else 1
                    score = max(0, 50 - 50 * distance / iqr)
            
            scores.append(score)
        
        return np.mean(scores) if scores else 0
    
    def detect_regime(self, factors):
        """
        Detect current market regime.
        
        Args:
            factors: Dict with current factor values
            
        Returns:
            Dict with:
                - regime: Best matching regime name
                - confidence: Match score (0-100)
                - all_scores: Dict of all regime scores
        """
        scores = {}
        
        for regime_name, regime_data in self.fingerprints.items():
            scores[regime_name] = self._score_regime(factors, regime_data)
        
        # Find best match
        best_regime = max(scores, key=scores.get)
        confidence = scores[best_regime]
        
        # Sort all scores
        sorted_scores = dict(sorted(scores.items(), key=lambda x: -x[1]))
        
        return {
            'regime': best_regime,
            'confidence': round(confidence, 1),
            'all_scores': sorted_scores,
        }
    
    def get_regime_group(self, regime):
        """
        Get the regime group (RISK_OFF, RISK_ON, TRANSITIONAL).
        
        Args:
            regime: Regime name
            
        Returns:
            String: Group name
        """
        risk_off = ['RISK_OFF_LIQUIDATION', 'RISK_OFF_DEFLATIONARY', 'RISK_OFF_STAGFLATION']
        risk_on = ['RISK_ON_GROWTH', 'RISK_ON_INFLATION', 'GOLDILOCKS']
        transitional = ['CHOPPY_TRANSITIONAL', 'DEBASEMENT_RALLY']
        
        if regime in risk_off:
            return 'RISK_OFF'
        elif regime in risk_on:
            return 'RISK_ON'
        elif regime in transitional:
            return 'TRANSITIONAL'
        else:
            return 'UNKNOWN'


if __name__ == "__main__":
    # Test with sample factors
    sample_factors = {
        'spy_roc_50': 3.0,
        'tlt_roc_50': -2.0,
        'iau_roc_50': 8.0,
        'dbc_roc_50': 4.0,
        'vix_level': 15.0,
        'vix_change_5': -5.0,
        'vix_change_20': -10.0,
        'spy_tlt_corr': -0.3,
        'iau_spy_corr': 0.1,
        'spy_vs_200ema': 5.0,
    }
    
    detector = RegimeDetector()
    result = detector.detect_regime(sample_factors)
    
    print(f"Detected Regime: {result['regime']}")
    print(f"Confidence: {result['confidence']}%")
    print(f"Group: {detector.get_regime_group(result['regime'])}")
    print("\nAll Scores:")
    for regime, score in result['all_scores'].items():
        print(f"  {regime}: {score:.1f}%")
