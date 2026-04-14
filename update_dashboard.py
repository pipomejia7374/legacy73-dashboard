#!/usr/bin/env python3
"""
Legacy 73 LLC Dashboard Updater
Runs in GitHub Actions — fetches live prices from Yahoo Finance,
rebuilds data.json and appends to history.json.
No local files, no PANEL xlsx, no browser automation needed.

Portfolio composition: update POSITIONS / MEMBERS below when holdings change.
"""

import json
import sys
from datetime import date
from pathlib import Path

import yfinance as yf

# ── Portfolio Composition ────────────────────────────────────────────────────
# Update this section whenever positions change.
POSITIONS = [
    {"symbol": "IBIT",                "display": "IBIT",                    "description": "ISHARES BITCOIN TRUST ETF",                                  "asset_type": "ETF",    "qty":  2340, "cost_basis": 128500.89, "multiplier": 1},
    {"symbol": "ASTS",                "display": "ASTS",                    "description": "AST SPACEMOBILE INC CLASS CLASS A",                          "asset_type": "Equity", "qty":    50, "cost_basis":   3685.00, "multiplier": 1},
    {"symbol": "AMD",                 "display": "AMD",                     "description": "ADVANCED MICRO DEVIC",                                        "asset_type": "Equity", "qty":    20, "cost_basis":   4964.20, "multiplier": 1},
    {"symbol": "TSLA",                "display": "TSLA",                    "description": "TESLA INC",                                                   "asset_type": "Equity", "qty":    12, "cost_basis":   5120.80, "multiplier": 1},
    {"symbol": "PLTR",                "display": "PLTR",                    "description": "PALANTIR TECHNOLOGIES INCLASS CLASS A",                       "asset_type": "Equity", "qty":    27, "cost_basis":   4903.79, "multiplier": 1},
    {"symbol": "TSM",                 "display": "TSM",                     "description": "TAIWAN SEMICONDUCTOR M FSPONSORED ADR 1 ADR REPS 5 ORD SHS", "asset_type": "Equity", "qty":     8, "cost_basis":   2370.80, "multiplier": 1},
    {"symbol": "HOOD",                "display": "HOOD",                    "description": "ROBINHOOD MKTS INC CLASS CLASS A",                            "asset_type": "Equity", "qty":    34, "cost_basis":   4407.92, "multiplier": 1},
    {"symbol": "HIMS",                "display": "HIMS",                    "description": "HIMS & HERS HEALTH INC CLASS CLASS A",                        "asset_type": "Equity", "qty":   104, "cost_basis":   4092.35, "multiplier": 1},
    {"symbol": "OKLO",                "display": "OKLO",                    "description": "OKLO INC CLASS A",                                            "asset_type": "Equity", "qty":    40, "cost_basis":   2863.40, "multiplier": 1},
    {"symbol": "DUOL",                "display": "DUOL",                    "description": "DUOLINGO INC CLASS A",                                        "asset_type": "Equity", "qty":    20, "cost_basis":   3538.10, "multiplier": 1},
    {"symbol": "MSTR",                "display": "MSTR",                    "description": "STRATEGY INC CLASS A",                                        "asset_type": "Equity", "qty":    10, "cost_basis":   2015.10, "multiplier": 1},
    {"symbol": "IBIT270115C00045000", "display": "IBIT 01/15/2027 45.00 C", "description": "CALL ISHR BITCOIN TR ETF$45 EXP 01/15/27",                   "asset_type": "Option", "qty":     5, "cost_basis":   8878.30, "multiplier": 100},
    {"symbol": "IBIT271217C00045000", "display": "IBIT 12/17/2027 45.00 C", "description": "CALL ISHR BITCOIN TR ETF$45 EXP 12/17/27",                   "asset_type": "Option", "qty":     1, "cost_basis":   2845.66, "multiplier": 100},
    {"symbol": "IBIT280121P00040000", "display": "IBIT 01/21/2028 40.00 P", "description": "PUT ISHR BITCOIN TR ETF $40 EXP 01/21/28",                   "asset_type": "Option", "qty":    -1, "cost_basis":   -714.34, "multiplier": 100},
]

