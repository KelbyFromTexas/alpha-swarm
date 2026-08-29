import json
from datetime import datetime, timezone
from pathlib import Path
from gate import filter_pairs, write_stream_boards

IGNORE = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
src = Path("/home/box/agent-data/projects/alpha-swarm/data/audit/pair-scan-20260829T131823Z.json")
data = json.loads(src.read_text())
asof = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
rows, _ = filter_pairs([p for p in (data.get("new_pairs") or []) if p.get("mint") != IGNORE])

def mint_short(m):
    m = m or ""
    if len(m) <= 12:
        return m
    return f"{m[:6]}…{m[-4:]}"

def age_s(p):
    a = p.get("age_minutes")
    if a is None:
        return "?"
    if a < 1:
        return f"{int(round(a*60))}s"
    return f"{a:.1f}m"

lines = [
    "PAIR FEED — live",
    f"asof: {asof}",
    f"count: {len(rows)}",
    "",
    "SYMBOL | MINT_SHORT | NAME | age",
    "------ | ---------- | ---- | ---",
]
for p in rows:
    sym = (p.get("symbol") or "?").replace("|", "/")
    name = (p.get("name") or "?").replace("|", "/")
    lines.append(f"{sym} | {mint_short(p.get('mint') or '')} | {name} | {age_s(p)}")
write_stream_boards("\n".join(lines) + "\n")
slim = {
    "feed_id": "pf-live-20260829T131823Z",
    "asof": asof,
    "new_pairs": [
        {
            "mint": p.get("mint"),
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "creator": p.get("creator"),
            "pump_url": p.get("pump_url") or ("https://pump.fun/coin/" + (p.get("mint") or "")),
        }
        for p in rows
    ],
    "blockers": [
        "sample window 31.1s yielded 15 creates (below 20-40; topping up)",
        "source: PumpPortal subscribeNewToken (auth WS)",
    ],
}
Path("/workspace/pairfeed/live-slim.json").write_text(json.dumps(slim, indent=2))
print("wrote", board_path, "bytes", board_path.stat().st_size, "pairs", len(rows))
