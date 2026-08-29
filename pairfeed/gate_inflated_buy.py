#!/usr/bin/env python3
"""Clear placeholder-inflated buy_candidate; refresh boards. Never print keys."""
import json
from datetime import datetime, timezone
from pathlib import Path
from gate import filter_pairs, write_stream_boards

LAUNCH = Path("/workspace/alpha-swarm-launch")
AUDIT = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
TALLY = Path("/home/box/agent-data/projects/alpha-swarm/data/tally.jsonl")
CYCLE = Path("/workspace/pairfeed/cycle.json")
SLIM = Path("/workspace/pairfeed/live-slim.json")

now = datetime.now(timezone.utc)
asof = now.strftime("%Y-%m-%dT%H:%M:%SZ")
stamp = now.strftime("%Y%m%dT%H%M%SZ")

d = json.loads(CYCLE.read_text())
pairs, _omit = filter_pairs(d.get("new_pairs") or [])
old_buy = d.get("buy_candidate")

note = (
    "NO BUY this cycle — surv=10.0 cluster looks placeholder-inflated "
    "(tape/creator/buy_persistence unmeasured); need tape-backed components"
)


def inflated(p):
    c = p.get("components") or {}
    tape_backed = [c.get("buy_persistence"), c.get("tape_quality"), c.get("creator_skin")]
    missing = sum(v is None for v in tape_backed)
    surv = p.get("survivability")
    return missing >= 2 and surv is not None and surv >= 9.5


n_inflated = 0
for p in pairs:
    if inflated(p):
        n_inflated += 1
        if p.get("recommend") == "advance":
            p["recommend"] = "watch"
            notes = list(p.get("notes") or [])
            if "placeholder_inflated_no_tape" not in notes:
                notes.append("placeholder_inflated_no_tape")
            p["notes"] = notes

d["buy_candidate"] = None
d["asof"] = asof
blockers = list(d.get("blockers") or [])
gate_note = (
    f"buy_candidate cleared: placeholder-inflated surv (n_inflated={n_inflated}); "
    "require tape-backed buy_persistence/tape_quality/creator_skin before micro-buy"
)
if old_buy:
    gate_note += f"; was {old_buy.get('symbol')} surv={old_buy.get('survivability')}"
if gate_note not in blockers:
    blockers.append(gate_note)
d["blockers"] = blockers
d["feed_id"] = f"pf-cycle-{stamp}"
CYCLE.write_text(json.dumps(d, indent=2) + "\n")


def mint_short(m):
    m = m or ""
    return m if len(m) <= 12 else f"{m[:6]}…{m[-4:]}"


def age_label(age_min):
    if age_min is None:
        return "?"
    if age_min < 1:
        return f"{int(round(age_min * 60))}s"
    return f"{age_min:.1f}m"


lines = [
    "PAIR FEED — live",
    f"asof: {asof}",
    f"count: {len(pairs)}",
    "",
    "SYMBOL | MINT_SHORT | NAME | age | surv | rec",
    "------ | ---------- | ---- | --- | ---- | ---",
]
for p in pairs[:40]:
    surv = p.get("survivability")
    surv_s = "-" if surv is None else f"{surv:.1f}"
    lines.append(
        f"{(p.get('symbol') or '?').replace('|', '/')} | {mint_short(p.get('mint'))} | "
        f"{(p.get('name') or '?').replace('|', '/')} | {age_label(p.get('age_minutes'))} | "
        f"{surv_s} | {p.get('recommend') or '-'}"
    )
lines += ["", "buy_candidate: none", note]
board_body = "\n".join(lines) + "\n"
write_stream_boards(board_body)

(LAUNCH / "TALLY_BOARD.txt").write_text(
    "\n".join(
        [
            "TALLY — micro trenches (0.01 SOL)",
            f"asof: {asof}",
            "buys: 0",
            "sol_spent: 0.00",
            "",
            f"last_cycle: {len(pairs)} pairs scored — NO BUY (inflated surv gated)",
            "rule: every 3m; buy 0.01 only if anti-rug pass + tape-backed comps (not bare surv=10)",
            "",
            "(no fills yet)",
            "Kill rate is the product.",
            "",
        ]
    )
)

with TALLY.open("a") as f:
    f.write(
        json.dumps(
            {
                "ts": asof,
                "action": "no_buy",
                "pairs_scored": len(pairs),
                "buy_candidate": None,
                "gate": "placeholder_inflated_surv",
                "n_inflated": n_inflated,
                "cleared_candidate": None
                if not old_buy
                else {
                    "symbol": old_buy.get("symbol"),
                    "mint": old_buy.get("mint"),
                    "survivability": old_buy.get("survivability"),
                },
            }
        )
        + "\n"
    )

AUDIT.mkdir(parents=True, exist_ok=True)
(AUDIT / f"pair-scan-{stamp}.json").write_text(
    json.dumps(
        {
            "feed_id": d["feed_id"],
            "asof": asof,
            "mints": [
                {
                    "mint": p["mint"],
                    "survivability": p.get("survivability"),
                    "rug_flag": p.get("rug_flag"),
                    "recommend": p.get("recommend"),
                }
                for p in pairs
            ],
            "buy_candidate": None,
            "gate": "placeholder_inflated_surv",
            "n_inflated": n_inflated,
            "cleared_candidate": old_buy,
            "note": note,
        },
        indent=2,
    )
    + "\n"
)

SLIM.write_text(
    json.dumps(
        {
            "feed_id": d["feed_id"],
            "asof": asof,
            "new_pairs": [
                {
                    "mint": p.get("mint"),
                    "name": p.get("name"),
                    "symbol": p.get("symbol"),
                    "creator": p.get("creator"),
                    "pump_url": p.get("pump_url"),
                }
                for p in pairs
            ],
            "blockers": blockers,
        },
        indent=2,
    )
    + "\n"
)

print(
    json.dumps(
        {
            "asof": asof,
            "pairs": len(pairs),
            "n_inflated": n_inflated,
            "buy_candidate": None,
            "cleared": None if not old_buy else old_buy.get("symbol"),
            "audit": f"pair-scan-{stamp}.json",
        }
    )
)