# ── Fund Parameters ──────────────────────────────────────────────────────────
TOTAL_SHARES   = 17731.906   # Total shares outstanding (Class A + Class B)
OTHER_ASSETS   = 997.0       # Non-Schwab assets (cash/other); update if changed
INCEPTION_DATE = "2024-01-01"

MEMBERS = {
    "mongol":          {"name": "Mongol",          "shares_a": 2050.00, "shares_b": 2871.9183},
    "7m":              {"name": "7M",              "shares_a": 2003.00, "shares_b": 2724.0000},
    "lerd":            {"name": "Lerd",            "shares_a": 2532.00, "shares_b": 3003.3083},
    "jacucha":         {"name": "Jacucha",         "shares_a": 1031.00, "shares_b":  106.8637},
    "vargas":          {"name": "Vargas",          "shares_a":  609.00, "shares_b":   91.8480},
    "familia_gump":    {"name": "Familia Gump",    "shares_a":  550.00, "shares_b":    0.0000},
    "gump_individual": {"name": "Gump Individual", "shares_a":    0.00, "shares_b":  158.9676},
}


# ── Price Fetching ────────────────────────────────────────────────────────────

def fetch_all_prices():
    """Fetch closing prices, day changes, and 52-week ranges for all positions."""
    prices      = {}
    prev_prices = {}
    wk52        = {}

    # Equities & ETFs — batch download
    eq_syms = [p["symbol"] for p in POSITIONS if p["asset_type"] in ("ETF", "Equity")]
    print(f"Fetching equity/ETF prices: {eq_syms}")
    raw = yf.download(eq_syms, period="5d", interval="1d",
                      auto_adjust=True, progress=False)

    close = raw["Close"].dropna(how="all")
    if close.empty:
        raise RuntimeError("yfinance returned no equity data — market may be closed or API issue")

    data_date = str(close.index[-1].date())
    print(f"  Market data date: {data_date}")

    for sym in eq_syms:
        try:
            series = close[sym].dropna()
            prices[sym]      = round(float(series.iloc[-1]), 4)
            prev_prices[sym] = round(float(series.iloc[-2]), 4) if len(series) >= 2 else prices[sym]
        except Exception as e:
            print(f"  Warning: {sym} — {e}", file=sys.stderr)
            prices[sym] = prev_prices[sym] = 0.0

    # 52-week high/low from fast_info
    for sym in eq_syms:
        try:
            fi = yf.Ticker(sym).fast_info
            wk52[sym] = {
                "low":  round(float(fi.fifty_two_week_low),  2),
                "high": round(float(fi.fifty_two_week_high), 2),
            }
        except Exception:
            wk52[sym] = {"low": None, "high": None}

    # Options — individual Ticker calls
    for pos in POSITIONS:
        if pos["asset_type"] != "Option":
            continue
        sym = pos["symbol"]
        print(f"Fetching option:  {sym}")
        try:
            t    = yf.Ticker(sym)
            info = t.info
            bid  = float(info.get("bid")  or 0)
            ask  = float(info.get("ask")  or 0)
            if bid > 0 and ask > 0:
                price = (bid + ask) / 2.0
            else:
                price = float(
                    info.get("regularMarketPrice") or
                    info.get("lastPrice")          or
                    info.get("previousClose")      or 0
                )
            prev = float(
                info.get("regularMarketPreviousClose") or
                info.get("previousClose")              or price
            )
            prices[sym]      = round(price, 4)
            prev_prices[sym] = round(prev,  4)
            lo = info.get("fiftyTwoWeekLow")
            hi = info.get("fiftyTwoWeekHigh")
            wk52[sym] = {
                "low":  round(float(lo), 2) if lo else None,
                "high": round(float(hi), 2) if hi else None,
            }
        except Exception as e:
            print(f"  Warning: {sym} — {e}", file=sys.stderr)
            prices[sym] = prev_prices[sym] = 0.0
            wk52[sym]   = {"low": None, "high": None}

    # Day changes
    day_changes = {}
    for pos in POSITIONS:
        sym = pos["symbol"]
        p   = prices.get(sym, 0)
        pp  = prev_prices.get(sym, p)
        mv      = pos["qty"] * p  * pos["multiplier"]
        mv_prev = pos["qty"] * pp * pos["multiplier"]
        day_changes[sym] = {
            "pct": round((p - pp) / pp * 100, 2) if pp else 0.0,
            "usd": round(mv - mv_prev, 2),
        }

    return data_date, prices, wk52, day_changes


