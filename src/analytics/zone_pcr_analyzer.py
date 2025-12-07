"""
Analyzes Put-Call Ratio by zone instead of whole market
"""
import numpy as np
from typing import Dict, List

class ZonePCRAnalyzer:
    def __init__(self, zone_width: int = 200):
        self.zone_width = zone_width
    
    def analyze_zone_pcr(self, chain_data: Dict, spot_price: float, 
                        key_zones: List[Dict]) -> Dict:
        """Analyze PCR in specific zones"""
        return {
            'global_pcr': self._calculate_global_pcr(chain_data),
            'zone_pcr': self._calculate_zone_pcr(chain_data, spot_price, key_zones),
            'support_pcr': self._calculate_support_pcr(chain_data, key_zones),
            'resistance_pcr': self._calculate_resistance_pcr(chain_data, key_zones),
            'pcr_divergence': self._analyze_pcr_divergence(chain_data, spot_price)
        }
    
    def _calculate_global_pcr(self, chain_data: Dict) -> float:
        """Calculate global PCR"""
        total_pe_oi = 0
        total_ce_oi = 0
        
        for strike, data in chain_data.items():
            total_pe_oi += data.get('PE', {}).get('open_interest', 0)
            total_ce_oi += data.get('CE', {}).get('open_interest', 0)
        
        if total_ce_oi > 0:
            return total_pe_oi / total_ce_oi
        return 1.0
    
    def _calculate_zone_pcr(self, chain_data: Dict, spot_price: float, 
                           key_zones: List[Dict]) -> Dict:
        """Calculate PCR in specific zones around spot"""
        zone_pcr = {}
        
        # Define zones around spot
        zones = [
            ('NEAR_ZONE', spot_price - self.zone_width, spot_price + self.zone_width),
            ('SUPPORT_ZONE', spot_price - 2*self.zone_width, spot_price - self.zone_width),
            ('RESISTANCE_ZONE', spot_price + self.zone_width, spot_price + 2*self.zone_width)
        ]
        
        for zone_name, lower, upper in zones:
            zone_ce_oi = 0
            zone_pe_oi = 0
            
            for strike in chain_data.keys():
                if lower <= strike <= upper:
                    zone_ce_oi += chain_data[strike].get('CE', {}).get('open_interest', 0)
                    zone_pe_oi += chain_data[strike].get('PE', {}).get('open_interest', 0)
            
            zone_pcr[zone_name] = {
                'pcr': zone_pe_oi / max(zone_ce_oi, 1),
                'ce_oi': zone_ce_oi,
                'pe_oi': zone_pe_oi,
                'strike_range': f"{lower}-{upper}"
            }
        
        return zone_pcr
    
    def _calculate_support_pcr(self, chain_data: Dict, key_zones: List[Dict]) -> Dict:
        """Calculate PCR at support zones"""
        support_pcr = {}
        
        # Get support strikes from key zones
        support_strikes = [zone['strike'] for zone in key_zones 
                          if zone.get('type') == 'SUPPORT' or zone.get('dominance') == 'PE']
        
        for strike in support_strikes[:3]:  # Top 3 supports
            # Look at strikes around support
            lower = strike - 50
            upper = strike + 50
            
            ce_oi = 0
            pe_oi = 0
            
            for s in chain_data.keys():
                if lower <= s <= upper:
                    ce_oi += chain_data[s].get('CE', {}).get('open_interest', 0)
                    pe_oi += chain_data[s].get('PE', {}).get('open_interest', 0)
            
            support_pcr[strike] = {
                'pcr': pe_oi / max(ce_oi, 1),
                'ce_oi': ce_oi,
                'pe_oi': pe_oi,
                'strength': 'STRONG' if pe_oi > ce_oi * 2 else 'MODERATE' if pe_oi > ce_oi else 'WEAK'
            }
        
        return support_pcr
    
    def _calculate_resistance_pcr(self, chain_data: Dict, key_zones: List[Dict]) -> Dict:
        """Calculate PCR at resistance zones"""
        resistance_pcr = {}
        
        # Get resistance strikes from key zones
        resistance_strikes = [zone['strike'] for zone in key_zones 
                             if zone.get('type') == 'RESISTANCE' or zone.get('dominance') == 'CE']
        
        for strike in resistance_strikes[:3]:  # Top 3 resistances
            lower = strike - 50
            upper = strike + 50
            
            ce_oi = 0
            pe_oi = 0
            
            for s in chain_data.keys():
                if lower <= s <= upper:
                    ce_oi += chain_data[s].get('CE', {}).get('open_interest', 0)
                    pe_oi += chain_data[s].get('PE', {}).get('open_interest', 0)
            
            resistance_pcr[strike] = {
                'pcr': pe_oi / max(ce_oi, 1),
                'ce_oi': ce_oi,
                'pe_oi': pe_oi,
                'strength': 'STRONG' if ce_oi > pe_oi * 2 else 'MODERATE' if ce_oi > pe_oi else 'WEAK'
            }
        
        return resistance_pcr
    
    def _analyze_pcr_divergence(self, chain_data: Dict, spot_price: float) -> Dict:
        """Analyze divergence between global and zone PCR"""
        global_pcr = self._calculate_global_pcr(chain_data)
        
        # Calculate near zone PCR
        near_ce = 0
        near_pe = 0
        
        for strike in chain_data.keys():
            if spot_price - 100 <= strike <= spot_price + 100:
                near_ce += chain_data[strike].get('CE', {}).get('open_interest', 0)
                near_pe += chain_data[strike].get('PE', {}).get('open_interest', 0)
        
        near_pcr = near_pe / max(near_ce, 1)
        
        # Analyze divergence
        divergence = near_pcr - global_pcr
        
        if divergence > 0.2:
            divergence_type = 'NEAR_ZONE_PE_HEAVY'
            interpretation = 'Localized put buildup near spot despite balanced overall market'
        elif divergence < -0.2:
            divergence_type = 'NEAR_ZONE_CE_HEAVY'
            interpretation = 'Localized call buildup near spot despite balanced overall market'
        else:
            divergence_type = 'BALANCED'
            interpretation = 'No significant divergence'
        
        return {
            'global_pcr': global_pcr,
            'near_zone_pcr': near_pcr,
            'divergence': divergence,
            'divergence_type': divergence_type,
            'interpretation': interpretation,
            'trading_implication': 'FADE_GLOBAL_PCR' if abs(divergence) > 0.3 else 'TRUST_GLOBAL_PCR'
      }
