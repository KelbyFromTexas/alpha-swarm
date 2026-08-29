#!/usr/bin/env python3
"""CYCLE NOW: sanitize, anti-rug score, board, buy_candidate. Never print keys."""
import json
import math
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from gate import write_stream_boards, filter_pairs

IGNORE_MINT = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"
ENV_PATH = Path("/workspace/pairfeed/.env.score")
SLIM = Path("/workspace/pairfeed/live-slim.json")
_AUDIT = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")
_scans = sorted(_AUDIT.glob("pair-scan-*.json"), key=lambda x: x.stat().st_mtime, reverse=True) if _AUDIT.exists() else []
SCAN = _scans[0] if _scans else Path("/dev/null")
BOARD = Path("/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt")
OUT = Path("/workspace/pairfeed/cycle.json")
AUDIT = Path("/home/box/agent-data/projects/alpha-swarm/data/audit")

SLUR_RE = re.compile(
    r"nigg|faggot|kike|tranny|retard|coon\b|spic\b|wetback|chink|gook|beaner|rapist",
    re.I,
)
TRAGEDY_RE = re.compile(
    r"\b(rape|nazi|hitler|holocaust|9/?11|school.?shoot|mass.?shoot|isis|pedo|\bcp\b)",
    re.I,
)
PRIVATE_RE = re.compile(r"justice for\s+[A-Z]", re.I)
IMPERSONATION = {
    "TESLA", "APPLE", "GOOGLE", "MICROSOFT", "OPENAI", "NVIDIA", "BITCOIN", "ETHEREUM",
    "TRUMP", "BIDEN", "ELON", "MUSK", "ELONMON", "MICKEY", "DISNEY", "NIKE", "COKE",
    "PEPSI", "FERRARI", "LAMBO", "ROLEX", "NBA", "NFL", "FIFA", "SPONGEBOB", "PIKACHU",
    "MARIO", "SONIC", "BATMAN", "POKEMON", "RONALDO", "MESSI",
}
WEIGHTS = {
    "holder_dispersion": 0.20,
    "buy_persistence": 0.20,
    "creator_skin": 0.15,
    "tape_quality": 0.15,
    "metadata_legibility": 0.10,
    "cultural_hook": 0.10,
    "lateness": 0.10,
}


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


def gate_reason(p):
    mint = p.get("mint") or ""
    if mint == IGNORE_MINT:
        return "house_swan"
    blob = f"{p.get('name') or ''} {p.get('symbol') or ''}"
    if SLUR_RE.search(blob):
        return "slur_hate"
    if TRAGEDY_RE.search(blob):
        return "tragedy_crime"
    if PRIVATE_RE.search(blob):
        return "private_individual"
    toks = set(blob.upper().replace("$", " ").replace("-", " ").replace("_", " ").split())
    if toks & IMPERSONATION:
        return "impersonation_brand"
    up = blob.upper().replace(" ", "")
    for t in IMPERSONATION:
        if len(t) >= 4 and t in up:
            return "impersonation_brand"
    return None


def metadata_legibility(name, symbol):
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
    return max(1.0, min(10.0, score))


def lateness_score(age_min):
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


def geo_surv(components):
    used = {k: v for k, v in components.items() if v is not None and k in WEIGHTS}
    if not used:
        return None
    wsum = sum(WEIGHTS[k] for k in used)
    prod = 1.0
    for k, c in used.items():
        c = max(0.05, min(10.0, float(c)))
        prod *= (c / 10.0) ** (WEIGHTS[k] / wsum)
    return round(10.0 * prod, 2)


def rpc_largest(rpc, mint):
    body = json.dumps({
        "jsonrpc": "2.0", "id": 1,
        "method": "getTokenLargestAccounts",
        "params": [mint],
    }).encode()
    req = urllib.request.Request(rpc, data=body, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=6) as resp:
            data = json.loads(resp.read().decode())
        val = (data.get("result") or {}).get("value") if isinstance(data.get("result"), dict) else data.get("result")
        return mint, val or []
    except Exception:
        return mint, []


def top_pct_from_largest(largest):
    rows = []
    total = 0.0
    for acc in largest or []:
        amt = acc.get("uiAmount")
        if amt is None:
            continue
        amt = float(amt)
        total += amt
        rows.append(amt)
    if total <= 0 or not rows:
        return None
    rows.sort(reverse=True)
    rest = rows[1:] if len(rows) > 1 else []
    if not rest:
        return 0.0
    return rest[0] / total