# ── Portfolio Maths ───────────────────────────────────────────────────────────

def moving_average(series, n):
    if len(series) < n:
        return None
    return round(sum(series[-n:]) / n, 4)


def compute_schwab_value(prices):
    return round(sum(
        pos["qty"] * prices.get(pos["symbol"], 0) * pos["multiplier"]
        for pos in POSITIONS
    ), 2)


def pct_chg(curr, prev):
    return round((curr - prev) / prev * 100, 2) if prev else 0.0


def compute_metrics(schwab_value, data_date, history):
    today_total = round(schwab_value + OTHER_ASSETS, 2)
    share_price = round(today_total / TOTAL_SHARES, 4)

    daily     = history["daily"]
    sp_hist   = [d["share_price"] for d in daily]
    sp_series = sp_hist + [share_price]

    ma30 = moving_average(sp_series, 30)
    ma50 = moving_average(sp_series, 50)
    ma90 = moving_average(sp_series, 90)

    prev_sp = sp_hist[-1]  if sp_hist            else share_price
    sp_1w   = sp_hist[-5]  if len(sp_hist) >= 5  else sp_hist[0] if sp_hist else share_price
    sp_1m   = sp_hist[-21] if len(sp_hist) >= 21 else sp_hist[0] if sp_hist else share_price

    ytd_start = f"{data_date[:4]}-01-01"
    ytd_entry = next((d for d in reversed(daily) if d["date"] <= ytd_start),
                     daily[0] if daily else None)
    sp_ytd = ytd_entry["share_price"] if ytd_entry else share_price

    change_1d  = round(share_price - prev_sp, 4)
    change_1w  = round(share_price - sp_1w,   4)
    change_1m  = round(share_price - sp_1m,   4)
    change_ytd = round(share_price - sp_ytd,  4)

    inc_price      = history.get("inception_price", sp_series[0])
    change_inc     = round(share_price - inc_price, 4)
    change_inc_pct = pct_chg(share_price, inc_price)

    inc_date = date.fromisoformat(INCEPTION_DATE)
    today    = date.fromisoformat(data_date)
    years    = max((today - inc_date).days / 365.25, 0.01)
    cagr     = round(((share_price / inc_price) ** (1.0 / years) - 1) * 100, 2) if inc_price > 0 else 0.0

    max_price = history.get("max_price", share_price)
    max_date  = history.get("max_date",  data_date)
    min_price = history.get("min_price", share_price)
    min_date  = history.get("min_date",  data_date)
    if share_price > max_price:
        max_price, max_date = share_price, data_date
    if share_price < min_price:
        min_price, min_date = share_price, data_date

    drawdown_pct   = round((share_price - max_price) / max_price * 100, 2) if max_price else 0.0
    drawdown_usd   = round(share_price - max_price, 4)
    days_since_max = (today - date.fromisoformat(max_date)).days

    return {
        "today_total":    today_total,
        "share_price":    share_price,
        "ma30": ma30, "ma50": ma50, "ma90": ma90,
        "change_1d":      change_1d,    "change_1d_pct":  pct_chg(share_price, prev_sp),
        "change_1w":      change_1w,    "change_1w_pct":  pct_chg(share_price, sp_1w),
        "change_1m":      change_1m,    "change_1m_pct":  pct_chg(share_price, sp_1m),
        "change_ytd":     change_ytd,   "change_ytd_pct": pct_chg(share_price, sp_ytd),
        "change_inc":     change_inc,   "change_inc_pct": change_inc_pct,
        "cagr":           cagr,
        "max_price": max_price, "max_date": max_date,
        "min_price": min_price, "min_date": min_date,
        "drawdown_pct": drawdown_pct, "drawdown_usd": drawdown_usd,
        "days_since_max": days_since_max,
        "price_vs_ma30":  round((share_price / ma30 - 1) * 100, 2) if ma30 else None,
        "price_vs_ma90":  round((share_price / ma90 - 1) * 100, 2) if ma90 else None,
    }


