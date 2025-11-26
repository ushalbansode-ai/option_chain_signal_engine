#!/usr/bin/env python3
"""
option_signals.py  (Option B - Full Pro)
- Computes price trend, EMA, VWAP deviation, IV trend, OI speed (from option chain only)
- Persists snapshot to previous_snapshot.json so metrics are incremental
- Outputs:
    docs/dashboard.json
    signals/latest.json
    option_signals.csv
    detailed_option_data.csv
"""

import requests
import json
import csv
import os
import time
from datetime import datetime, timedelta

# ------------------ CONFIG ------------------
SYMBOLS = [
    "NIFTY", "BANKNIFTY",
    "RELIANCE", "TCS", "INFY", "HDFCBANK", "ICICIBANK",
    "KOTAKBANK", "HDFC", "BHARTIARTL", "ITC", "SBIN",
    # +10
    "LT", "AXISBANK", "MARUTI", "HINDUNILVR", "BAJFINANCE",
    "ADANIENT", "ULTRACEMCO", "SUNPHARMA", "WIPRO", "LTI"
]

USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
REQUEST_TIMEOUT = 12
SLEEP_BETWEEN = 0.6   # politeness delay
SNAPSHOT_FILE = "previous_snapshot.json"

# EMA settings (fast, configurable)
EMA_PERIOD = 3  # small EMA for momentum

# weights for composite score (sum should be ~1.0)
WEIGHTS = {
    "price_trend": 0.30,
    "ema_momentum": 0.20,
    "vwap_dev": 0.15,
    "iv_trend": 0.20,
    "oi_speed": 0.15
}

# ------------------ UTILITIES ------------------
def ist_now_str(fmt="%Y-%m-%d %H:%M:%S"):
    """Return IST timestamp string (UTC +5:30)."""
    return (datetime.utcnow() + timedelta(hours=5, minutes=30)).strftime(fmt)

def safe_int(x):
    try:
        return int(x or 0)
    except:
        return 0

def safe_float(x):
    try:
        return float(x or 0.0)
    except:
        return 0.0

def ema_update(prev_ema, price, period):
    """Incremental EMA update: alpha = 2/(N+1). If prev_ema is None -> price."""
    if prev_ema is None:
        return price
    alpha = 2.0 / (period + 1.0)
    return alpha * price + (1 - alpha) * prev_ema

# ------------------ Snapshot persistence ------------------
def load_snapshot(path=SNAPSHOT_FILE):
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {"timestamp": None, "symbols": {}}
    return {"timestamp": None, "symbols": {}}

def save_snapshot(data, path=SNAPSHOT_FILE):
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)
    except Exception as e:
        print("✖ Error saving snapshot:", e)

