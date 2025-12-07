import pandas as pd




def parse_chain(data):
"""Parse NSE option chain JSON into a standardized pandas DataFrame.
Expected JSON structure matches NSE's /api/option-chain-indices response.
"""
records = data.get("records", {}).get("data", [])
rows = []


for r in records:
strike = r.get("strikePrice")


CE = r.get("CE", {}) or {}
PE = r.get("PE", {}) or {}


rows.append({
"strike": int(strike),
"CE_OI": int(CE.get("openInterest", 0) or 0),
"CE_chg_OI": int(CE.get("changeinOpenInterest", 0) or 0),
"CE_LTP": float(CE.get("lastPrice", 0) or 0),
"CE_IV": float(CE.get("impliedVolatility", 0) or 0),
"CE_volume": int(CE.get("totalTradedVolume", 0) or 0),


"PE_OI": int(PE.get("openInterest", 0) or 0),
"PE_chg_OI": int(PE.get("changeinOpenInterest", 0) or 0),
"PE_LTP": float(PE.get("lastPrice", 0) or 0),
"PE_IV": float(PE.get("impliedVolatility", 0) or 0),
"PE_volume": int(PE.get("totalTradedVolume", 0) or 0),
})


df = pd.DataFrame(rows)
if df.empty:
return df


df = df.sort_values("strike").reset_index(drop=True)
df["total_OI"] = df["CE_OI"] + df["PE_OI"]
df["OI_diff"] = df["CE_OI"] - df["PE_OI"]
df["OI_chg_diff"] = df["CE_chg_OI"] - df["PE_chg_OI"]


# Derived ratios
df["CE_vol_to_OI"] = df.apply(lambda r: r['CE_volume']/r['CE_OI'] if r['CE_OI']>0 else 0, axis=1)
df["PE_vol_to_OI"] = df.apply(lambda r: r['PE_volume']/r['PE_OI'] if r['PE_OI']>0 else 0, axis=1)


return df
