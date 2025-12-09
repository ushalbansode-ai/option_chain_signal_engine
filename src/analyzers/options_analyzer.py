"""Options Data Analysis"""
import pandas as pd
import numpy as np

class OptionsAnalyzer:
    def __init__(self, data):
        self.data = data
        self.options_data = data[data['INSTRUMENT'].isin(['OPTSTK', 'OPTIDX'])]
    
    def calculate_pcr(self, symbol=None):
        if symbol:
            df = self.options_data[self.options_data['SYMBOL'] == symbol]
        else:
            df = self.options_data
        
        puts = df[df['OPTION_TYP'] == 'PE']
        calls = df[df['OPTION_TYP'] == 'CE']
        
        put_oi = puts['OPEN_INT'].sum()
        call_oi = calls['OPEN_INT'].sum()
        
        return put_oi / call_oi if call_oi > 0 else 0
    
    def find_high_oi_buildup(self, threshold=1.5):
        opportunities = []
        
        for symbol in self.options_data['SYMBOL'].unique():
            symbol_data = self.options_data[self.options_data['SYMBOL'] == symbol]
            
            for strike in symbol_data['STRIKE_PR'].unique():
                strike_data = symbol_data[symbol_data['STRIKE_PR'] == strike]
                
                for option_type in ['CE', 'PE']:
                    opt_data = strike_data[strike_data['OPTION_TYP'] == option_type]
                    
                    if not opt_data.empty:
                        oi = opt_data['OPEN_INT'].values[0]
                        oi_change = opt_data['CHG_IN_OI'].values[0]
                        
                        if oi > 0 and abs(oi_change / oi) > threshold:
                            opportunities.append({
                                'symbol': symbol,
                                'strike': strike,
                                'type': option_type,
                                'oi': oi,
                                'oi_change_pct': (oi_change / oi) * 100
                            })
        
        return pd.DataFrame(opportunities)