# ── data.json Builder ─────────────────────────────────────────────────────────

def build_data_json(data_date, schwab_value, prices, wk52, day_changes, metrics, history):
    sp = metrics["share_price"]

    # Members
    members = {}
    for key, m in MEMBERS.items():
        tot = m["shares_a"] + m["shares_b"]
        members[key] = {
            "name":         m["name"],
            "shares_a":     m["shares_a"],
            "shares_b":     m["shares_b"],
            "total_shares": round(tot, 4),
            "pct":          round(tot / TOTAL_SHARES * 100, 4),
            "value":        round(tot * sp, 2),
            "change_1d":    round(tot * metrics["change_1d"], 2),
        }

    # chart_3m — last 91 trading days + today
    all_daily = history["daily"]
    base      = all_daily[-91:]
    chart_3m  = []
    for i, d in enumerate(base):
        idx    = len(all_daily) - len(base) + i
        sp_sub = [x["share_price"] for x in all_daily[: idx + 1]]
        chart_3m.append({
            "date":        d["date"],
            "schwab":      d["schwab"],
            "total":       d["total"],
            "share_price": d["share_price"],
            "ma50":        moving_average(sp_sub, 50),
        })
    chart_3m.append({
        "date":        data_date,
        "schwab":      schwab_value,
        "total":       metrics["today_total"],
        "share_price": sp,
        "ma50":        metrics["ma50"],
    })
    chart_3m = chart_3m[-91:]

    # chart_alltime — monthly
    chart_alltime = [dict(e) for e in history.get("monthly", [])]
    cur_month = data_date[:7] + "-01"
    if chart_alltime and chart_alltime[-1]["date"][:7] == data_date[:7]:
        chart_alltime[-1] = {"date": cur_month, "total": metrics["today_total"], "share_price": sp}
    else:
        chart_alltime.append({"date": cur_month, "total": metrics["today_total"], "share_price": sp})

    # Holdings
    total_cost = sum(p["cost_basis"] for p in POSITIONS)
    positions  = []
    for pos in POSITIONS:
        sym   = pos["symbol"]
        price = prices.get(sym, 0)
        mv    = round(pos["qty"] * price * pos["multiplier"], 2)
        cb    = pos["cost_basis"]
        gain_usd = round(mv - cb, 2)
        gain_pct = round((mv - cb) / abs(cb) * 100, 2) if cb else None
        pct_port = round(mv / schwab_value * 100, 2) if mv > 0 and schwab_value else None
        dc = day_changes.get(sym, {})
        w  = wk52.get(sym, {})
        positions.append({
            "symbol":           pos["display"],
            "description":      pos["description"],
            "asset_type":       pos["asset_type"],
            "qty":              pos["qty"],
            "price":            round(price, 2),
            "market_value":     mv,
            "pct_of_portfolio": pct_port,
            "cost_basis":       cb,
            "gain_pct":         gain_pct,
            "gain_usd":         gain_usd,
            "day_chg_pct":      dc.get("pct"),
            "day_chg_usd":      dc.get("usd"),
            "wk52_low":         w.get("low"),
            "wk52_high":        w.get("high"),
        })
    positions.sort(key=lambda x: abs(x["market_value"]), reverse=True)

    total_gain_usd = round(schwab_value - total_cost, 2)
    total_gain_pct = round(total_gain_usd / total_cost * 100, 2) if total_cost else 0.0

    return {
        "updated": data_date,
        "portfolio": {
            "schwab_value":   schwab_value,
            "total_value":    metrics["today_total"],
            "share_price":    sp,
            "ma30":           metrics["ma30"],
            "ma50":           metrics["ma50"],
            "ma90":           metrics["ma90"],
            "change_1d":      metrics["change_1d"],    "change_1d_pct":  metrics["change_1d_pct"],
            "change_1w":      metrics["change_1w"],    "change_1w_pct":  metrics["change_1w_pct"],
            "change_1m":      metrics["change_1m"],    "change_1m_pct":  metrics["change_1m_pct"],
            "change_ytd":     metrics["change_ytd"],   "change_ytd_pct": metrics["change_ytd_pct"],
            "change_inc":     metrics["change_inc"],   "change_inc_pct": metrics["change_inc_pct"],
            "cagr":           metrics["cagr"],
            "max_price":      metrics["max_price"],    "max_date":       metrics["max_date"],
            "min_price":      metrics["min_price"],    "min_date":       metrics["min_date"],
            "drawdown_pct":   metrics["drawdown_pct"], "drawdown_usd":   metrics["drawdown_usd"],
            "days_since_max": metrics["days_since_max"],
            "price_vs_ma30":  metrics["price_vs_ma30"],
            "price_vs_ma90":  metrics["price_vs_ma90"],
        },
        "shares": {
            "total_a": round(sum(m["shares_a"] for m in MEMBERS.values()), 2),
            "total_b": round(sum(m["shares_b"] for m in MEMBERS.values()), 4),
            "total":   TOTAL_SHARES,
        },
        "members":       members,
        "chart_3m":      chart_3m,
        "chart_alltime": chart_alltime,
        "holdings": {
            "as_of":          data_date,
            "source":         "Yahoo Finance (live prices)",
            "total_value":    schwab_value,
            "total_cost":     round(total_cost, 2),
            "total_gain_pct": total_gain_pct,
            "total_gain_usd": total_gain_usd,
            "positions":      positions,
        },
    }


