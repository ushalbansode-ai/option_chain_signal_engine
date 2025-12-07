"""
Analyzes option LTP stickiness vs elasticity at key strikes
"""
import numpy as np
from typing import Dict, List

class OptionElasticityAnalyzer:
    def __init__(self, sensitivity_threshold: float = 0.3):
        self.sensitivity_threshold = sensitivity_threshold
        self.price_history = {}
        
    def analyze_elasticity(self, chain_data: Dict, spot_price: float, 
                          spot_change: float, key_strikes: List[float]) -> Dict:
        """Analyze option price elasticity at key strikes"""
        elasticity_results = {}
        
        for strike in key_strikes:
            if strike in chain_data:
                for option_type in ['CE', 'PE']:
                    if option_type in chain_data[strike]:
                        elasticity = self._calculate_elasticity(
                            chain_data[strike][option_type],
                            strike,
                            spot_price,
                            spot_change,
                            option_type
                        )
                        
                        elasticity_results[f"{strike}_{option_type}"] = elasticity
        
        return {
            'elasticity_map': elasticity_results,
            'sticky_zones': self._identify_sticky_zones(elasticity_results),
            'elastic_zones': self._identify_elastic_zones(elasticity_results),
            'gamma_risk': self._assess_gamma_risk(elasticity_results)
        }
    
    def _calculate_elasticity(self, option_data: Dict, strike: float,
                             spot_price: float, spot_change: float, 
                             option_type: str) -> Dict:
        """Calculate elasticity of option price"""
        ltp = option_data.get('LTP', 0)
        delta = self._estimate_delta(option_data, strike, spot_price, option_type)
        iv = option_data.get('IV', 0)
        
        # Calculate expected price change
        expected_change = delta * spot_change if delta else 0
        
        # Get actual price change from history
        actual_change = self._get_actual_price_change(
            f"{strike}_{option_type}", ltp
        )
        
        # Calculate elasticity ratio
        if expected_change != 0:
            elasticity_ratio = actual_change / expected_change
        else:
            elasticity_ratio = 1
        
        # Classify elasticity
        if elasticity_ratio < self.sensitivity_threshold:
            elasticity_type = 'STICKY'  # Low sensitivity
        elif elasticity_ratio > 2.0:
            elasticity_type = 'SUPER_ELASTIC'  # High gamma
        elif elasticity_ratio > 1.0:
            elasticity_type = 'ELASTIC'
        else:
            elasticity_type = 'NORMAL'
        
        return {
            'strike': strike,
            'type': option_type,
            'ltp': ltp,
            'delta': delta,
            'iv': iv,
            'elasticity_ratio': elasticity_ratio,
            'elasticity_type': elasticity_type,
            'expected_change': expected_change,
            'actual_change': actual_change,
            'is_itm': (option_type == 'CE' and strike < spot_price) or 
                     (option_type == 'PE' and strike > spot_price)
        }
    
    def _estimate_delta(self, option_data: Dict, strike: float, 
                       spot_price: float, option_type: str) -> float:
        """Estimate delta based on moneyness and IV"""
        # Simplified delta estimation
        moneyness = abs(spot_price - strike) / strike
        
        if option_type == 'CE':
            if strike < spot_price:  # ITM
                base_delta = 0.7
            elif strike == spot_price:  # ATM
                base_delta = 0.5
            else:  # OTM
                base_delta = 0.3
        else:  # PE
            if strike > spot_price:  # ITM
                base_delta = -0.7
            elif strike == spot_price:  # ATM
                base_delta = -0.5
            else:  # OTM
                base_delta = -0.3
        
        # Adjust for IV
        iv = option_data.get('IV', 0)
        iv_factor = 1.0 + (50 - iv) / 100  # Higher IV = lower delta magnitude
        
        return base_delta * iv_factor
    
    def _get_actual_price_change(self, key: str, current_price: float) -> float:
        """Get actual price change from history"""
        if key in self.price_history and len(self.price_history[key]) > 0:
            previous_price = self.price_history[key][-1]
            price_change = ((current_price - previous_price) / 
                           max(previous_price, 0.01)) * 100
        else:
            price_change = 0
        
        # Update history
        if key not in self.price_history:
            self.price_history[key] = []
        
        self.price_history[key].append(current_price)
        
        # Keep only last 5 prices
        if len(self.price_history[key]) > 5:
            self.price_history[key].pop(0)
        
        return price_change
    
    def _identify_sticky_zones(self, elasticity_map: Dict) -> List[Dict]:
        """Identify zones with sticky options (good for fading)"""
        sticky_zones = []
        
        for key, data in elasticity_map.items():
            if data['elasticity_type'] == 'STICKY':
                sticky_zones.append({
                    'strike': data['strike'],
                    'type': data['type'],
                    'elasticity_ratio': data['elasticity_ratio'],
                    'ltp': data['ltp'],
                    'reason': 'Strong selling pressure' if data['ltp'] > 10 else 'Low gamma'
                })
        
        return sticky_zones
    
    def _identify_elastic_zones(self, elasticity_map: Dict) -> List[Dict]:
        """Identify zones with elastic options (risk of squeezes)"""
        elastic_zones = []
        
        for key, data in elasticity_map.items():
            if data['elasticity_type'] in ['ELASTIC', 'SUPER_ELASTIC']:
                elastic_zones.append({
                    'strike': data['strike'],
                    'type': data['type'],
                    'elasticity_ratio': data['elasticity_ratio'],
                    'ltp': data['ltp'],
                    'is_itm': data['is_itm'],
                    'risk_level': 'HIGH' if data['elasticity_type'] == 'SUPER_ELASTIC' else 'MEDIUM'
                })
        
        return elastic_zones
    
    def _assess_gamma_risk(self, elasticity_map: Dict) -> float:
        """Assess overall gamma risk"""
        super_elastic_count = 0
        total_count = 0
        
        for key, data in elasticity_map.items():
            if data['is_itm'] or abs(data['strike'] - data.get('spot_price', 0)) < 100:
                total_count += 1
                if data['elasticity_type'] == 'SUPER_ELASTIC':
                    super_elastic_count += 1
        
        if total_count > 0:
            gamma_risk = super_elastic_count / total_count
        else:
            gamma_risk = 0
        
        return gamma_risk
