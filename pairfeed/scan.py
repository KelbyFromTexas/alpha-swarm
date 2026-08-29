#!/usr/bin/env python3
"""PumpPortal sample + anti-rug score. Never print API keys or private keys."""
import json
import math
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

IGNORE_MINT = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
ENV_PATH = Path("/home/box/agent-data/projects/alpha-swarm/.env")
OUT_DIR = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
DEBUG_PATH = Path("/workspace/pairfeed/last-raw-meta.json")
MAX_SEC = 70
MAX_PAIRS = 15
WEIGHTS = {
    "holder_dispersion": 0.20,
    "buy_persistence": 0.20,
    "creator_skin": 0.15,
    "tape_quality": 0.15,
    "metadata_legibility": 0.10,
    "cultural_hook": 0.10,
    "lateness": 0.10,
}
# obvious impersonation bait only; Pair Feed does not culture-score
IMPERSONATION_TOKENS = {
    "TESLA", "APPLE", "GOOGLE", "MICROSOFT", "OPENAI", "NVIDIA", "BITCOIN", "ETHEREUM",
    "TRUMP", "BIDEN", "ELON", "MUSK", "MICKEY", "DISNEY", "NIKE", "COKE", "PEPSI",
    "FERRARI", "LAMBO", "ROLEEX", "ROLEX", "NBA", "NFL", "FIFA",
}


def load_env(path: Path) -> dict:
    d = {}
    if not path.exists():
        return d
    for line in path.read_text().splitlines():
        s = line.strip()
        if not s or s.startswith("#") or "=" not in s:
            continue
        k, v = s.split("=", 1)
        d[k.strip()] = v.strip().strip('"').strip("'")
    return d


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def rpc_post(url: str, method: str, params):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            return json.loads(resp.read().decode())
    except Exception as e:
        return {"error": type(e).__name__}


def extract_items(payload):
    if payload is None:
        return []
    if isinstance(payload, list):
        return [x for x in payload if isinstance(x, dict)]
    if isinstance(payload, dict):
        for k in ("result", "data", "tokens", "token"):
            if k in payload and payload[k] is not None and k != "mint":
                inner = extract_items(payload[k])
                if inner:
                    return inner
        return [payload]
    return []


def mint_of(d: dict) -> str:
    for k in ("mint", "tokenMint", "ca"):
        v = d.get(k)
        if isinstance(v, str) and len(v) >= 32:
            return v
    return ""


def tx_type(d: dict) -> str:
    return str(d.get("txType") or d.get("tx_type") or d.get("type") or "").lower()


def metadata_legibility(name, symbol) -> float:
    n = (name or "").strip()
    s = (symbol or "").strip()
    if not n and not s:
        return 1.0
    score = 10.0
    if not n or not s:
        score -= 3
    if len(n) > 32 or len(s) > 12:
        score -= 2
    if len(s) < 2:
        score -= 2
    garbage = sum(1 for ch in (n + s) if ord(ch) > 127 or ch in "█�")
    if garbage:
        score -= 3
    return max(1.0, min(10.0, score))


def lateness_score(age_min, migrated: bool) -> float:
    if migrated:
        return 1.0
    if age_min is None:
        return None
    if 2 <= age_min <= 45:
        return 10.0
    if age_min < 2:
        return 8.5
    if age_min <= 180:
        return 4.0
    return 1.5


def creator_skin_score(initial_buy):
    if initial_buy is None:
        return None
    try:
        x = float(initial_buy)
    except Exception:
        return None
    if x <= 0:
        return 3.0
    if 0.05 <= x <= 2.5:
        return 8.5
    if x < 0.05:
        return 5.0
    if x <= 5:
        return 6.0
    return 4.0


def geo_survivability(components: dict):
    used = {k: v for k, v in components.items() if v is not None and k in WEIGHTS}
    if not used:
        return None
    wsum = sum(WEIGHTS[k] for k in used)
    if wsum <= 0:
        return None
    prod = 1.0
    for k, c in used.items():
        c = max(0.05, min(10.0, float(c)))
        w = WEIGHTS[k] / wsum
        prod *= (c / 10.0) ** w
    return round(10.0 * prod, 2)


