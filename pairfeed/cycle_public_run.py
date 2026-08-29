#!/usr/bin/env python3
"""Fresh 3m cycle: PumpPortal sample, gated boards, tally line. Never print keys."""
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

from gate import filter_pairs, write_stream_boards, IGNORE_MINT
import cycle_now as cn

ENV_PATH = Path("/home/box/agent-data/projects/alpha-swarm/.env")
SLIM = Path("/workspace/pairfeed/live-slim.json")
CYCLE = Path("/workspace/pairfeed/cycle.json")
TALLY = Path("/workspace/alpha-swarm-launch/TALLY_BOARD.txt")
AUDIT = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
MAX_SEC = 45
MAX_PAIRS = 20


def load_env(path):
    d = {}
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def mint_of(d):
    v = d.get("mint") or d.get("tokenMint")
    return v if isinstance(v, str) and len(v) >= 32 else ""


def tx_type(d):
    return str(d.get("txType") or d.get("tx_type") or d.get("type") or "").lower()


def collect(key):
    import websocket
    # public WS only (automation binder-safe); ignore key
    url = "wss://pumpportal.fun/api/data"
    ws = websocket.create_connection(url, timeout=12)
    ws.settimeout(1.0)
    ws.send(json.dumps({"method": "subscribeNewToken"}))
    pairs, seen, errors = [], set(), []
    t0 = time.time()
    deadline = t0 + MAX_SEC
    while time.time() < deadline and len(pairs) < MAX_PAIRS:
        try:
            raw = ws.recv()
        except websocket.WebSocketTimeoutException:
            continue
        except Exception as e:
            errors.append(type(e).__name__)
            break
        try:
            d = json.loads(raw)
        except Exception:
            continue
        items = d if isinstance(d, list) else [d]
        for item in items:
            if not isinstance(item, dict):
                continue
            mint = mint_of(item)
            tx = tx_type(item)
            if not mint or mint == IGNORE_MINT or mint in seen:
                continue
            if tx in ("buy", "sell", "migration", "migrate"):
                continue
            is_create = tx in ("create", "newtoken", "new_token") or (item.get("name") and item.get("symbol"))
            if not is_create:
                continue
            seen.add(mint)
            ib = item.get("initialBuy") or item.get("initial_buy_sol")
            try:
                ib = float(ib) if ib is not None else None
            except Exception:
                ib = None
            pairs.append({
                "mint": mint,
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "creator": item.get("creator") or item.get("traderPublicKey"),
                "uri": item.get("uri"),
                "pump_url": f"https://pump.fun/coin/{mint}",
                "initial_buy_sol": ib,
                "created_unix": time.time(),
                "created_at": now_iso(),
            })
    try:
        ws.close()
    except Exception:
        pass
    return pairs, round(time.time() - t0, 1), errors


def update_tally(asof, count, buy, omitted_n):
    buys, spent = "0", "0.00"
    if TALLY.exists():
        for line in TALLY.read_text().splitlines():
            if line.startswith("buys:"):
                buys = line.split(":", 1)[1].strip()
            if line.startswith("sol_spent:"):
                spent = line.split(":", 1)[1].strip()
    if buy:
        last = f"last_cycle: {count} pairs scored — candidate {buy.get('symbol')} surv={buy.get('survivability')} (Apex decides)"
    else:
        last = f"last_cycle: {count} pairs scored — NO BUY (omitted={omitted_n})"
    TALLY.write_text(
        "\n".join([
            "TALLY — micro trenches (0.01 SOL)",
            f"asof: {asof}",
            f"buys: {buys}",
            f"sol_spent: {spent}",
            "",
            last,
            "rule: every 3m; buy 0.01 only if anti-rug pass + tape-backed comps (not bare surv=10)",
            "",
            "(no fills yet)" if buys in ("0", "0.00") else "",
            "Kill rate is the product.",
            "",
        ])
    )