# ------------------ Engine (fetch + analyze) ------------------
class AdvancedOptionSignalGenerator:
    def __init__(self, symbols=SYMBOLS):
        self.symbols = symbols
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": USER_AGENT,
            "Accept": "*/*"
        })
        # load previous snapshot (for EMA/VWAP/IV speed)
        self.snapshot = load_snapshot()
        # ensure structure
        if "symbols" not in self.snapshot:
            self.snapshot["symbols"] = {}
        # store newly collected snapshot results here before persisting
        self.new_snapshot = {"timestamp": ist_now_str(), "symbols": {}}

    def _warm(self):
        try:
            self.session.get("https://www.nseindia.com", timeout=5)
        except Exception:
            pass

    def fetch_option_chain(self, symbol):
        """Fetch option chain JSON from NSE for given symbol."""
        self._warm()
        if symbol in ("NIFTY", "BANKNIFTY"):
            url = f"https://www.nseindia.com/api/option-chain-indices?symbol={symbol}"
        else:
            url = f"https://www.nseindia.com/api/option-chain-equities?symbol={symbol}"

        try:
            r = self.session.get(url, timeout=REQUEST_TIMEOUT)
            if r.status_code == 200:
                return r.json()
            print(f"✖ HTTP {r.status_code} for {symbol}")
        except Exception as e:
            print(f"✖ Fetch error for {symbol}: {e}")
        return None

    def analyze_atm_strikes(self, raw):
        """Return ATM info and ATM±5 filtered rows."""
        if not raw or "records" not in raw:
            return None
        records = raw["records"]
        underlying = records.get("underlyingValue")
        expiry_list = records.get("expiryDates", []) or []
        all_rows = records.get("data", []) or []
        if underlying is None or not expiry_list or not all_rows:
            return None
        expiry = expiry_list[0]
        rows_for_expiry = [r for r in all_rows if r.get("expiryDate") == expiry]
        if not rows_for_expiry:
            return None
        strikes = sorted({int(r.get("strikePrice", 0)) for r in rows_for_expiry})
        if not strikes:
            return None
        atm = min(strikes, key=lambda x: abs(x - float(underlying)))
        atm_index = strikes.index(atm)
        start = max(0, atm_index - 5)
        end = min(len(strikes), atm_index + 6)
        selected = strikes[start:end]
        filtered_rows = [r for r in rows_for_expiry if int(r.get("strikePrice", 0)) in selected]
        return {
            "underlying": float(underlying),
            "atm_strike": atm,
            "expiry": expiry,
            "strikes_analyzed": selected,
            "strike_rows": filtered_rows,
            "all_rows": rows_for_expiry
        }

    def analyze_strike_strength(self, strike_rows):
        """Summarize per-strike CE/PE info into numeric fields."""
        out = []
        for r in strike_rows:
            strike = int(r.get("strikePrice", 0))
            ce = r.get("CE") or {}
            pe = r.get("PE") or {}
            ce_oi = safe_int(ce.get("openInterest"))
            pe_oi = safe_int(pe.get("openInterest"))
            ce_chg = safe_int(ce.get("changeinOpenInterest"))
            pe_chg = safe_int(pe.get("changeinOpenInterest"))
            ce_vol = safe_int(ce.get("totalTradedVolume"))
            pe_vol = safe_int(pe.get("totalTradedVolume"))
            ce_iv = safe_float(ce.get("impliedVolatility"))
            pe_iv = safe_float(pe.get("impliedVolatility"))
            ce_ltp = safe_float(ce.get("lastPrice"))
            pe_ltp = safe_float(pe.get("lastPrice"))
            out.append({
                "strike": strike,
                "ce_oi": ce_oi, "pe_oi": pe_oi,
                "ce_chg": ce_chg, "pe_chg": pe_chg,
                "ce_vol": ce_vol, "pe_vol": pe_vol,
                "ce_iv": ce_iv, "pe_iv": pe_iv,
                "ce_ltp": ce_ltp, "pe_ltp": pe_ltp,
                "ce_strength": ce_oi + ce_chg + ce_vol,
                "pe_strength": pe_oi + pe_chg + pe_vol
            })
        return out

    # ------------------ Metric computations ------------------
    def compute_price_trend(self, symbol, underlying):
        """Compute simple price trend percent vs previous snapshot (last underlying)"""
        prev_sym = self.snapshot.get("symbols", {}).get(symbol, {})
        # support both old-style underlying and meta.underlying
        prev_price = None
        if prev_sym:
            prev_price = prev_sym.get("underlying") or (prev_sym.get("meta") or {}).get("underlying")
        if prev_price:
            try:
                pct = (underlying - float(prev_price)) / float(prev_price)
                return round(pct * 100.0, 4)  # percentage
            except Exception:
                return 0.0
        return 0.0

    def compute_ema_and_update(self, symbol, strike, option_ltp):
        """Persist EMA per symbol->strike->ema. Returns updated ema and previous."""
        sym_snap = self.snapshot.get("symbols", {}).get(symbol, {})
        prev_strikes = sym_snap.get("strikes", {}) if sym_snap else {}
        prev = None
        if prev_strikes and str(strike) in prev_strikes:
            prev = prev_strikes[str(strike)].get("ema_ltp")
        new_ema = ema_update(prev, option_ltp, EMA_PERIOD)
        # prepare new_snapshot structure
        self.new_snapshot["symbols"].setdefault(symbol, {}).setdefault("strikes", {}).setdefault(str(strike), {})
        self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["ema_ltp"] = new_ema
        return prev, new_ema

    def compute_vwap_and_update(self, symbol, strike, option_ltp, vol):
        """
        Approximate VWAP over time by maintaining cumulative (price*vol) and cum_vol in snapshot.
        VWAP = cum_vwap_num / cum_vol
        """
        sym_snap = self.snapshot.get("symbols", {}).get(symbol, {})
        prev_strikes = sym_snap.get("strikes", {}) if sym_snap else {}
        prev_cum_num = 0.0
        prev_cum_vol = 0
        if prev_strikes and str(strike) in prev_strikes:
            prev_cum_num = prev_strikes[str(strike)].get("cum_vwap_num", 0.0)
            prev_cum_vol = prev_strikes[str(strike)].get("cum_vol", 0)
        # update with current observation
        add_num = option_ltp * vol if option_ltp and vol else 0.0
        cum_num = prev_cum_num + add_num
        cum_vol = prev_cum_vol + vol
        vwap = (cum_num / cum_vol) if cum_vol > 0 else None
        # save into new_snapshot
        self.new_snapshot["symbols"].setdefault(symbol, {}).setdefault("strikes", {}).setdefault(str(strike), {})
        self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["cum_vwap_num"] = cum_num
        self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["cum_vol"] = cum_vol
        return vwap, prev_cum_num, prev_cum_vol

    def compute_iv_trend_and_update(self, symbol, strike, iv_now):
        """Compute IV delta vs previous and persist iv history short"""
        sym_snap = self.snapshot.get("symbols", {}).get(symbol, {})
        prev_strikes = sym_snap.get("strikes", {}) if sym_snap else {}
        prev_iv = None
        if prev_strikes and str(strike) in prev_strikes:
            prev_iv = prev_strikes[str(strike)].get("iv")
        # store iv in new_snapshot
        self.new_snapshot["symbols"].setdefault(symbol, {}).setdefault("strikes", {}).setdefault(str(strike), {})
        self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["iv"] = iv_now
        iv_delta = None
        if prev_iv is not None:
            iv_delta = iv_now - prev_iv
        return iv_delta, prev_iv