def impersonation_fail(name, symbol) -> bool:
    blob = f"{name or ''} {symbol or ''}".upper()
    toks = set(blob.replace("$", " ").replace("-", " ").split())
    return bool(toks & IMPERSONATION_TOKENS)


def score_pair(p, tape_for_mint, largest, age_min):
    hard_fails = []
    notes = []
    creator = p.get("creator")
    name, symbol = p.get("name"), p.get("symbol")
    migrated = bool(p.get("migrated"))

    creator_sell_sol = 0.0
    creator_buy_sol = 0.0
    unique_buyers = set()
    unique_sellers = set()
    buys = sells = 0
    sizes = []
    for t in tape_for_mint:
        side = t.get("side")
        trader = t.get("trader")
        sol = float(t.get("sol") or 0)
        sizes.append(round(sol, 4))
        if side == "buy":
            buys += 1
            if trader:
                unique_buyers.add(trader)
            if trader and creator and trader == creator:
                creator_buy_sol += sol
        elif side == "sell":
            sells += 1
            if trader:
                unique_sellers.add(trader)
            if trader and creator and trader == creator:
                creator_sell_sol += sol

    init = p.get("initial_buy_sol")
    if init is not None and creator_sell_sol > 0 and float(init) > 0:
        if creator_sell_sol >= 0.7 * float(init):
            hard_fails.append("creator_sold_gt_70pct_initial")

    top_pct = None
    curve = p.get("bonding_curve")
    if largest:
        total = 0.0
        rows = []
        for acc in largest:
            amt = acc.get("uiAmount")
            if amt is None:
                continue
            amt = float(amt)
            addr = acc.get("address")
            total += amt
            rows.append((amt, addr))
        if total > 0:
            rows.sort(reverse=True)
            for amt, addr in rows:
                if curve and addr == curve:
                    continue
                top_pct = amt / total
                break
            if top_pct is not None and top_pct > 0.35:
                hard_fails.append("top_wallet_gt_35pct")

    if age_min is not None and age_min >= 2 and buys == 0 and creator_sell_sol > 0:
        hard_fails.append("bot_only_tape_zero_unique_buyers")

    if impersonation_fail(name, symbol):
        hard_fails.append("impersonation_or_brand_identity")

    if migrated:
        hard_fails.append("already_migrated_late")

    # wash: only if enough tape
    if len(tape_for_mint) >= 8 and unique_buyers and unique_sellers:
        overlap = unique_buyers & unique_sellers
        if len(overlap) >= 5 and abs(sum(sizes) / max(len(sizes), 1)) < 0.05:
            hard_fails.append("wash_cycling")

    holder_disp = None
    if top_pct is not None:
        holder_disp = max(1.0, min(10.0, (1.0 - top_pct) * 12.0))

    buy_pers = None
    if tape_for_mint:
        uniq = len(unique_buyers)
        if uniq == 0:
            buy_pers = 2.0
        else:
            buy_pers = max(1.0, min(10.0, 3.0 + math.log1p(uniq) * 2.5 + min(buys, 10) * 0.3))

    tape_q = None
    if tape_for_mint:
        ratio = buys / max(buys + sells, 1)
        tape_q = max(1.0, min(10.0, 4.0 + ratio * 6.0 - (1.0 if sells > buys else 0)))

    components = {
        "holder_dispersion": holder_disp,
        "buy_persistence": buy_pers,
        "creator_skin": creator_skin_score(init),
        "tape_quality": tape_q,
        "metadata_legibility": metadata_legibility(name, symbol),
        "cultural_hook": None,  # Pair Feed does not score culture
        "lateness": lateness_score(age_min, migrated),
    }
    missing = [k for k, v in components.items() if v is None]
    if missing:
        notes.append("unmeasured:" + ",".join(missing))
    surv = geo_survivability(components)
    rug_flag = bool(hard_fails)
    rec = "kill"
    if not rug_flag and surv is not None and surv >= 6.5 and age_min is not None and 2 <= age_min <= 45:
        rec = "advance"
    elif not rug_flag and surv is not None and surv >= 6.5:
        rec = "watch"
        notes.append("age_outside_2_45m_or_unmeasured")
    return {
        "rug_flag": rug_flag,
        "hard_fails": hard_fails,
        "components": {k: (None if v is None else round(float(v), 2)) for k, v in components.items()},
        "survivability": surv,
        "recommend": rec,
        "notes": notes,
        "top_holder_pct": None if top_pct is None else round(top_pct, 4),
        "tape_buys": buys,
        "tape_sells": sells,
        "unique_buyers": len(unique_buyers),
    }