def score_one(p, largest, age_min, init_buy):
    hard_fails = []
    notes = []
    top_pct = top_pct_from_largest(largest)
    if top_pct is not None and top_pct > 0.35:
        hard_fails.append("top_wallet_gt_35pct")
    holder_disp = None
    if top_pct is not None:
        holder_disp = max(1.0, min(10.0, (1.0 - top_pct) * 12.0))
    components = {
        "holder_dispersion": holder_disp,
        "buy_persistence": None,
        "creator_skin": creator_skin_score(init_buy),
        "tape_quality": None,
        "metadata_legibility": metadata_legibility(p.get("name"), p.get("symbol")),
        "cultural_hook": None,
        "lateness": lateness_score(age_min),
    }
    missing = [k for k, v in components.items() if v is None]
    if missing:
        notes.append("unmeasured:" + ",".join(missing))
    surv = geo_surv(components)
    tape_keys = ("buy_persistence", "tape_quality", "creator_skin")
    all_listed = all(components.get(k) is not None for k in WEIGHTS)
    tape_backed = all(components.get(k) is not None for k in tape_keys)
    if surv is not None and surv >= 10.0 and not (all_listed and tape_backed):
        surv = 9.4
        notes.append("surv_capped_not_fully_tape_backed")
    rug_flag = bool(hard_fails)
    rec = "kill"
    if not rug_flag and surv is not None and surv >= 6.5 and age_min is not None and 2 <= age_min <= 45:
        rec = "advance"
    elif not rug_flag and surv is not None and surv >= 6.5:
        rec = "watch"
        notes.append("age_outside_2_45m")
    return {
        "rug_flag": rug_flag,
        "hard_fails": hard_fails,
        "components": {k: (None if v is None else round(float(v), 2)) for k, v in components.items()},
        "survivability": surv,
        "recommend": rec,
        "notes": notes,
        "top_holder_pct": None if top_pct is None else round(top_pct, 4),
    }


def mint_short(m):
    m = m or ""
    return m if len(m) <= 12 else f"{m[:6]}…{m[-4:]}"


def age_label(age_min):
    if age_min is None:
        return "?"
    if age_min < 1:
        return f"{int(round(age_min * 60))}s"
    return f"{age_min:.1f}m"


def parse_created_unix(p, extra):
    if p.get("created_unix"):
        try:
            return float(p["created_unix"])
        except Exception:
            pass
    mint = p.get("mint")
    if extra.get(mint) and extra[mint].get("created_at"):
        try:
            ts = extra[mint]["created_at"]
            dt = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
            return dt.timestamp()
        except Exception:
            pass
    if extra.get(mint) and extra[mint].get("created_unix"):
        try:
            return float(extra[mint]["created_unix"])
        except Exception:
            pass
    return None


