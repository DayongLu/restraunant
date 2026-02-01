#!/usr/bin/env python3
"""Forward-test strategy for HK.09988 (BABA-W) on moomoo/Futu OpenD SIMULATE.

Rules (user-chosen):
- Horizon: ~1 month (30 days) forward test.
- Buy: 3 tranches at support levels
  1) 20-day low
  2) 50-day low
  3) 200-day SMA
  Allocation: 30% / 35% / 35% of configured cash budget.
- Sell (Rule A):
  - Take-profit 1: +5% vs avg cost, sell 1/3
  - Take-profit 2: +10% vs avg cost, sell 1/3
  - Remaining: trailing stop, exit if price falls 5% from max price since entry

This script is designed to be run repeatedly (cron). It will:
- compute levels from kline
- maintain limit orders (buy + sell) in SIMULATE
- maintain a state JSON
- stay quiet unless it places/cancels an order or the test ends

NOT FINANCIAL ADVICE.
"""

from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import pandas as pd
from futu import (
    OpenQuoteContext,
    OpenSecTradeContext,
    Market,
    SecurityType,
    SubType,
    AuType,
    KLType,
    TrdMarket,
    TrdEnv,
    TrdSide,
    OrderType,
    ModifyOrderOp,
)


def now_ts() -> int:
    return int(time.time())


def round_hk_price(px: float) -> float:
    # Simplified tick rounding; real tick sizes vary.
    return round(px * 10) / 10.0


def get_lot_size(code: str, host: str, port: int) -> int:
    q = OpenQuoteContext(host=host, port=port)
    try:
        ret, data = q.get_stock_basicinfo(Market.HK, SecurityType.STOCK)
        if ret == 0:
            row = data[data["code"] == code]
            if not row.empty:
                return int(row.iloc[0]["lot_size"])
    finally:
        q.close()
    return 100


def load_state(path: str) -> dict:
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {}


def save_state(path: str, state: dict):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2, sort_keys=True)
    os.replace(tmp, path)


def sma(vals: list[float], period: int) -> float | None:
    if len(vals) < period:
        return None
    return sum(vals[-period:]) / period


def get_kline(code: str, host: str, port: int, count: int = 260) -> pd.DataFrame:
    q = OpenQuoteContext(host=host, port=port)
    try:
        # Must subscribe before calling get_cur_kline on some OpenD setups.
        ret, msg = q.subscribe([code], [SubType.K_DAY], is_first_push=False)
        if ret != 0:
            raise RuntimeError(f"subscribe K_DAY error: {msg}")

        ret, data = q.get_cur_kline(code, num=count, ktype=KLType.K_DAY, autype=AuType.QFQ)
        if ret != 0:
            raise RuntimeError(f"get_cur_kline error: {data}")
        return data
    finally:
        try:
            q.unsubscribe([code], [SubType.K_DAY])
        except Exception:
            pass
        q.close()


def get_last_price(code: str, host: str, port: int) -> tuple[float, str]:
    q = OpenQuoteContext(host=host, port=port)
    try:
        ret, snap = q.get_market_snapshot([code])
        if ret != 0:
            raise RuntimeError(f"snapshot error: {snap}")
        row = snap.iloc[0]
        return float(row["last_price"]), str(row.get("update_time"))
    finally:
        q.close()


def get_sim_acc_id(trd: OpenSecTradeContext) -> int:
    ret, accs = trd.get_acc_list()
    if ret != 0:
        raise RuntimeError(f"get_acc_list error: {accs}")
    sim = accs[accs["trd_env"] == "SIMULATE"].iloc[0]
    return int(sim["acc_id"])


def list_orders(trd: OpenSecTradeContext, acc_id: int, code: str) -> pd.DataFrame:
    ret, df = trd.order_list_query(trd_env=TrdEnv.SIMULATE, acc_id=acc_id)
    if ret != 0:
        raise RuntimeError(f"order_list_query error: {df}")
    return df[df["code"] == code].copy()


def list_positions(trd: OpenSecTradeContext, acc_id: int, code: str) -> pd.DataFrame:
    ret, df = trd.position_list_query(trd_env=TrdEnv.SIMULATE, acc_id=acc_id)
    if ret != 0:
        raise RuntimeError(f"position_list_query error: {df}")
    return df[df["code"] == code].copy()


