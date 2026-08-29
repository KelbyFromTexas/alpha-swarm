#!/usr/bin/env python3
"""Score a pump.fun frontend-api snapshot. No env/keys. Never print secrets."""
from __future__ import annotations

import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/workspace/pairfeed")
from gate import filter_pairs, write_stream_boards
import cycle_now as cn

SRC = Path("/tmp/pump_latest.json")
CYCLE = Path("/workspace/pairfeed/cycle.json")
SLIM = Path("/workspace/pairfeed/live-slim.json")
TALLY_BOARD = Path("/workspace/alpha-swarm-launch/TALLY_BOARD.txt")
TALLY_JSONL = Path("/home/box/agent-data/projects/alpha-swarm/data/tally.jsonl")
AUDIT = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
IGNORE = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
RPC = "https://api.mainnet-beta.solana.com"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def created_unix(row):
    ts = row.get("created_timestamp")
    if ts is None:
        return None
    try:
        x = float(ts)
    except Exception:
        return None
    if x > 1e12:
        x = x / 1000.0
    return x


def to_pair(row):
    mint = row.get("mint") or ""
    return {
        "mint": mint,
        "name": row.get("name"),
        "symbol": row.get("symbol"),
        "creator": row.get("creator"),
        "uri": row.get("metadata_uri") or row.get("image_uri"),
        "pump_url": f"https://pump.fun/coin/{mint}" if mint else "",
        "initial_buy_sol": None,
        "created_unix": created_unix(row),
        "usd_market_cap": row.get("usd_market_cap"),
        "reply_count": row.get("reply_count"),
    }


def tape_backed(p):
    c = p.get("components") or {}
    return all(c.get(k) is not None for k in ("buy_persistence", "tape_quality", "creator_skin"))


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
            f"surv={buy.get('survivability')} (Apex decides)"
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
    raw = json.loads(SRC.read_text())
    if not isinstance(raw, list):
        raise SystemExit("unexpected snapshot shape")
    pairs = [to_pair(r) for r in raw if isinstance(r, dict)]
    pairs = [p for p in pairs if p.get("mint") and p["mint"] != IGNORE]
    kept, omitted = filter_pairs(pairs)
    asof_pre = now_iso()
    prefix = f"SCORED PAIRS — cycle {asof_pre} (every 3m)\n\n"
    write_stream_boards(
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

    largest_map = {}
    if kept:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(cn.rpc_largest, RPC, p["mint"]) for p in kept]
            for fut in as_completed(futs):
                mint, val = fut.result()
                largest_map[mint] = val

    now = time.time()
    scored = []
    for p in kept:
        cu = p.get("created_unix") or now
        age_min = round((now - float(cu)) / 60.0, 2)
        s = cn.score_one(p, largest_map.get(p["mint"]) or [], age_min, p.get("initial_buy_sol"))
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

    buy_candidate = None
    eligible = []
    for x in scored:
        if x["rug_flag"]:
            continue
        if x.get("survivability") is None or x["survivability"] < 6.5:
            continue
        if not (2 <= (x.get("age_minutes") or 0) <= 45):
            continue
        if x.get("recommend") != "advance":
            continue
        if not tape_backed(x):
            continue
        eligible.append(x)
    if eligible:
        eligible.sort(key=lambda x: (-(x["survivability"] or 0), x.get("age_minutes") or 99))
        e = eligible[0]
        buy_candidate = {
            "mint": e["mint"],
            "symbol": e["symbol"],
            "name": e["name"],
            "survivability": e["survivability"],
            "age_minutes": e["age_minutes"],
            "pump_url": e["pump_url"],
            "recommend": e["recommend"],
            "hard_fails": e.get("hard_fails") or [],
            "rug_flag": e.get("rug_flag", False),
            "tape_backed": True,
        }

    asof = now_iso()
    stamp = now_stamp()
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
        lines += [
            "",
            f"buy_candidate: {buy_candidate['symbol']} {cn.mint_short(buy_candidate['mint'])} surv={buy_candidate['survivability']}",
        ]
    else:
        lines += ["", "NO BUY this cycle", "buy_candidate: none"]
    write_stream_boards("\n".join(lines) + "\n", scored_prefix=prefix)

    omitted_n = sum(omitted.values()) if omitted else 0
    blockers = [
        "source: pump.fun frontend-api-v3 coins?sort=created_timestamp",
        "write_stream_boards PAIR_FEED_BOARD.txt + SCORED_PAIRS.txt",
        "tape missing → watch/kill (buy_persistence/tape_quality unmeasured)",
    ]
    if omitted:
        blockers.append("omitted_counts:" + json.dumps(omitted, separators=(",", ":")))
    if not buy_candidate:
        blockers.append(
            "buy_candidate null: need rug_flag=false AND surv>=6.5 AND age 2-45m AND recommend=advance AND tape-backed"
        )

    feed = {
        "feed_id": f"pf-cycle-{stamp}",
        "asof": asof,
        "count": len(scored),
        "new_pairs": scored,
        "buy_candidate": buy_candidate,
        "blockers": blockers,
        "sample_seconds": 0,
    }
    CYCLE.write_text(json.dumps(feed, indent=2))
    SLIM.write_text(
        json.dumps(
            {
                "feed_id": feed["feed_id"],
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
    AUDIT.mkdir(parents=True, exist_ok=True)
    audit_path = AUDIT / f"pair-scan-{stamp}.json"
    audit_path.write_text(
        json.dumps(
            {
                "feed_id": feed["feed_id"],
                "asof": asof,
                "count": len(scored),
                "mints": [
                    {
                        "mint": p["mint"],
                        "symbol": p.get("symbol"),
                        "survivability": p["survivability"],
                        "rug_flag": p["rug_flag"],
                    }
                    for p in scored
                ],
                "buy_candidate": buy_candidate,
                "omitted": omitted,
            },
            indent=2,
        )
    )
    update_tally_board(asof, len(scored), buy_candidate, omitted_n)
    TALLY_JSONL.parent.mkdir(parents=True, exist_ok=True)
    with TALLY_JSONL.open("a") as f:
        f.write(
            json.dumps(
                {
                    "ts": asof,
                    "action": "no_buy" if not buy_candidate else "buy_candidate",
                    "pairs_scored": len(scored),
                    "buy_candidate": buy_candidate,
                    "gate": "tape_missing_watch_only" if not buy_candidate else "tape_backed_advance",
                    "omitted": omitted,
                }
            )
            + "\n"
        )
    print(
        json.dumps(
            {
                "feed_id": feed["feed_id"],
                "asof": asof,
                "count": len(scored),
                "buy_candidate": None if not buy_candidate else buy_candidate.get("symbol"),
                "omitted": omitted,
                "audit": str(audit_path),
            }
        )
    )


if __name__ == "__main__":
    main()
