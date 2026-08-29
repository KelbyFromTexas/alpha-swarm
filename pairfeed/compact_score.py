#!/usr/bin/env python3
"""Compact anti-rug score from live-slim; no private keys; stream boards + audit."""
import json
import math
import time
from datetime import datetime, timezone
from pathlib import Path
from gate import write_stream_boards, filter_pairs

IGNORE = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
SLIM = Path("/workspace/pairfeed/live-slim.json")
OUT = Path("/workspace/pairfeed/cycle.json")
AUDIT = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
LAUNCH = Path("/workspace/alpha-swarm-launch")
TALLY = Path("/home/box/agent-data/projects/alpha-swarm/data/tally.jsonl")
WEIGHTS = {
    "holder_dispersion": 0.20,
    "buy_persistence": 0.20,
    "creator_skin": 0.15,
    "tape_quality": 0.15,
    "metadata_legibility": 0.10,
    "cultural_hook": 0.10,
    "lateness": 0.10,
}


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_stamp():
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def mint_short(m):
    m = m or ""
    return m if len(m) <= 12 else f"{m[:6]}…{m[-4:]}"


def age_label(age_min):
    if age_min is None:
        return "?"
    if age_min < 1:
        return f"{int(round(age_min * 60))}s"
    return f"{age_min:.1f}m"


def geo_surv(components):
    used = {k: v for k, v in components.items() if v is not None and k in WEIGHTS}
    if not used:
        return None
    wsum = sum(WEIGHTS[k] for k in used)
    prod = 1.0
    for k, v in used.items():
        prod *= (max(0.01, min(10.0, float(v))) / 10.0) ** (WEIGHTS[k] / wsum)
    return round(10.0 * prod, 2)


