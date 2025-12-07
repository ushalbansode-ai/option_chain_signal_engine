import pandas as pd




def compute_freshness(df_history, window_minutes=15):
"""df_history: list of parsed DataFrames ordered oldest..newest
Returns: dict keyed by strike -> {'freshness_score': int, 'flag': str}
Flags: FRESH_HARD_BUILD, FRESH_AGAINST_MOVE, STALE
"""
res = {}
if not df_history:
return res


latest = df_history[-1].set_index('strike')


# ensure consistent strikes present across history; fill zeros where missing
strikes = sorted(latest.index.tolist())


for strike in strikes:
ce_changes = []
pe_changes = []
ce_prices = []
pe_prices = []
for df in df_history:
if strike in df['strike'].values:
row = df.set_index('strike').loc[strike]
ce_changes.append(int(row.get('CE_chg_OI', 0) or 0))
pe_changes.append(int(row.get('PE_chg_OI', 0) or 0))
ce_prices.append(float(row.get('CE_LTP', 0) or 0))
pe_prices.append(float(row.get('PE_LTP', 0) or 0))
else:
ce_changes.append(0)
pe_changes.append(0)
ce_prices.append(0.0)
pe_prices.append(0.0)


ce_trend = sum(ce_changes[-5:])
pe_trend = sum(pe_changes[-5:])
score = abs(ce_trend) + abs(pe_trend)


# rules (tune thresholds as needed)
if score > 5000 and ce_trend > 0 and (ce_prices[-1] > ce_prices[0] if ce_prices[0] > 0 else True):
flag = 'FRESH_HARD_BUILD'
elif score > 3000 and ((ce_trend > 0 and (ce_prices[-1] <= ce_prices[0] if ce_prices[0]>0 else True))
or (pe_trend > 0 and (pe_prices[-1] <= pe_prices[0] if pe_prices[0]>0 else True))):
flag = 'FRESH_AGAINST_MOVE'
else:
flag = 'STALE'


res[int(strike)] = {'freshness_score': int(score), 'flag': flag}


return res