# ---------------- Part 1 end ----------------
import math
class AdvancedOptionSignalGenerator(AdvancedOptionSignalGenerator):
    """Extends itself with scoring & run_all (keeps methods from Part 1)."""

    def compute_oi_speed(self, symbol, strike, coi):
        """
        Compute OI speed: changeinOpenInterest / minutes_since_last_snapshot.
        If no previous timestamp for symbol, returns 0.
        """
        prev_sym = self.snapshot.get("symbols", {}).get(symbol, {})
        prev_time = self.snapshot.get("timestamp")
        if not prev_time:
            # still persist coi into snapshot even if no prev timestamp
            self.new_snapshot["symbols"].setdefault(symbol, {}).setdefault("strikes", {}).setdefault(str(strike), {})
            self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["coi"] = coi
            return 0.0
        try:
            prev_dt = datetime.strptime(prev_time, "%Y-%m-%d %H:%M:%S")
        except Exception:
            # persist and return 0
            self.new_snapshot["symbols"].setdefault(symbol, {}).setdefault("strikes", {}).setdefault(str(strike), {})
            self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["coi"] = coi
            return 0.0
        now_dt = datetime.utcnow() + timedelta(hours=5, minutes=30)
        minutes = max(1.0, (now_dt - prev_dt).total_seconds() / 60.0)
        # prev_coi for strike
        prev_coi = 0
        prev_strikes = prev_sym.get("strikes", {}) if prev_sym else {}
        if prev_strikes and str(strike) in prev_strikes:
            prev_coi = prev_strikes[str(strike)].get("coi", 0)
        # speed = (coi - prev_coi) / minutes
        speed = (coi - prev_coi) / minutes
        # persist coi to new snapshot
        self.new_snapshot["symbols"].setdefault(symbol, {}).setdefault("strikes", {}).setdefault(str(strike), {})
        self.new_snapshot["symbols"][symbol]["strikes"][str(strike)]["coi"] = coi
        return round(speed, 4)

    def score_candidate(self, metrics):
        """
        metrics: dict contains:
          price_trend_pct, ema_delta, vwap_dev_pct, iv_delta, oi_speed
        Returns composite score (higher -> stronger buy for CE side, lower -> stronger sell for PE side)
        We'll map values into normalized sub-scores then weight.
        """
        # simple normalization heuristics (you can tune)
        # price_trend_pct: typically small percent - map +/-3% to -1..+1
        pt = max(-3.0, min(3.0, metrics.get("price_trend_pct", 0.0))) / 3.0

        # ema_delta is difference current_ema - prev_ema (positive bullish)
        ema_delta = metrics.get("ema_delta", 0.0)
        ed = max(-5.0, min(5.0, ema_delta)) / 5.0

        # vwap_dev_pct: e.g. +5% -> bullish for buying CE; map -10..+10 to -1..1
        vd = max(-10.0, min(10.0, metrics.get("vwap_dev_pct", 0.0))) / 10.0

        # iv_delta: rising IV hurts buyers; negative iv_delta (falling IV) good for buyer -> invert sign
        ivd = -max(-5.0, min(5.0, metrics.get("iv_delta", 0.0))) / 5.0

        # oi_speed: quick build-up positive for side depending on sign (we'll scale)
        oi_speed = metrics.get("oi_speed", 0.0)
        oi_norm = max(-1000.0, min(1000.0, oi_speed)) / 1000.0

        # Weighted composite
        comp = (
            WEIGHTS["price_trend"] * pt +
            WEIGHTS["ema_momentum"] * ed +
            WEIGHTS["vwap_dev"] * vd +
            WEIGHTS["iv_trend"] * ivd +
            WEIGHTS["oi_speed"] * oi_norm
        )
        # scale to score range, e.g. -100..100
        score = round(comp * 100.0, 2)
        return score

    def select_optimal_strike_with_metrics(self, analysis_data, option_side):
        """
        For a side (CE/PE) compute metrics for each strike candidate and choose by combined score + OI/volume filters.
        Returns best candidate dict with metrics included.
        """
        # analyze strike-level fields
        strike_info = self.analyze_strike_strength(analysis_data["strike_rows"])
        candidates = []
        for info in strike_info:
            strike = info["strike"]
            # choose option ltp and iv depending on side
            if option_side == "CE":
                ltp = info.get("ce_ltp", 0.0)
                iv = info.get("ce_iv", 0.0)
                vol = info.get("ce_vol", 0)
                coi = info.get("ce_chg", 0)
                oi_val = info.get("ce_oi", 0)
            else:
                ltp = info.get("pe_ltp", 0.0)
                iv = info.get("pe_iv", 0.0)
                vol = info.get("pe_vol", 0)
                coi = info.get("pe_chg", 0)
                oi_val = info.get("pe_oi", 0)

            # compute metrics using snapshot persistence helpers
            # price trend (symbol-level)
            price_trend_pct = self.compute_price_trend(analysis_data.get("symbol"), analysis_data.get("underlying"))
            # ema prev/new (we compute using option LTP)
            prev_ema, new_ema = self.compute_ema_and_update(analysis_data.get("symbol"), strike, ltp)
            ema_delta = 0.0
            if prev_ema is not None:
                ema_delta = new_ema - prev_ema
            # vwap approx
            vwap, prev_num, prev_vol = self.compute_vwap_and_update(analysis_data.get("symbol"), strike, ltp, vol)
            vwap_dev_pct = 0.0
            if vwap:
                try:
                    vwap_dev_pct = ((ltp - vwap) / vwap) * 100.0
                except Exception:
                    vwap_dev_pct = 0.0
            # iv trend
            iv_delta, prev_iv = self.compute_iv_trend_and_update(analysis_data.get("symbol"), strike, iv)
            iv_delta = iv_delta if iv_delta is not None else 0.0
            # oi speed
            oi_speed = self.compute_oi_speed(analysis_data.get("symbol"), strike, coi)

            metrics = {
                "price_trend_pct": round(price_trend_pct, 4),
                "ema_prev": prev_ema,
                "ema_new": new_ema,
                "ema_delta": round(ema_delta, 6),
                "vwap": vwap,
                "vwap_dev_pct": round(vwap_dev_pct, 4),
                "iv_delta": round(iv_delta, 6),
                "iv_now": iv,
                "oi_speed": oi_speed,
                "ltp": ltp,
                "volume": vol,
                "coi": coi
            }

            # base liquidity filter: skip if volume very low unless OI strong
            if vol < 10 and info.get("ce_oi", 0) + info.get("pe_oi", 0) < 50:
                continue

            # compute composite score
            score = self.score_candidate(metrics)

            candidate = {
                "strike": strike,
                "side": option_side,
                "ltp": ltp,
                "iv": iv,
                "volume": vol,
                "coi": coi,
                "oi": oi_val,
                "score": score,
                "metrics": metrics
            }
            candidates.append(candidate)

        if not candidates:
            return None
        # sort by score (desc) and volume as tiebreaker
        candidates.sort(key=lambda x: (x["score"], x["volume"]), reverse=True)
        return candidates[0]

    def generate_signal_from_analysis(self, analysis):
        """Determine BUY/SELL signals using PCR and OI window, then select strike with metrics."""
        # PCR from all rows
        ce_oi = pe_oi = 0
        for r in analysis["all_rows"]:
            ce_oi += safe_int((r.get("CE") or {}).get("openInterest"))
            pe_oi += safe_int((r.get("PE") or {}).get("openInterest"))
        pcr = (pe_oi / ce_oi) if ce_oi else 0.0

        # local OI in ATM window
        atm_ce = atm_pe = 0
        for r in analysis["strike_rows"]:
            atm_ce += safe_int((r.get("CE") or {}).get("openInterest"))
            atm_pe += safe_int((r.get("PE") or {}).get("openInterest"))
        oi_ratio = (atm_pe / atm_ce) if atm_ce else 0.0

        # basic sentiment counters
        bullish = bearish = 0
        if pcr >= 1.5:
            bullish += 2
        elif pcr >= 1.2:
            bullish += 1

        if pcr <= 0.6:
            bearish += 2
        elif pcr <= 0.8:
            bearish += 1

        if oi_ratio >= 1.3:
            bullish += 1
        elif oi_ratio <= 0.7:
            bearish += 1

        # Decide side and strength
        side = None
        label = None
        if bullish >= 3:
            side = "CE"; label = "STRONG BUY"
        elif bullish >= 2:
            side = "CE"; label = "BUY"
        elif bearish >= 3:
            side = "PE"; label = "STRONG SELL"
        elif bearish >= 2:
            side = "PE"; label = "SELL"
        else:
            return None  # no clear signal

        best = self.select_optimal_strike_with_metrics(analysis, side)
        if not best:
            return None

        # fill output structure (export metrics for transparency)
        metrics = best.get("metrics", {})
        out = {
            "symbol": analysis.get("symbol"),
            "signal": label,
            "option_type": side,
            "strike": best.get("strike"),
            "atm": analysis.get("atm_strike"),
            "distance_from_atm": abs(best.get("strike") - analysis.get("atm_strike")) if best.get("strike") and analysis.get("atm_strike") else 0,
            "ltp": best.get("ltp"),
            "oi": best.get("oi"),      # total open interest at strike (CE/PE depending on side)
            "coi": best.get("coi"),    # change in open interest
            "volume": best.get("volume"),
            "iv": best.get("iv"),
            "score": best.get("score"),

            # Expose metrics at top-level using Option C keys
            "price_trend": metrics.get("price_trend_pct"),
            "ema_trend": metrics.get("ema_delta"),
            "vwap_dev": metrics.get("vwap_dev_pct"),
            "iv_trend": metrics.get("iv_delta"),
            "oi_speed": metrics.get("oi_speed"),

            "metrics": metrics,  # keep full metrics if needed
            "pcr": round(pcr, 3),
            "oi_ratio": round(oi_ratio, 3),
            "timestamp": ist_now_str()
        }
        return out

    def run_all(self):
        """Main orchestrator: fetch each symbol, compute signals, persist snapshot & outputs."""
        all_signals = []
        dashboard_data = []
        detailed_rows = []

        for sym in self.symbols:
            print(f"\n🔍 Processing {sym}")
            raw = self.fetch_option_chain(sym)
            if not raw:
                print(f"✖ No data for {sym}")
                continue

            analysis = self.analyze_atm_strikes(raw)
            if not analysis:
                print(f"✖ ATM analysis error for {sym}")
                continue

            # attach symbol for metric functions
            analysis["symbol"] = sym

            # generate signal (may return None)
            sig = self.generate_signal_from_analysis(analysis)
            if sig:
                all_signals.append(sig)
                print(f"   ✓ {sig['signal']} {sig['option_type']} @{sig['strike']} (score {sig['score']})")
            else:
                print(f"   ◼ No clear signal for {sym}")

            # dashboard summarised row
            dashboard_data.append({
                "symbol": sym,
                "current_price": analysis["underlying"],
                "atm_strike": analysis["atm_strike"],
                "strikes_analyzed": analysis["strikes_analyzed"],
                "signal": sig["signal"] if sig else None,
                "timestamp": ist_now_str()
            })

            # detailed rows (strike-level summary)
            for s in self.analyze_strike_strength(analysis["strike_rows"]):
                detailed_rows.append({"symbol": sym, **s})

            # polite pause
            time.sleep(SLEEP_BETWEEN)

        # Save CSVs
        self.save_csv("option_signals.csv", all_signals)
        self.save_csv("detailed_option_data.csv", detailed_rows)

        # Final JSON build & top 3 picks
        final_json = {
            "last_updated": ist_now_str(),
            "signals": all_signals,
            "market": [
                {
                    "symbol": d["symbol"],
                    "price": d["current_price"],
                    "atm": d["atm_strike"],
                    "strikes": len(d["strikes_analyzed"]),
                    "updated": d["timestamp"]
                }
                for d in dashboard_data
            ]
        }

        # choose top buys/sells by score
        buy_candidates = [s for s in all_signals if "BUY" in (s.get("signal") or "")]
        sell_candidates = [s for s in all_signals if "SELL" in (s.get("signal") or "")]
        buy_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        sell_candidates.sort(key=lambda x: x.get("score", 0), reverse=True)
        final_json["top_buy"] = buy_candidates[:3]
        final_json["top_sell"] = sell_candidates[:3]

        # persist outputs
        self.save_json("docs/dashboard.json", final_json)
        os.makedirs("signals", exist_ok=True)
        self.save_json("signals/latest.json", all_signals)

        # persist snapshot (merge self.new_snapshot over old to keep symbol-level underlying)
        # copy previous symbol-level underlying into new_snapshot to preserve underlying history
        for sym in self.symbols:
            # ensure underlying saved
            # find any dashboard_data entry
            for d in dashboard_data:
                if d["symbol"] == sym:
                    self.new_snapshot["symbols"].setdefault(sym, {}).setdefault("meta", {})
                    self.new_snapshot["symbols"][sym]["meta"]["underlying"] = d["current_price"]
        # set timestamp
        self.new_snapshot["timestamp"] = ist_now_str()
        # Save snapshot file (overwrite)
        save_snapshot(self.new_snapshot)
        print("\n✓ Completed.")
        return all_signals

    # ------------------ IO helpers ------------------
    def save_csv(self, filename, rows):
        try:
            keys = set()
            for r in rows:
                keys.update(r.keys())
            keys = list(keys)
            with open(filename, "w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=keys)
                writer.writeheader()
                for r in rows:
                    writer.writerow(r)
            print(f"📄 Saved CSV: {filename}")
        except Exception as e:
            print(f"✖ CSV error {e}")

    def save_json(self, filename, data):
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            print(f"📝 JSON saved: {filename}")
        except Exception as e:
            print(f"✖ JSON error {filename}: {e}")


# ------------------ RUN ------------------
def main():
    print("\n🧪 Starting NSE Option Signals (Option B - Full Pro)…")
    engine = AdvancedOptionSignalGenerator()
    engine.run_all()
    print("✔ Done.")

if __name__ == "__main__":
    main()
# ---------------- Part 2 end ---------
