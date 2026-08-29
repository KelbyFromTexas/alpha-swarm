#!/usr/bin/env python3
"""Drop hard-gate/slur tickers from board AND json. Never print keys."""
import json
import re
import time
from datetime import datetime, timezone
from pathlib import Path
from gate import write_stream_boards

IGNORE_MINT = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
SLIM = Path("/workspace/pairfeed/live-slim.json")
BOARD = Path("/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt")

# slur/hate (obfuscated fragments)
SLUR_RE = re.compile(
    r"nigg|faggot|kike|tranny|retard|coon\b|spic\b|wetback|chink|gook|beaner|rapist",
    re.I,
)
TRAGEDY_RE = re.compile(
    r"\b(rape|nazi|hitler|holocaust|9/?11|school.?shoot|mass.?shoot|isis| pedo|cp\b)",
    re.I,
)
IMPERSONATION = {
    "TESLA", "APPLE", "GOOGLE", "MICROSOFT", "OPENAI", "NVIDIA", "BITCOIN", "ETHEREUM",
    "TRUMP", "BIDEN", "ELON", "MUSK", "ELONMON", "MICKEY", "DISNEY", "NIKE", "COKE",
    "PEPSI", "FERRARI", "LAMBO", "ROLEX", "NBA", "NFL", "FIFA", "SPONGEBOB", "Pikachu".upper(),
    "MARIO", "SONIC", "BATMAN", "POKEMON", "POKÉMON",
}


def gate_reason(p) -> str | None:
    mint = p.get("mint") or ""
    if mint == IGNORE_MINT:
        return "house_swan"
    blob = f"{p.get('name') or ''} {p.get('symbol') or ''}"
    if SLUR_RE.search(blob):
        return "slur_hate"
    if TRAGEDY_RE.search(blob):
        return "tragedy_crime"
    toks = set(
        blob.upper().replace("$", " ").replace("-", " ").replace("_", " ").split()
    )
    if toks & IMPERSONATION:
        return "impersonation_brand"
    # concatenated impersonation e.g. Elonmon
    up = blob.upper().replace(" ", "")
    for t in IMPERSONATION:
        if len(t) >= 4 and t in up:
            return "impersonation_brand"
    return None


def mint_short(m):
    m = m or ""
    return m if len(m) <= 12 else f"{m[:6]}…{m[-4:]}"


def age_s(p, now=None):
    now = now or time.time()
    if p.get("created_unix"):
        age_min = (now - float(p["created_unix"])) / 60.0
    else:
        age_min = p.get("age_minutes")
    if age_min is None:
        return "?"
    if age_min < 1:
        return f"{int(round(age_min * 60))}s"
    return f"{age_min:.1f}m"


def sanitize(pairs):
    kept, omitted = [], {}
    seen = set()
    for p in pairs:
        mint = p.get("mint")
        if not mint or mint in seen:
            continue
        seen.add(mint)
        reason = gate_reason(p)
        if reason:
            omitted[reason] = omitted.get(reason, 0) + 1
            continue
        kept.append(p)
    return kept, omitted


def write_board(pairs, asof):
    lines = [
        "PAIR FEED — live",
        f"asof: {asof}",
        f"count: {len(pairs)}",
        "",
        "SYMBOL | MINT_SHORT | NAME | age",
        "------ | ---------- | ---- | ---",
    ]
    now = time.time()
    for p in pairs:
        sym = (p.get("symbol") or "?").replace("|", "/")
        name = (p.get("name") or "?").replace("|", "/")
        lines.append(f"{sym} | {mint_short(p.get('mint') or '')} | {name} | {age_s(p, now)}")
    write_stream_boards("\n".join(lines) + "\n")


def main():
    data = json.loads(SLIM.read_text()) if SLIM.exists() else {"new_pairs": []}
    kept, omitted = sanitize(data.get("new_pairs") or [])
    asof = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    write_board(kept, asof)
    omitted_n = sum(omitted.values())
    blockers = [
        "source: PumpPortal subscribeNewToken",
        "hard-gate/slur/impersonation omitted from board and JSON (counts only)",
    ]
    if omitted:
        blockers.append("omitted_counts:" + json.dumps(omitted, separators=(",", ":")))
    if len(kept) < 20:
        blockers.append(f"count {len(kept)} below 20-40 target")
    out = {
        "feed_id": f"pf-live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "asof": asof,
        "new_pairs": [
            {
                "mint": p.get("mint"),
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "creator": p.get("creator"),
                "pump_url": p.get("pump_url") or f"https://pump.fun/coin/{p.get('mint')}",
            }
            for p in kept
        ],
        "blockers": blockers,
    }
    SLIM.write_text(json.dumps(out, indent=2))
    print(json.dumps({"kept": len(kept), "omitted": omitted, "omitted_n": omitted_n}))


if __name__ == "__main__":
    main()
