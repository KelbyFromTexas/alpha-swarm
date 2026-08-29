#!/usr/bin/env python3
"""ALPHA pair scan cycle — public WS + public RPC only. Never print keys. No buys."""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/workspace/pairfeed")
import gate
import cycle_now as cn

RPC = "https://api.mainnet-beta.solana.com"
WS_URL = "wss://pumpportal.fun/api/data"
MAX_SEC = 40
MAX_PAIRS = 20
TALLY_BOARD = Path("/workspace/alpha-swarm-launch/TALLY_BOARD.txt")
TALLY_JSONL = Path("/home/box/agent-data/projects/alpha-swarm/data/tally.jsonl")
AUDIT_DIR = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
CYCLE = Path("/workspace/pairfeed/cycle.json")
SLIM = Path("/workspace/pairfeed/live-slim.json")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def mint_of(d):
    v = d.get("mint") or d.get("tokenMint")
    return v if isinstance(v, str) and len(v) >= 32 else ""


def tx_type(d):
    return str(d.get("txType") or d.get("tx_type") or d.get("type") or "").lower()


def collect_pairs():
    import websocket

    ws = websocket.create_connection(WS_URL, timeout=12)
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
            if not mint or mint == gate.IGNORE_MINT or mint in seen:
                continue
            if tx in ("buy", "sell", "migration", "migrate"):
                continue
            is_create = tx in ("create", "newtoken", "new_token") or (
                item.get("name") and item.get("symbol")
            )
            if not is_create:
                continue
            seen.add(mint)
            ib = item.get("initialBuy") or item.get("initial_buy_sol")
            try:
                ib = float(ib) if ib is not None else None
            except Exception:
                ib = None
            pairs.append(
                {
                    "mint": mint,
                    "name": item.get("name"),
                    "symbol": item.get("symbol"),
                    "creator": item.get("creator") or item.get("traderPublicKey"),
                    "uri": item.get("uri"),
                    "pump_url": f"https://pump.fun/coin/{mint}",
                    "initial_buy_sol": ib,
                    "created_unix": time.time(),
                    "created_at": now_iso(),
                }
            )
    try:
        ws.close()
    except Exception:
        pass
    return pairs, round(time.time() - t0, 1), errors


def tape_backed(components: dict) -> bool:
    if not isinstance(components, dict):
        return False
    return all(
        components.get(k) is not None
        for k in ("buy_persistence", "tape_quality", "creator_skin")
    )


def pick_buy_candidate(scored):
    """Strict gate: surv>=6.5, rug_flag=false, age 2-45m, recommend=advance, tape-backed."""
    kill_on = Path(
        "/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on"
    ).exists()
    if kill_on:
        return None, "kill_switch_on"
    eligible = []
    for x in scored:
        comps = x.get("components") or {}
        age = x.get("age_minutes")
        surv = x.get("survivability")
        if x.get("rug_flag"):
            continue
        if surv is None or surv < 6.5:
            continue
        if age is None or not (2 <= age <= 45):
            continue
        if x.get("recommend") != "advance":
            continue
        if not tape_backed(comps):
            continue
        eligible.append(x)
    if not eligible:
        return None, "tape_missing_watch_only"
    eligible.sort(key=lambda x: (-(x["survivability"] or 0), x.get("age_minutes") or 99))
    e = eligible[0]
    return (
        {
            "symbol": e.get("symbol"),
            "mint": e.get("mint"),
            "surv": e.get("survivability"),
            "age": e.get("age_minutes"),
            "recommend": e.get("recommend"),
            "tape_backed": True,
        },
        "eligible",
    )


def update_tally_board(asof, count, buy, omitted_n):
    buys, spent = "0", "0.00"
    if TALLY_BOARD.exists():
        for line in TALLY_BOARD.read_text().splitlines():
            if line.startswith("buys:"):
                buys = line.split(":", 1)[1].strip()
            if line.startswith("sol_spent:"):
                spent = line.split(":", 1)[1].strip()
    if buy:
        last = (
            f"last_cycle: {count} pairs scored — candidate {buy.get('symbol')} "
            f"surv={buy.get('surv')} (Apex decides)"
        )
    else:
        last = f"last_cycle: {count} pairs scored — NO BUY (omitted={omitted_n})"
    TALLY_BOARD.write_text(
        "\n".join(
            [
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
            ]
        )
    )


