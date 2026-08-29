#!/usr/bin/env python3
import json, re, time
from datetime import datetime, timezone
from pathlib import Path
from gate import filter_pairs, write_stream_boards, blocked_reason
from urllib.parse import quote

IGNORE = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
SLUR_RE = re.compile(r"nigg", re.I)
ENV_PATH = Path("/home/box/agent-data/projects/alpha-swarm/.env")
SLIM = Path("/workspace/pairfeed/live-slim.json")
BOARD = Path("/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt")
MAX_SEC = 55
MAX_PAIRS = 40

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

def mint_of(d):
    v = d.get("mint") or d.get("tokenMint")
    return v if isinstance(v, str) and len(v) >= 32 else ""

def tx_type(d):
    return str(d.get("txType") or d.get("tx_type") or d.get("type") or "").lower()

def mint_short(m):
    m = m or ""
    return m if len(m) <= 12 else f"{m[:6]}…{m[-4:]}"

def write_board(pairs, asof, redacted):
    rows = []
    for p in pairs:
        blob = f"{p.get('name') or ''} {p.get('symbol') or ''}"
        if SLUR_RE.search(blob):
            continue
        rows.append(p)
    lines = [
        "PAIR FEED — live",
        f"asof: {asof}",
        f"count: {len(rows)}",
        "",
        "SYMBOL | MINT_SHORT | NAME | age",
        "------ | ---------- | ---- | ---",
    ]
    now = time.time()
    for p in rows:
        created = p.get("created_unix") or now
        age_min = (now - created) / 60.0
        if age_min < 1:
            age = f"{int(round(age_min*60))}s"
        else:
            age = f"{age_min:.1f}m"
        sym = (p.get("symbol") or "?").replace("|", "/")
        name = (p.get("name") or "?").replace("|", "/")
        lines.append(f"{sym} | {mint_short(p.get('mint') or '')} | {name} | {age}")
    write_stream_boards("\n".join(lines) + "\n")

def main():
    import websocket
    env = load_env(ENV_PATH)
    key = env.get("PUMPPORTAL_API_KEY") or ""
    existing = json.loads(SLIM.read_text()) if SLIM.exists() else {"new_pairs": []}
    pairs = []
    seen = set()
    created_unix = {}
    t_now = time.time()
    for p in existing.get("new_pairs") or []:
        mint = p.get("mint")
        if not mint or mint == IGNORE or mint in seen:
            continue
        seen.add(mint)
        p = dict(p)
        p["created_unix"] = t_now - 180  # ~3m old carryover
        pairs.append(p)
    errors = []
    url = f"wss://pumpportal.fun/api/data?api-key={quote(key, safe='')}" if key else "wss://pumpportal.fun/api/data"
    ws = websocket.create_connection(url, timeout=12)
    ws.settimeout(1.0)
    ws.send(json.dumps({"method": "subscribeNewToken"}))
    deadline = time.time() + MAX_SEC
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
            if mint == IGNORE or not mint or mint in seen:
                continue
            if tx in ("buy", "sell", "migration", "migrate"):
                continue
            is_create = tx in ("create", "newtoken", "new_token") or (item.get("name") and item.get("symbol"))
            if not is_create:
                continue
            seen.add(mint)
            rec = {
                "mint": mint,
                "name": item.get("name"),
                "symbol": item.get("symbol"),
                "creator": item.get("creator") or item.get("traderPublicKey"),
                "pump_url": f"https://pump.fun/coin/{mint}",
                "created_unix": time.time(),
            }
            pairs.append(rec)
    try:
        ws.close()
    except Exception:
        pass
    asof = now_iso()
    redacted = sum(1 for p in pairs if SLUR_RE.search(f"{p.get('name') or ''} {p.get('symbol') or ''}"))
    write_board(pairs, asof, redacted)
    slim = {
        "feed_id": f"pf-live-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        "asof": asof,
        "new_pairs": [
            {
                "mint": p["mint"],
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "creator": p.get("creator"),
                "pump_url": p.get("pump_url"),
                "created_unix": p.get("created_unix"),
            }
            for p in pairs[:MAX_PAIRS]
        ],
        "blockers": [
            f"board {BOARD} count_on_board={len(pairs)-redacted} json_pairs={len(pairs)}",
            f"{redacted} slur/hate ticker(s) omitted from livestream board; still in JSON" if redacted else "board includes all json pairs",
            "source: PumpPortal subscribeNewToken auth WS + prior sample merge",
        ] + (["ws_errors:" + ",".join(errors)] if errors else []),
    }
    SLIM.write_text(json.dumps(slim, indent=2))
    print(json.dumps({"pairs": len(pairs), "board": len(pairs)-redacted, "redacted": redacted, "errors": errors}))

if __name__ == "__main__":
    main()
