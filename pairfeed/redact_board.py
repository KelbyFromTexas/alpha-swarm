import json, re
from datetime import datetime, timezone
from pathlib import Path

SLUR_RE = re.compile(r"nigg", re.I)
IGNORE = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
slim_path = Path("/workspace/pairfeed/live-slim.json")
data = json.loads(slim_path.read_text())
# ages from scan
scan = json.loads(Path("/home/box/agent-data/projects/alpha-swarm/data/audit/pair-scan-20260829T131823Z.json").read_text())
age = {p["mint"]: p.get("age_minutes") for p in scan.get("new_pairs") or []}
asof = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
data["asof"] = asof
redacted = 0
board_rows = []
for p in data.get("new_pairs") or []:
    mint = p.get("mint") or ""
    if mint == IGNORE:
        continue
    blob = f"{p.get('name') or ''} {p.get('symbol') or ''}"
    if SLUR_RE.search(blob):
        redacted += 1
        continue
    board_rows.append(p)

def mint_short(m):
    m = m or ""
    return m if len(m) <= 12 else f"{m[:6]}…{m[-4:]}"

def age_s(p):
    a = age.get(p.get("mint"))
    if a is None:
        return "?"
    if a < 1:
        return f"{int(round(a*60))}s"
    return f"{a:.1f}m"

lines = [
    "PAIR FEED — live",
    f"asof: {asof}",
    f"count: {len(board_rows)}",
    "",
    "SYMBOL | MINT_SHORT | NAME | age",
    "------ | ---------- | ---- | ---",
]
for p in board_rows:
    sym = (p.get("symbol") or "?").replace("|", "/")
    name = (p.get("name") or "?").replace("|", "/")
    lines.append(f"{sym} | {mint_short(p.get('mint') or '')} | {name} | {age_s(p)}")
Path("/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt").write_text("\n".join(lines) + "\n")
blockers = data.get("blockers") or []
note = f"{redacted} slur/hate ticker(s) omitted from livestream board; still in JSON"
if note not in blockers:
    blockers.append(note)
data["blockers"] = blockers
slim_path.write_text(json.dumps(data, indent=2))
print("board_rows", len(board_rows), "redacted", redacted)