def main():
    import websocket

    env = load_env(ENV_PATH)
    key = env.get("PUMPPORTAL_API_KEY") or ""
    rpc = env.get("SOLANA_RPC_URL") or ""
    blockers = []
    if not key:
        blockers.append("PUMPPORTAL_API_KEY missing/empty")
    if not rpc:
        blockers.append("SOLANA_RPC_URL missing")

    new_pairs = []
    by_mint = {}
    tape = []
    seen = set()
    tx_hist = {}
    raw_meta = []
    migration_count = 0
    swan_ignored = 0
    raw_count = 0
    errors = []
    subscribed_trades = set()
    t0 = time.time()

    def ingest(raw: str, ws):
        nonlocal raw_count, migration_count, swan_ignored
        raw_count += 1
        try:
            payload = json.loads(raw)
        except Exception:
            return
        for d in extract_items(payload):
            mint = mint_of(d)
            tx = tx_type(d)
            tx_hist[tx or "blank"] = tx_hist.get(tx or "blank", 0) + 1
            if len(raw_meta) < 40:
                raw_meta.append({
                    "txType": tx or None,
                    "keys": sorted(list(d.keys()))[:24],
                    "has_name": bool(d.get("name")),
                    "has_symbol": bool(d.get("symbol")),
                    "mint_len": len(mint),
                })
            if mint == IGNORE_MINT:
                swan_ignored += 1
                continue
            if tx in ("migration", "migrate"):
                migration_count += 1
                if mint and mint in by_mint:
                    by_mint[mint]["migrated"] = True
                continue
            if tx in ("buy", "sell"):
                sol = d.get("solAmount") or d.get("sol")
                try:
                    sol = float(sol) if sol is not None else None
                except Exception:
                    sol = None
                mcap = d.get("marketCapSol")
                rec = {
                    "mint": mint,
                    "side": tx,
                    "sol": sol,
                    "mcap_usd": None,
                    "mcap_sol": mcap,
                    "trader": d.get("traderPublicKey") or d.get("trader"),
                    "ts": now_iso(),
                }
                tape.append(rec)
                continue
            if not mint:
                continue
            if mint in seen:
                continue
            is_create = tx in ("create", "newtoken", "new_token", "token_create") or (
                not tx and d.get("name") and d.get("symbol")
            )
            if not is_create:
                continue
            seen.add(mint)
            ib = d.get("initialBuy") or d.get("initial_buy_sol")
            try:
                ib = float(ib) if ib is not None else None
            except Exception:
                ib = None
            rec = {
                "mint": mint,
                "name": d.get("name"),
                "symbol": d.get("symbol"),
                "uri": d.get("uri"),
                "creator": d.get("creator") or d.get("traderPublicKey") or d.get("trader"),
                "created_at": now_iso(),
                "initial_buy_sol": ib,
                "pump_url": f"https://pump.fun/coin/{mint}",
                "bonding_curve": d.get("bondingCurveKey") or d.get("bondingCurve"),
                "market_cap_sol": d.get("marketCapSol"),
                "migrated": False,
                "seen_at_unix": time.time(),
            }
            new_pairs.append(rec)
            by_mint[mint] = rec
            if ws is not None and mint not in subscribed_trades and key:
                try:
                    ws.send(json.dumps({"method": "subscribeTokenTrade", "keys": [mint]}))
                    subscribed_trades.add(mint)
                except Exception as e:
                    errors.append(f"sub_trade:{type(e).__name__}")

    ws = None
    used_auth = False
    connected = False
    urls = []
    if key:
        urls.append(("auth", f"wss://pumpportal.fun/api/data?api-key={quote(key, safe='')}"))
    urls.append(("free", "wss://pumpportal.fun/api/data"))
    for mode, url in urls:
        try:
            ws = websocket.create_connection(url, timeout=12)
            ws.settimeout(1.0)
            ws.send(json.dumps({"method": "subscribeNewToken"}))
            if mode == "auth":
                ws.send(json.dumps({"method": "subscribeMigration"}))
            connected = True
            used_auth = mode == "auth"
            break
        except Exception as e:
            errors.append(f"connect_{mode}:{type(e).__name__}")
            ws = None
    if not connected:
        blockers.append("websocket connect failed")
    elif not used_auth:
        blockers.append("auth WS failed; free subscribeNewToken only")

    deadline = time.time() + MAX_SEC
    while connected and time.time() < deadline and len(new_pairs) < MAX_PAIRS:
        try:
            ingest(ws.recv(), ws)
        except websocket.WebSocketTimeoutException:
            continue
        except Exception as e:
            errors.append(f"recv:{type(e).__name__}")
            break
    if ws is not None:
        try:
            ws.close()
        except Exception:
            pass

    elapsed = round(time.time() - t0, 1)
    asof = now_iso()
    scored = []
    for p in new_pairs:
        age_min = round((time.time() - p["seen_at_unix"]) / 60.0, 2)
        p["age_minutes"] = age_min
        p["age"] = age_min
        largest = None
        if rpc:
            r = rpc_post(rpc, "getTokenLargestAccounts", [p["mint"]])
            if isinstance(r, dict) and "result" in r:
                val = r["result"]
                largest = val.get("value") if isinstance(val, dict) else val
            elif isinstance(r, dict) and r.get("error"):
                errors.append(f"rpc_largest:{r.get('error')}")
        tape_m = [t for t in tape if t.get("mint") == p["mint"]]
        s = score_pair(p, tape_m, largest or [], age_min)
        item = {
            "mint": p["mint"],
            "name": p["name"],
            "symbol": p["symbol"],
            "creator": p["creator"],
            "pump_url": p["pump_url"],
            "created_at": p["created_at"],
            "initial_buy_sol": p["initial_buy_sol"],
            "age_minutes": age_min,
            "age": age_min,
            "uri": p.get("uri"),
            **s,
        }
        scored.append(item)

    if swan_ignored:
        blockers.append(f"ignored {swan_ignored} $SWAN event(s)")
    if migration_count:
        blockers.append(f"{migration_count} migration event(s) (late)")
    if connected and not new_pairs:
        blockers.append(f"no new_pairs in {elapsed}s sample window")
    if errors:
        blockers.append("errors:" + ",".join(errors[:8]))
    blockers.append("tx_hist:" + json.dumps(tx_hist, separators=(",", ":")))

    feed = {
        "feed_id": f"pf-scan-{now_stamp()}",
        "asof": asof,
        "ready": True,
        "sample_seconds": elapsed,
        "raw_messages": raw_count,
        "auth_ws": used_auth,
        "new_pairs": scored,
        "tape": [
            {"mint": t["mint"], "side": t["side"], "sol": t["sol"], "mcap_usd": None, "ts": t["ts"]}
            for t in tape[:80]
        ],
        "matches": [],
        "blockers": blockers,
    }
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUT_DIR / f"pair-scan-{now_stamp()}.json"
    out_path.write_text(json.dumps(feed, indent=2))
    Path("/workspace/pairfeed-sample.json").write_text(json.dumps(feed, indent=2))
    DEBUG_PATH.write_text(json.dumps({"tx_hist": tx_hist, "raw_meta": raw_meta[:20]}, indent=2))
    print(json.dumps({
        "ok": connected,
        "auth_ws": used_auth,
        "pairs": len(scored),
        "raw": raw_count,
        "elapsed": elapsed,
        "migrations": migration_count,
        "tape": len(tape),
        "swan_ignored": swan_ignored,
        "shortlist": sum(1 for x in scored if not x["rug_flag"] and (x["survivability"] or 0) >= 6.5),
        "out": str(out_path),
    }))


if __name__ == "__main__":
    main()