# ── History Updater ───────────────────────────────────────────────────────────

def update_history(history, data_date, schwab_value, total_value, share_price, metrics, chart_alltime):
    daily = history.setdefault("daily", [])
    entry = {"date": data_date, "schwab": schwab_value, "total": total_value, "share_price": share_price}
    if daily and daily[-1]["date"] == data_date:
        daily[-1] = entry   # same-day re-run: overwrite
    else:
        daily.append(entry)
    history["daily"]   = daily[-365:]
    history["monthly"] = chart_alltime
    history["max_price"] = metrics["max_price"]
    history["max_date"]  = metrics["max_date"]
    history["min_price"] = metrics["min_price"]
    history["min_date"]  = metrics["min_date"]
    return history


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    script_dir   = Path(__file__).parent
    history_path = script_dir / "history.json"
    data_path    = script_dir / "data.json"

    # Load history
    if history_path.exists():
        history = json.loads(history_path.read_text())
    else:
        print("WARNING: history.json not found — starting with defaults", file=sys.stderr)
        history = {
            "inception_price": 7.7434,
            "max_price": 12.5475, "max_date": "2025-10-06",
            "min_price":  6.003,  "min_date": "2026-02-23",
            "daily": [], "monthly": [],
        }

    # Fetch prices
    data_date, prices, wk52, day_changes = fetch_all_prices()

    # Avoid duplicate entries (same-day re-run) unless --force passed
    daily = history.get("daily", [])
    if daily and daily[-1]["date"] == data_date and "--force" not in sys.argv:
        print(f"Already up to date for {data_date}. Pass --force to override.")
        return 0

    # Compute
    schwab_value = compute_schwab_value(prices)
    metrics      = compute_metrics(schwab_value, data_date, history)
    data         = build_data_json(data_date, schwab_value, prices, wk52, day_changes, metrics, history)

    # Update history
    history = update_history(
        history, data_date, schwab_value,
        metrics["today_total"], metrics["share_price"],
        metrics, data["chart_alltime"]
    )

    # Write files
    data_path.write_text(json.dumps(data, indent=2))
    history_path.write_text(json.dumps(history, indent=2))

    print(f"data.json    written — {data_path.stat().st_size:,} bytes")
    print(f"history.json written — {history_path.stat().st_size:,} bytes  ({len(history['daily'])} daily entries)")
    print(f"  Date: {data_date} | Share Price: ${metrics['share_price']:.4f} | NAV: ${metrics['today_total']:,.2f}")
    print(f"  Schwab: ${schwab_value:,.2f} | MA30: {metrics['ma30']} | MA50: {metrics['ma50']} | MA90: {metrics['ma90']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