def main():
    env = {}
    key = ""
    rpc = "https://api.mainnet-beta.solana.com"
    raw_pairs, elapsed, errors = collect(key)
    kept, omitted = filter_pairs(raw_pairs)
    asof_pre = now_iso()
    stamp = now_stamp()
    prefix = f"SCORED PAIRS — cycle {asof_pre} (every 3m)\n\n"

    # interim board so stream isn't stale during score
    write_stream_boards(
        "\n".join([
            "PAIR FEED — live",
            f"asof: {asof_pre}",
            f"count: {len(kept)}",
            "",
            "SYMBOL | MINT_SHORT | NAME | age | surv | rec",
            "------ | ---------- | ---- | --- | ---- | ---",
        ] + [
            f"{(p.get('symbol') or '?').replace('|','/')} | {cn.mint_short(p.get('mint'))} | {(p.get('name') or '?').replace('|','/')} | … | … | …"
            for p in kept[:40]
        ]) + "\n",
        scored_prefix=prefix,
    )

    largest_map = {}
    if rpc and kept:
        from concurrent.futures import ThreadPoolExecutor, as_completed
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(cn.rpc_largest, rpc, p["mint"]) for p in kept]
            for fut in as_completed(futs):
                mint, val = fut.result()
                largest_map[mint] = val

    now = time.time()
    scored = []
    for p in kept:
        age_min = round((now - float(p.get("created_unix") or now)) / 60.0, 2)
        s = cn.score_one(p, largest_map.get(p["mint"]) or [], age_min, p.get("initial_buy_sol"))
        scored.append({
            "mint": p["mint"],
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "creator": p.get("creator"),
            "pump_url": p.get("pump_url"),
            "age_minutes": age_min,
            "initial_buy_sol": p.get("initial_buy_sol"),
            **s,
        })

    kill_on = Path("/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on").exists()
    buy_candidate = None
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
        }

    asof = now_iso()
    prefix = f"SCORED PAIRS — cycle {asof} (every 3m)\n\n"
    lines = [
        "PAIR FEED — live",
        f"asof: {asof}",
        f"count: {len(scored)}",
        "",
        "SYMBOL | MINT_SHORT | NAME | age | surv | rec",
        "------ | ---------- | ---- | --- | ---- | ---",
    ]
    for p in scored[:40]:
        surv = p.get("survivability")
        surv_s = "-" if surv is None else f"{surv:.1f}"
        lines.append(
            f"{(p.get('symbol') or '?').replace('|','/')} | {cn.mint_short(p.get('mint'))} | "
            f"{(p.get('name') or '?').replace('|','/')} | {cn.age_label(p.get('age_minutes'))} | "
            f"{surv_s} | {p.get('recommend') or '-'}"
        )
    if buy_candidate:
        lines += ["", f"buy_candidate: {buy_candidate['symbol']} {cn.mint_short(buy_candidate['mint'])} surv={buy_candidate['survivability']}"]
    else:
        lines += ["", "NO BUY this cycle", "buy_candidate: none"]
    write_stream_boards("\n".join(lines) + "\n", scored_prefix=prefix)

    blockers = [
        f"source: PumpPortal subscribeNewToken {elapsed}s raw={len(raw_pairs)} kept={len(scored)}",
        "write_stream_boards PAIR_FEED_BOARD.txt + SCORED_PAIRS.txt",
    ]
    if omitted:
        blockers.append("omitted_counts:" + json.dumps(omitted, separators=(",", ":")))
    if errors:
        blockers.append("ws_errors:" + ",".join(errors[:6]))
    if kill_on:
        blockers.append("kill-switch.on — buy recommend suppressed")
    if not buy_candidate:
        blockers.append("buy_candidate null: no rug_flag=false AND surv>=6.5 AND age 2-45m (fresh window often <2m)")

    feed = {
        "feed_id": f"pf-cycle-{stamp}",
        "asof": asof,
        "count": len(scored),
        "new_pairs": scored,
        "buy_candidate": buy_candidate,
        "blockers": blockers,
        "sample_seconds": elapsed,
    }
    CYCLE.write_text(json.dumps(feed, indent=2))
    SLIM.write_text(json.dumps({
        "feed_id": feed["feed_id"], "asof": asof,
        "new_pairs": [{"mint": p["mint"], "name": p["name"], "symbol": p["symbol"],
                       "creator": p["creator"], "pump_url": p["pump_url"]} for p in scored],
        "blockers": blockers,
    }, indent=2))
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / f"pair-scan-{stamp}.json").write_text(json.dumps({
        "feed_id": feed["feed_id"], "asof": asof, "count": len(scored),
        "mints": [{"mint": p["mint"], "symbol": p.get("symbol"), "survivability": p["survivability"],
                   "rug_flag": p["rug_flag"]} for p in scored],
        "buy_candidate": buy_candidate, "omitted": omitted,
    }, indent=2))
    update_tally(asof, len(scored), buy_candidate, sum(omitted.values()) if omitted else 0)
    print(json.dumps({
        "feed_id": feed["feed_id"], "asof": asof, "count": len(scored),
        "buy_candidate": None if not buy_candidate else buy_candidate["symbol"],
        "omitted": omitted, "elapsed": elapsed,
    }))


if __name__ == "__main__":
    main()
