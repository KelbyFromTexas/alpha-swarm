from pathlib import Path
p = Path("/workspace/pairfeed/cycle_3m.py")
t = p.read_text()

old_append = '''            pairs.append({
                "mint": mint,
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "creator": item.get("creator") or item.get("traderPublicKey"),
                "uri": item.get("uri"),
                "pump_url": f"https://pump.fun/coin/{mint}",
                "initial_buy_sol": ib,
                "created_unix": time.time(),
                "created_at": now_iso(),
            })'''
new_append = '''            mcap = item.get("marketCapSol")
            try:
                mcap = float(mcap) if mcap is not None else None
            except Exception:
                mcap = None
            vsol = item.get("vSolInBondingCurve") or item.get("virtualSolReserves")
            try:
                vsol = float(vsol) if vsol is not None else None
            except Exception:
                vsol = None
            pairs.append({
                "mint": mint,
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "creator": item.get("creator") or item.get("traderPublicKey"),
                "uri": item.get("uri"),
                "pump_url": f"https://pump.fun/coin/{mint}",
                "initial_buy_sol": ib,
                "market_cap_sol": mcap,
                "v_sol": vsol,
                "bonding_curve": item.get("bondingCurveKey") or item.get("bondingCurve"),
                "created_unix": time.time(),
                "created_at": now_iso(),
            })'''
if old_append not in t:
    raise SystemExit("append block missing")
t = t.replace(old_append, new_append, 1)

old_scored = '''        scored.append({
            "mint": p["mint"],
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "creator": p.get("creator"),
            "pump_url": p.get("pump_url"),
            "age_minutes": age_min,
            "initial_buy_sol": p.get("initial_buy_sol"),
            **s,
        })'''
new_scored = '''        scored.append({
            "mint": p["mint"],
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "creator": p.get("creator"),
            "pump_url": p.get("pump_url"),
            "age_minutes": age_min,
            "initial_buy_sol": p.get("initial_buy_sol"),
            "market_cap_sol": p.get("market_cap_sol"),
            "v_sol": p.get("v_sol"),
            "bonding_curve": p.get("bonding_curve"),
            **s,
        })'''
if old_scored not in t:
    raise SystemExit("scored block missing")
t = t.replace(old_scored, new_scored, 1)

old_el = '''    buy_candidate = None
    eligible = [
        x for x in scored
        if (not x["rug_flag"]) and x.get("survivability") is not None
        and x["survivability"] >= 6.5
        and 2 <= (x.get("age_minutes") or 0) <= 45
    ]
    if kill_on:
        eligible = []
    if eligible:
        eligible.sort(key=lambda x: (-(x["survivability"] or 0), x.get("age_minutes") or 99))
        e = eligible[0]
        buy_candidate = {
            "mint": e["mint"], "symbol": e["symbol"], "name": e["name"],
            "survivability": e["survivability"], "age_minutes": e["age_minutes"],
            "pump_url": e["pump_url"], "recommend": e["recommend"],
            "hard_fails": e.get("hard_fails") or [], "rug_flag": e.get("rug_flag", False),
        }'''
new_el = '''    buy_candidate = None
    eligible = [
        x for x in scored
        if (not x.get("rug_flag"))
        and not (x.get("hard_fails") or [])
        and x.get("survivability") is not None
        and 5.0 <= float(x["survivability"]) <= 9.4
    ]
    if eligible:
        eligible.sort(key=lambda x: (-(x["survivability"] or 0), x.get("age_minutes") or 99))
        e = eligible[0]
        buy_candidate = {
            "mint": e["mint"],
            "symbol": e["symbol"],
            "name": e["name"],
            "creator": e.get("creator"),
            "survivability": e["survivability"],
            "age_minutes": e["age_minutes"],
            "pump_url": e["pump_url"],
            "recommend": "advance",
            "hard_fails": e.get("hard_fails") or [],
            "rug_flag": False,
            "mode": "lenient",
            "entry_hints": {
                "mint": e["mint"],
                "pump_url": e["pump_url"],
                "market_cap_sol": e.get("market_cap_sol"),
                "v_sol": e.get("v_sol"),
                "initial_buy_sol": e.get("initial_buy_sol"),
                "asof_sample": None,
            },
        }
        if kill_on:
            buy_candidate["recommend"] = "watch"
            buy_candidate["kill_switch"] = True'''
if old_el not in t:
    raise SystemExit("eligible block missing")
t = t.replace(old_el, new_el, 1)

old_bl = '''    if not buy_candidate:
        blockers.append("buy_candidate null: no rug_flag=false AND surv>=6.5 AND age 2-45m (fresh window often <2m)")'''
new_bl = '''    blockers.append("lenient: buy_candidate = best non-hard-fail/non-slur with surv 5-9.4 (no fake 10.0)")
    if not buy_candidate:
        blockers.append("buy_candidate null: no row cleared hard fails with surv in 5-9.4")'''
if old_bl not in t:
    raise SystemExit("blocker block missing")
t = t.replace(old_bl, new_bl, 1)

p.write_text(t)
print("patched")