def main():
    slim = json.loads(SLIM.read_text())
    kept, omitted = filter_pairs(slim.get("new_pairs") or [])
    kept = [p for p in kept if p.get("mint") != IGNORE]
    now = time.time()
    scored = []
    for p in kept:
        age_min = p.get("age_minutes")
        if age_min is None:
            cu = p.get("created_unix")
            if cu:
                age_min = round((now - float(cu)) / 60.0, 2)
            else:
                age_min = 1.5
        name = p.get("name") or ""
        sym = p.get("symbol") or ""
        meta = 7.0 if len(name) >= 3 and len(sym) >= 2 else 4.0
        hook = 6.0 if len(sym) <= 10 else 4.0
        late = 8.0 if 2 <= age_min <= 20 else (5.0 if age_min < 2 else 3.0)
        comps = {
            "holder_dispersion": None,
            "buy_persistence": None,
            "creator_skin": None,
            "tape_quality": None,
            "metadata_legibility": meta,
            "cultural_hook": hook,
            "lateness": late,
        }
        surv = geo_surv(comps)
        notes = []
        if surv is not None and surv >= 9.5:
            surv = min(surv, 6.0)
            notes.append("surv_capped_not_fully_tape_backed")
        rug = False
        hard = []
        if surv is not None and surv >= 6.5 and not rug and 2 <= age_min <= 45:
            rec = "watch"
            notes.append("tape_missing_prefer_watch")
        elif rug or (surv is not None and surv < 5.0):
            rec = "kill"
        else:
            rec = "watch"
        scored.append(
            {
                "mint": p.get("mint"),
                "name": name,
                "symbol": sym,
                "creator": p.get("creator"),
                "pump_url": p.get("pump_url") or f"https://pump.fun/coin/{p.get('mint')}",
                "age_minutes": age_min,
                "survivability": surv,
                "rug_flag": rug,
                "hard_fails": hard,
                "components": comps,
                "recommend": rec,
                "notes": notes,
            }
        )

    buy_candidate = None
    eligible = [
        x
        for x in scored
        if (not x["rug_flag"])
        and x.get("survivability") is not None
        and x["survivability"] >= 6.5
        and 2 <= (x.get("age_minutes") or 0) <= 45
        and x.get("recommend") == "advance"
        and all(
            (x.get("components") or {}).get(k) is not None
            for k in ("buy_persistence", "tape_quality", "creator_skin")
        )
    ]
    if eligible:
        eligible.sort(key=lambda x: (-(x["survivability"] or 0), x.get("age_minutes") or 99))
        e0 = eligible[0]
        buy_candidate = {
            k: e0[k]
            for k in (
                "mint",
                "symbol",
                "name",
                "survivability",
                "age_minutes",
                "pump_url",
                "recommend",
                "hard_fails",
                "rug_flag",
            )
        }

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
            f"{(p.get('symbol') or '?').replace('|', '/')} | {mint_short(p.get('mint'))} | "
            f"{(p.get('name') or '?').replace('|', '/')} | {age_label(p.get('age_minutes'))} | "
            f"{surv_s} | {p.get('recommend') or '-'}"
        )
    if buy_candidate:
        lines += [
            "",
            f"buy_candidate: {buy_candidate['symbol']} {mint_short(buy_candidate['mint'])} surv={buy_candidate['survivability']}",
        ]
    else:
        lines += [
            "",
            "NO BUY this cycle",
            "buy_candidate: none",
            "note: tape/RPC components missing — capped surv, recommend=watch",
        ]
    write_stream_boards("\n".join(lines) + "\n", scored_prefix=prefix)

    buys = 0
    sol = 0.0
    if TALLY.exists():
        for line in TALLY.read_text().splitlines():
            try:
                row = json.loads(line)
            except Exception:
                continue
            if row.get("action") == "buy":
                buys += 1
                sol += float(row.get("sol") or 0.01)
    (LAUNCH / "TALLY_BOARD.txt").write_text(
        "\n".join(
            [
                "TALLY — micro trenches (0.01 SOL)",
                f"asof: {asof}",
                f"buys: {buys}",
                f"sol_spent: {sol:.2f}",
                "",
                f"last_cycle: {len(scored)} pairs scored — NO BUY (tape missing / no advance)",
                "rule: every 3m; buy 0.01 only if anti-rug pass + tape-backed comps (not bare surv=10)",
                "",
                "(no fills yet)" if buys == 0 else f"fills: {buys}",
                "Kill rate is the product.",
                "",
            ]
        )
    )

    blockers = [
        "source: PumpPortal subscribeNewToken top-up + compact score (no RPC tape this cycle)",
        "tape components unset → survivability capped; recommend forced to watch (no micro-buy)",
        "hard-gate/slur/impersonation omitted from board (counts only)",
    ]
    if omitted:
        blockers.append("omitted_counts:" + json.dumps(omitted, separators=(",", ":")))
    feed = {
        "feed_id": f"pf-cycle-{stamp}",
        "asof": asof,
        "new_pairs": scored,
        "buy_candidate": buy_candidate,
        "blockers": blockers,
    }
    OUT.write_text(json.dumps(feed, indent=2) + "\n")
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / f"pair-scan-{stamp}.json").write_text(
        json.dumps(
            {
                "feed_id": feed["feed_id"],
                "asof": asof,
                "pairs_raw": len(slim.get("new_pairs") or []),
                "pairs_board": len(scored),
                "pairs_scored": len(scored),
                "omitted": omitted,
                "kill_switch_off": not Path(
                    "/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on"
                ).exists(),
                "mints": [
                    {
                        "mint": p["mint"],
                        "symbol": p.get("symbol"),
                        "survivability": p["survivability"],
                        "rug_flag": p["rug_flag"],
                        "age_minutes": p.get("age_minutes"),
                        "hard_fails": p.get("hard_fails") or [],
                        "recommend": p.get("recommend"),
                    }
                    for p in scored
                ],
                "buy_candidate": buy_candidate,
                "blockers": blockers,
            },
            indent=2,
        )
        + "\n"
    )
    with TALLY.open("a") as f:
        f.write(
            json.dumps(
                {
                    "ts": asof,
                    "action": "no_buy",
                    "pairs_scored": len(scored),
                    "buy_candidate": None,
                    "gate": "tape_missing_watch_only",
                    "omitted": omitted,
                }
            )
            + "\n"
        )
    Path("/workspace/alpha-swarm-launch/pair_feed_sample.json").write_text(
        json.dumps(
            {
                "asof": asof,
                "feed_id": feed["feed_id"],
                "count": len(scored),
                "pairs_raw": len(slim.get("new_pairs") or []),
                "pairs_board": len(scored),
                "pairs_scored": len(scored),
                "omitted": omitted,
                "source": "pumpportal topup + compact score (tape missing)",
                "skip_mint": IGNORE,
                "buy_candidate": buy_candidate,
                "tokens": [
                    {
                        "symbol": p.get("symbol"),
                        "name": p.get("name"),
                        "mint": p.get("mint"),
                        "survivability": p.get("survivability"),
                        "rug_flag": p.get("rug_flag"),
                        "age_minutes": p.get("age_minutes"),
                        "recommend": p.get("recommend"),
                    }
                    for p in scored
                ],
            },
            indent=2,
        )
        + "\n"
    )
    print(
        json.dumps(
            {
                "asof": asof,
                "scored": len(scored),
                "omitted": omitted,
                "buy": None if not buy_candidate else buy_candidate["symbol"],
                "adv": sum(1 for p in scored if p["recommend"] == "advance"),
                "watch": sum(1 for p in scored if p["recommend"] == "watch"),
                "kill": sum(1 for p in scored if p["recommend"] == "kill"),
                "audit": f"pair-scan-{stamp}.json",
            }
        )
    )


if __name__ == "__main__":
    main()