def main():
    errors = []
    boards_overwritten = False
    raw_pairs, elapsed, ws_errors = collect_pairs()
    errors.extend(ws_errors)
    kept, omitted = gate.filter_pairs(raw_pairs)
    asof_pre = now_iso()
    stamp = now_stamp()
    prefix = f"SCORED PAIRS — cycle {asof_pre}\n\n"

    # interim board
    gate.write_stream_boards(
        "\n".join(
            [
                "PAIR FEED — live",
                f"asof: {asof_pre}",
                f"count: {len(kept)}",
                "",
                "SYMBOL | MINT_SHORT | NAME | age | surv | rec",
                "------ | ---------- | ---- | --- | ---- | ---",
            ]
            + [
                f"{(p.get('symbol') or '?').replace('|','/')} | {cn.mint_short(p.get('mint'))} | "
                f"{(p.get('name') or '?').replace('|','/')} | … | … | …"
                for p in kept[:40]
            ]
        )
        + "\n",
        scored_prefix=prefix,
    )
    boards_overwritten = True

    largest_map = {}
    if kept:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(cn.rpc_largest, RPC, p["mint"]) for p in kept]
            for fut in as_completed(futs):
                try:
                    mint, val = fut.result()
                    largest_map[mint] = val
                except Exception as e:
                    errors.append(f"rpc:{type(e).__name__}")

    now = time.time()
    scored = []
    for p in kept:
        age_min = round((now - float(p.get("created_unix") or now)) / 60.0, 2)
        s = cn.score_one(
            p, largest_map.get(p["mint"]) or [], age_min, p.get("initial_buy_sol")
        )
        scored.append(
            {
                "mint": p["mint"],
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "creator": p.get("creator"),
                "pump_url": p.get("pump_url"),
                "age_minutes": age_min,
                "initial_buy_sol": p.get("initial_buy_sol"),
                **s,
            }
        )

    buy_candidate, gate_reason = pick_buy_candidate(scored)
    asof = now_iso()
    stamp = now_stamp()
    prefix = f"SCORED PAIRS — cycle {asof}\n\n"
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
        lines += [
            "",
            f"buy_candidate: {buy_candidate['symbol']} {cn.mint_short(buy_candidate['mint'])} "
            f"surv={buy_candidate['surv']}",
        ]
    else:
        lines += ["", "NO BUY this cycle", "buy_candidate: none"]
    gate.write_stream_boards("\n".join(lines) + "\n", scored_prefix=prefix)
    boards_overwritten = True

    feed_id = f"pf-cycle-{stamp}"
    blockers = [
        f"source: PumpPortal subscribeNewToken {elapsed}s raw={len(raw_pairs)} kept={len(scored)}",
        "write_stream_boards PAIR_FEED_BOARD.txt + SCORED_PAIRS.txt",
        f"buy_gate: {gate_reason}",
    ]
    if omitted:
        blockers.append("omitted_counts:" + json.dumps(omitted, separators=(",", ":")))
    if errors:
        blockers.append("errors:" + ",".join(errors[:8]))

    feed = {
        "feed_id": feed_id,
        "asof": asof,
        "count": len(scored),
        "new_pairs": scored,
        "buy_candidate": buy_candidate,
        "blockers": blockers,
        "sample_seconds": elapsed,
        "omitted": omitted,
    }
    CYCLE.write_text(json.dumps(feed, indent=2))
    SLIM.write_text(
        json.dumps(
            {
                "feed_id": feed_id,
                "asof": asof,
                "new_pairs": [
                    {
                        "mint": p["mint"],
                        "name": p["name"],
                        "symbol": p["symbol"],
                        "creator": p["creator"],
                        "pump_url": p["pump_url"],
                    }
                    for p in scored
                ],
                "blockers": blockers,
            },
            indent=2,
        )
    )

    AUDIT_DIR.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT_DIR / f"pair-scan-{stamp}.json"
    audit_path.write_text(
        json.dumps(
            {
                "feed_id": feed_id,
                "asof": asof,
                "count": len(scored),
                "mints": [
                    {
                        "mint": p["mint"],
                        "symbol": p.get("symbol"),
                        "survivability": p["survivability"],
                        "rug_flag": p["rug_flag"],
                        "recommend": p.get("recommend"),
                        "age_minutes": p.get("age_minutes"),
                    }
                    for p in scored
                ],
                "buy_candidate": buy_candidate,
                "omitted": omitted,
                "gate_reason": gate_reason,
            },
            indent=2,
        )
    )

    update_tally_board(
        asof, len(scored), buy_candidate, sum(omitted.values()) if omitted else 0
    )

    TALLY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TALLY_JSONL.open("a", encoding="utf-8") as f:
        f.write(
            json.dumps(
                {
                    "ts": asof,
                    "action": "buy" if buy_candidate else "no_buy",
                    "pairs_scored": len(scored),
                    "buy_candidate": buy_candidate,
                    "gate": gate_reason,
                    "omitted": omitted,
                }
            )
            + "\n"
        )

    summary = {
        "asof": asof,
        "feed_id": feed_id,
        "count_scored": len(scored),
        "omitted": omitted,
        "buy_candidate": buy_candidate,
        "audit_path": str(audit_path),
        "boards_overwritten": boards_overwritten,
        "errors": errors[:8],
        "sample_seconds": elapsed,
        "raw_count": len(raw_pairs),
        "gate_reason": gate_reason,
    }
    print(json.dumps(summary))


if __name__ == "__main__":
    main()