def place_limit(trd: OpenSecTradeContext, acc_id: int, code: str, side: str, qty: int, price: float) -> tuple[int, pd.DataFrame | str]:
    return trd.place_order(
        price=float(price),
        qty=float(qty),
        code=code,
        trd_side=TrdSide.BUY if side == "BUY" else TrdSide.SELL,
        order_type=OrderType.NORMAL,
        trd_env=TrdEnv.SIMULATE,
        acc_id=acc_id,
    )


def ensure_order(trd: OpenSecTradeContext, acc_id: int, orders: pd.DataFrame, code: str, *, side: str, qty: int, price: float, price_tol: float = 0.05) -> tuple[bool, str]:
    """Ensure there is an outstanding order similar to (side, qty, price).

    We treat orders with same side and price within tolerance as already present.
    """
    if qty <= 0:
        return False, "qty<=0"

    # Consider active-ish statuses only
    active = orders[orders["order_status"].isin(["SUBMITTED", "SUBMITTING", "WAITING_SUBMIT", "SUBMIT_FAILED", "SUBMITTING_PART", "SUBMITTED_PART"])].copy()
    if not active.empty:
        same_side = active[active["trd_side"].astype(str) == side]
        if not same_side.empty:
            # if any order price close enough
            for _, r in same_side.iterrows():
                try:
                    if abs(float(r["price"]) - price) <= price_tol:
                        return False, "exists"
                except Exception:
                    continue

    # Prefer the code from the open orders dataframe when available; otherwise use the provided code.
    ret, resp = place_limit(trd, acc_id, orders.iloc[0]["code"] if len(orders) else code, side, qty, price)
    if ret != 0:
        return True, f"FAILED place {side} {qty}@{price}: {resp}"
    oid = resp.iloc[0]["order_id"] if hasattr(resp, "iloc") else "?"
    return True, f"PLACED {side} {qty}@{price} (order_id {oid})"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=11111)
    ap.add_argument("--code", default="HK.09988")
    ap.add_argument("--budget-hkd", type=float, default=1_000_000)
    ap.add_argument("--state", default="/Users/dylu/clawd/memory/strategy_baba_sim.json")
    ap.add_argument("--days", type=int, default=30)
    args = ap.parse_args()

    state = load_state(args.state)
    start_ts = state.get("start_ts")
    if not start_ts:
        start_ts = now_ts()
        state["start_ts"] = start_ts
        state["end_ts"] = start_ts + args.days * 24 * 3600
        state["max_price_since_entry"] = None
        state["initial_equity_hkd"] = None
        state["notes"] = {
            "buy_rule": "20d low / 50d low / 200d SMA, 30/35/35",
            "sell_rule": "A: +5% sell 1/3, +10% sell 1/3, trailing stop 5% on remainder",
        }

    # Connect trade
    trd = OpenSecTradeContext(filter_trdmarket=TrdMarket.HK, host=args.host, port=args.port)
    try:
        acc_id = get_sim_acc_id(trd)

        # equity snapshot (best-effort)
        if state.get("initial_equity_hkd") is None:
            try:
                ret, df = trd.accinfo_query(trd_env=TrdEnv.SIMULATE, acc_id=acc_id)
                if ret == 0 and not df.empty:
                    # fields vary; try common ones
                    for col in ["total_assets", "total_assets_hkd", "assets", "power"]:
                        if col in df.columns:
                            state["initial_equity_hkd"] = float(df.iloc[0][col])
                            break
            except Exception:
                pass

        # End condition
        if now_ts() >= int(state["end_ts"]):
            # compute current equity
            equity = None
            try:
                ret, df = trd.accinfo_query(trd_env=TrdEnv.SIMULATE, acc_id=acc_id)
                if ret == 0 and not df.empty:
                    for col in ["total_assets", "total_assets_hkd", "assets", "power"]:
                        if col in df.columns:
                            equity = float(df.iloc[0][col])
                            break
            except Exception:
                pass

            init_eq = state.get("initial_equity_hkd")
            msg = {
                "event": "END_OF_TEST",
                "code": args.code,
                "start": datetime.fromtimestamp(start_ts).isoformat(),
                "end": datetime.fromtimestamp(int(state["end_ts"])).isoformat(),
                "initial_equity_hkd": init_eq,
                "final_equity_hkd": equity,
            }
            if init_eq and equity:
                msg["return_pct"] = (equity / init_eq - 1.0) * 100
            save_state(args.state, state)
            print("STRATEGY_RESULT", json.dumps(msg, ensure_ascii=False))
            return

        # Data + levels
        k = get_kline(args.code, args.host, args.port, count=260)
        k = k.sort_values("time_key")
        # futu-api columns for kline are open/close/high/low (not *_price)
        lows = k["low"].astype(float).tolist()
        closes = k["close"].astype(float).tolist()

        low20 = min(lows[-20:]) if len(lows) >= 20 else None
        low50 = min(lows[-50:]) if len(lows) >= 50 else None
        sma200 = sma(closes, 200)

        last_price, upd = get_last_price(args.code, args.host, args.port)
        lot = get_lot_size(args.code, args.host, args.port)

        # Positions/orders
        pos = list_positions(trd, acc_id, args.code)
        orders = list_orders(trd, acc_id, args.code)

        holding_qty = 0
        avg_cost = None
        if not pos.empty:
            holding_qty = int(float(pos.iloc[0].get("qty", 0)))
            # avg_cost might be cost_price
            if "cost_price" in pos.columns:
                avg_cost = float(pos.iloc[0]["cost_price"])

        actions: list[str] = []

        # Track max since entry for trailing
        if holding_qty > 0:
            mx = state.get("max_price_since_entry")
            mx = float(mx) if mx is not None else last_price
            mx = max(mx, last_price)
            state["max_price_since_entry"] = mx
        else:
            state["max_price_since_entry"] = None

        # BUY maintenance (only if not currently holding much; allow building position regardless)
        # Combine budgets when multiple support definitions collapse to the same rounded price
        raw_levels = [
            ("LOW20", low20, args.budget_hkd * 0.30),
            ("LOW50", low50, args.budget_hkd * 0.35),
            ("SMA200", sma200, args.budget_hkd * 0.35),
        ]
        buckets: dict[float, dict] = {}
        for name, level, budget in raw_levels:
            if level is None:
                continue
            px = round_hk_price(float(level))
            b = buckets.setdefault(px, {"names": [], "budget": 0.0})
            b["names"].append(name)
            b["budget"] += float(budget)

        for px, meta in sorted(buckets.items(), key=lambda x: x[0], reverse=True):
            budget = meta["budget"]
            names = "+".join(meta["names"])
            raw_qty = int(budget // px)
            qty = (raw_qty // lot) * lot
            if qty < lot:
                qty = lot
            placed, info = ensure_order(trd, acc_id, orders, args.code, side="BUY", qty=qty, price=px)
            if placed:
                actions.append(f"{names}@{px}: {info}")

        # SELL logic (Rule A)
        if holding_qty > 0 and avg_cost:
            tp1 = round_hk_price(avg_cost * 1.05)
            tp2 = round_hk_price(avg_cost * 1.10)
            one_third = (holding_qty // 3 // lot) * lot
            if one_third < lot:
                one_third = lot

            # Place TP1 and TP2 sells if not existing
            placed, info = ensure_order(trd, acc_id, orders, args.code, side="SELL", qty=one_third, price=tp1)
            if placed:
                actions.append(f"TP1: {info}")
            placed, info = ensure_order(trd, acc_id, orders, args.code, side="SELL", qty=one_third, price=tp2)
            if placed:
                actions.append(f"TP2: {info}")

            # Trailing stop on remainder
            mx = float(state.get("max_price_since_entry") or last_price)
            trail_trigger = mx * 0.95
            # estimate remaining qty after TP orders (not perfect; but good enough)
            remaining = holding_qty - 2 * one_third
            remaining = (remaining // lot) * lot
            if remaining >= lot and last_price <= trail_trigger:
                # Place a protective sell near market
                px = round_hk_price(last_price * 0.995)
                ret, resp = place_limit(trd, acc_id, args.code, "SELL", remaining, px)
                if ret == 0:
                    oid = resp.iloc[0]["order_id"]
                    actions.append(f"TRAIL_STOP: PLACED SELL {remaining}@{px} (order_id {oid}) trigger<= {trail_trigger:.2f} (max {mx:.2f})")
                else:
                    actions.append(f"TRAIL_STOP: FAILED place SELL {remaining}@{px}: {resp}")

        save_state(args.state, state)

        if actions:
            # Short, WhatsApp-friendly
            print("BABA_STRATEGY_ACTION")
            print(f"- Code: {args.code} (SIMULATE)")
            print(f"- Last: {last_price} HKD (update {upd})")
            if low20 and low50 and sma200:
                print(f"- Supports: low20 {round_hk_price(low20)} | low50 {round_hk_price(low50)} | sma200 {round_hk_price(sma200)}")
            print("- Actions:")
            for a in actions:
                print(f"  - {a}")
        else:
            # Stay silent when nothing changed to avoid spam.
            return

    finally:
        trd.close()


if __name__ == "__main__":
    main()
