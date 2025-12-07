

def iv_skew(df, spot):
if df is None or df.empty:
return 0.0


# nearest strike
df['dist'] = (df['strike'] - spot).abs()
atm_row = df.loc[df['dist'].idxmin()]
ce_iv = float(atm_row.get('CE_IV', 0) or 0)
pe_iv = float(atm_row.get('PE_IV', 0) or 0)
return ce_iv - pe_iv
