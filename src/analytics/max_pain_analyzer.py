"""
Analyzes max-pain and synthetic pin level shifts
"""
import numpy as np
from typing import Dict, List

class MaxPainAnalyzer:
    def __init__(self):
        self.max_pain_history = []
        
    def calculate_max_pain(self, chain_data: Dict) -> Dict:
        """Calculate max pain and related metrics"""
        strikes = sorted(chain_data.keys())
        pain_points = []
        
        for strike in strikes:
            ce_oi = chain_data[strike].get('CE', {}).get('open_interest', 0)
            pe_oi = chain_data[strike].get('PE', {}).get('open_interest', 0)
            ce_price = chain_data[strike].get('CE', {}).get('LTP', 0)
            pe_price = chain_data[strike].get('PE', {}).get('LTP', 0)
            
            if ce_oi > 0 or pe_oi > 0:
                # Calculate pain (premium at risk)
                pain = (ce_oi * ce_price) + (pe_oi * pe_price)
                pain_points.append({
                    'strike': strike,
                    'pain': pain,
                    'ce_pain': ce_oi * ce_price,
                    'pe_pain': pe_oi * pe_price,
                    'net_pain': (ce_oi * ce_price) - (pe_oi * pe_price)
                })
        
        if not pain_points:
            return {'max_pain': 0, 'synthetic_pin': 0, 'shift': 0}
        
        # Find max pain (minimum pain for market makers)
        max_pain_point = min(pain_points, key=lambda x: x['pain'])
        
        # Calculate synthetic pin (weighted average of high OI clusters)
        weighted_sum = 0
        total_weight = 0
        
        for point in pain_points:
            if point['pain'] > max_pain_point['pain'] * 0.5:  # Significant clusters
                weight = point['pain']
                weighted_sum += point['strike'] * weight
                total_weight += weight
        
        synthetic_pin = weighted_sum / total_weight if total_weight > 0 else max_pain_point['strike']
        
        # Track shift
        shift = self._track_shift(max_pain_point['strike'])
        
        return {
            'max_pain': max_pain_point['strike'],
            'max_pain_pain': max_pain_point['pain'],
            'synthetic_pin': synthetic_pin,
            'shift': shift,
            'direction': 'UP' if shift > 0 else 'DOWN' if shift < 0 else 'STABLE',
            'oi_clusters': self._identify_oi_clusters(pain_points)
        }
    
    def _track_shift(self, current_max_pain: float) -> float:
        """Track intraday shift in max pain"""
        self.max_pain_history.append(current_max_pain)
        
        if len(self.max_pain_history) > 10:
            self.max_pain_history.pop(0)
        
        if len(self.max_pain_history) >= 5:
            old_avg = np.mean(self.max_pain_history[:5])
            new_avg = np.mean(self.max_pain_history[-5:])
            return new_avg - old_avg
        
        return 0
    
    def _identify_oi_clusters(self, pain_points: List[Dict]) -> List[Dict]:
        """Identify clusters of high OI"""
        clusters = []
        pain_values = [p['pain'] for p in pain_points]
        mean_pain = np.mean(pain_values)
        std_pain = np.std(pain_values)
        
        for point in pain_points:
            if point['pain'] > mean_pain + std_pain:
                clusters.append({
                    'strike': point['strike'],
                    'pain_zscore': (point['pain'] - mean_pain) / std_pain if std_pain > 0 else 0,
                    'type': 'CALL_DOMINANT' if point['net_pain'] > 0 else 'PUT_DOMINANT'
                })
        
        return clusters