def main():
    env = load_env(ENV_PATH)
    rpc = env.get("SOLANA_RPC_URL") or ""
    slim = json.loads(SLIM.read_text()) if SLIM.exists() else {"new_pairs": []}
    extra = {}
    if SCAN.exists():
        scan = json.loads(SCAN.read_text())
        for p in scan.get("new_pairs") or []:
            extra[p.get("mint")] = p

    omitted = {}
    kept = []
    seen = set()
    for p in slim.get("new_pairs") or []:
        mint = p.get("mint")
        if not mint or mint in seen:
            continue
        seen.add(mint)
        reason = gate_reason(p)
        if reason:
            omitted[reason] = omitted.get(reason, 0) + 1
            continue
        kept.append(dict(p))

    # write a clean board immediately so the stream drops slurs while scoring
    asof_pre = now_iso()
    write_stream_boards(
        "\n".join([
            "PAIR FEED — live",
            f"asof: {asof_pre}",
            f"count: {len(kept)}",
            "",
            "SYMBOL | MINT_SHORT | NAME | age | surv | rec",
            "------ | ---------- | ---- | --- | ---- | ---",
        ] + [
            f"{(p.get('symbol') or '?').replace('|','/')} | {mint_short(p.get('mint'))} | {(p.get('name') or '?').replace('|','/')} | ? | … | …"
            for p in kept[:40]
        ]) + "\n"
    )

    largest_map = {}
    if rpc and kept:
        with ThreadPoolExecutor(max_workers=8) as ex:
            futs = [ex.submit(rpc_largest, rpc, p["mint"]) for p in kept]
            for fut in as_completed(futs):
                mint, val = fut.result()
                largest_map[mint] = val

    now = time.time()
    scored = []
    for p in kept:
        mint = p["mint"]
        created_unix = parse_created_unix(p, extra)
        if created_unix is None:
            # top-up batch ended 13:22:15Z; treat unknown as ~2m if carryover-looking else 1m
            created_unix = now - 90
        age_min = round((now - created_unix) / 60.0, 2)
        init = None
        if extra.get(mint):
            init = extra[mint].get("initial_buy_sol")
            if extra[mint].get("age_minutes") is not None and extra[mint].get("created_at"):
                pass
        s = score_one(p, largest_map.get(mint) or [], age_min, init)
        scored.append({
            "mint": mint,
            "name": p.get("name"),
            "symbol": p.get("symbol"),
            "creator": p.get("creator"),
            "pump_url": p.get("pump_url") or f"https://pump.fun/coin/{mint}",
            "age_minutes": age_min,
            "initial_buy_sol": init,
            **s,
        })

    buy_candidate = None
    kill_on = Path("/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on").exists()
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
        buy_candidate = {
            "mint": eligible[0]["mint"],
            "symbol": eligible[0]["symbol"],
            "name": eligible[0]["name"],
            "survivability": eligible[0]["survivability"],
            "age_minutes": eligible[0]["age_minutes"],
            "pump_url": eligible[0]["pump_url"],
            "recommend": eligible[0]["recommend"],
            "hard_fails": eligible[0].get("hard_fails") or [],
            "rug_flag": eligible[0].get("rug_flag", False),
        }

    asof = now_iso()
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
        rec = p.get("recommend") or "-"
        lines.append(
            f"{(p.get('symbol') or '?').replace('|','/')} | {mint_short(p.get('mint'))} | {(p.get('name') or '?').replace('|','/')} | {age_label(p.get('age_minutes'))} | {surv_s} | {rec}"
        )
    if buy_candidate:
        lines += ["", f"buy_candidate: {buy_candidate['symbol']} {mint_short(buy_candidate['mint'])} surv={buy_candidate['survivability']}"]
    else:
        lines += ["", "NO BUY this cycle", "buy_candidate: none"]
    write_stream_boards("\n".join(lines) + "\n")

    blockers = [
        "source: PumpPortal subscribeNewToken (top-up sample + hard-gate filter + anti-rug score)",
        "hard-gate/slur/impersonation omitted from board and JSON (counts only)",
    ]
    if kill_on:
        blockers.append("kill-switch.on present — buy recommend suppressed")
    if omitted:
        blockers.append("omitted_counts:" + json.dumps(omitted, separators=(",", ":")))
    if not buy_candidate:
        blockers.append("no buy_candidate: none passed rug_flag=false AND survivability>=6.5 AND age 2-45m")

    feed = {
        "feed_id": f"pf-cycle-{now_stamp()}",
        "asof": asof,
        "new_pairs": scored,
        "buy_candidate": buy_candidate,
        "blockers": blockers,
    }
    OUT.write_text(json.dumps(feed, indent=2))
    AUDIT.mkdir(parents=True, exist_ok=True)
    (AUDIT / f"pair-scan-{now_stamp()}.json").write_text(json.dumps({
        "feed_id": feed["feed_id"],
        "asof": asof,
        "pairs_raw": len(slim.get("new_pairs") or []),
        "pairs_board": len(scored),
        "pairs_scored": len(scored),
        "omitted": omitted,
        "kill_switch_off": not kill_on,
        "mints": [{"mint": p["mint"], "symbol": p.get("symbol"), "survivability": p["survivability"], "rug_flag": p["rug_flag"], "age_minutes": p.get("age_minutes"), "hard_fails": p.get("hard_fails") or [], "recommend": p.get("recommend")} for p in scored],
        "buy_candidate": buy_candidate,
        "blockers": blockers,
    }, indent=2))
    SLIM.write_text(json.dumps({
        "feed_id": feed["feed_id"],
        "asof": asof,
        "new_pairs": [{"mint": p["mint"], "name": p["name"], "symbol": p["symbol"], "creator": p["creator"], "pump_url": p["pump_url"]} for p in scored],
        "blockers": blockers,
    }, indent=2))
    print(json.dumps({
        "scored": len(scored),
        "omitted": omitted,
        "buy": None if not buy_candidate else buy_candidate["symbol"],
        "adv": sum(1 for p in scored if p["recommend"] == "advance"),
        "watch": sum(1 for p in scored if p["recommend"] == "watch"),
        "kill": sum(1 for p in scored if p["recommend"] == "kill"),
        "out": str(OUT),
    }))


if __name__ == "__main__":
    main()
