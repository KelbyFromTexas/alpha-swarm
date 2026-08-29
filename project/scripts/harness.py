#!/usr/bin/env python3
"""ALPHA SWARM local deterministic backtest harness.

Uses ONLY asof_snapshot at decision_at. Fixture scores are not live Grok calls.
Import composite() from composite.py — do not reimplement.
"""

from __future__ import annotations

import hashlib
import json
import statistics
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from clock import LeakageError, parse_iso, search  # noqa: E402
from composite import composite  # noqa: E402

CORPUS_PATH = ROOT / "data" / "corpus" / "events.jsonl"
OUT_PATH = ROOT / "data" / "corpus" / "last_backtest.json"

COMPOSITE_KILL = 6.5
SATURATION_LIQ = 25_000
WINNER_MCAP = 250_000
MILLION_MCAP = 1_000_000
HARD_GATES = {
    "tragedy",
    "minor",
    "private_individual",
    "trademark",
    "slur",
    "saturated",
}


def load_events(path: Path = CORPUS_PATH) -> list[dict]:
    events = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            events.append(json.loads(line))
    return events


def _latency_minutes(event: dict) -> float:
    b = parse_iso(event["breakout_at"])
    d = parse_iso(event["decision_at"])
    return (d - b).total_seconds() / 60.0


def _citations_asof(snapshot: dict, as_of: str) -> list:
    signals = snapshot.get("fixture_signals") or {}
    raw = signals.get("citations") or []
    records = []
    for c in raw:
        if isinstance(c, str):
            records.append({"ref": c})
        else:
            records.append(c)
    return search(as_of, records)


def run_adversary(snapshot: dict, scores: dict, comp: float) -> Optional[dict]:
    """Separate adversary step AFTER analyst, seeing analyst scores."""
    fixture = snapshot.get("adversary_fixture")
    if fixture is None:
        return None
    # Adversary is allowed to see scores/composite; fixture is the recorded call.
    _ = (scores, comp)
    return fixture


def outcome_pnl(outcome: dict) -> float:
    peak = outcome.get("peak_mcap_usd")
    verdict = outcome.get("verdict") or ""
    if peak is not None:
        raw = float(peak) / float(WINNER_MCAP) - 1.0
        return max(-1.0, min(raw, 10.0))
    mapping = {
        "winner": 1.0,
        "flat": 0.0,
        "dud": -1.0,
        "rugged_by_market": -1.0,
        "never_launched": 0.0,
    }
    return mapping.get(verdict, 0.0)


def is_winner(outcome: dict) -> bool:
    peak = outcome.get("peak_mcap_usd")
    return peak is not None and float(peak) >= WINNER_MCAP


def evaluate_event(event: dict, *, require_adversary: bool = True) -> dict:
    """Pipeline for one event using only asof_snapshot (clock-enforced)."""
    as_of = event["decision_at"]
    if parse_iso(as_of) <= parse_iso(event["breakout_at"]):
        raise ValueError(f"{event.get('id')}: decision_at must be after breakout_at")

    snapshot = event.get("asof_snapshot") or {}
    outcome = event.get("outcome") or {}
    latency = _latency_minutes(event)

    result = {
        "id": event.get("id"),
        "topic_key": event.get("topic_key"),
        "vertical": event.get("vertical"),
        "status": None,
        "surfaced": False,
        "analyzed": False,
        "composite": None,
        "kill_reason": None,
        "launch_ready": False,
        "would_launch": False,
        "adversary_blocked": False,
        "counterfactual_launch_ready": False,
        "latency_minutes": latency,
        "human_approved": bool(snapshot.get("human_approved", False)),
        "winner": is_winner(outcome),
        "peak_mcap_usd": outcome.get("peak_mcap_usd"),
        "verdict": outcome.get("verdict"),
        "crypto_native": bool(event.get("crypto_native")),
        "hard_gate": snapshot.get("hard_gate"),
        "adversary_severity": None,
    }

    # Never feed future_leak into the decision. If a caller did, clock raises.
    # We still probe it so the leakage test has something to catch elsewhere.
    _ = event.get("future_leak")

    citations = _citations_asof(snapshot, as_of)

    # 1. Discard uncited scout items (<2 citations)
    if len(citations) < 2:
        result["status"] = "discarded_uncited"
        result["kill_reason"] = "uncited"
        return result

    result["surfaced"] = True  # promoted to candidate

    # 2. Hard gates → vetoed WITHOUT scoring
    gate = snapshot.get("hard_gate")
    if gate:
        if gate not in HARD_GATES:
            # unknown gate string still vetoes; do not score
            pass
        result["status"] = "vetoed_gate"
        result["kill_reason"] = f"hard_gate:{gate}"
        return result

    # 3. Analyst composite via composite.py
    scores = snapshot.get("analyst_fixture_scores")
    if not scores:
        result["status"] = "vetoed_composite"
        result["kill_reason"] = "missing_scores"
        return result
    comp = composite(scores)
    result["composite"] = comp
    result["analyzed"] = True
    if comp < COMPOSITE_KILL:
        result["status"] = "vetoed_composite"
        result["kill_reason"] = f"composite<{COMPOSITE_KILL}"
        return result

    # 4. Adversary as a SEPARATE step after analyst, seeing analyst scores
    adv = run_adversary(snapshot, scores, comp) if require_adversary else None
    result["adversary_severity"] = None if adv is None else adv.get("severity")
    adv_ok = bool(adv) and adv.get("severity") in ("pass", "warn")

    # 5. Saturation via existing liquid tokens
    saturated = False
    for tok in snapshot.get("existing_tokens") or []:
        liq = tok.get("liq_usd") or 0
        if float(liq) > SATURATION_LIQ:
            saturated = True
            break

    gates_clear = (not saturated) and (not gate)
    # counterfactual: if adversary had passed
    result["counterfactual_launch_ready"] = bool(
        gates_clear and comp >= COMPOSITE_KILL
    )

    if adv is None:
        result["status"] = "vetoed_no_adversary"
        result["kill_reason"] = "adversary_missing"
        return result
    if adv.get("severity") == "block":
        result["adversary_blocked"] = True
        result["status"] = "vetoed_adversary"
        result["kill_reason"] = "adversary_block"
        return result
    if not adv_ok:
        result["status"] = "vetoed_adversary"
        result["kill_reason"] = f"adversary_severity:{adv.get('severity')}"
        return result

    if saturated:
        result["status"] = "vetoed_saturation"
        result["kill_reason"] = "existing_token_liq>25000"
        return result

    # 6. launch_ready (pre-human) vs would_launch (post-human)
    result["launch_ready"] = True
    result["would_launch"] = bool(snapshot.get("human_approved", False))
    result["status"] = "would_launch" if result["would_launch"] else "launch_ready"
    return result


def id_half(eid: str) -> str:
    h = int(hashlib.sha256(str(eid).encode("utf-8")).hexdigest(), 16)
    return "even" if h % 2 == 0 else "odd"


def _precision(rows: list[dict]) -> Optional[float]:
    n = len(rows)
    if n == 0:
        return None
    hits = sum(1 for r in rows if r["winner"])
    return hits / n


def _bucket(comp: Optional[float]) -> Optional[str]:
    if comp is None:
        return None
    if comp < 3:
        return "[0,3)"
    if comp < 5:
        return "[3,5)"
    if comp < 6.5:
        return "[5,6.5)"
    if comp < 8:
        return "[6.5,8)"
    return "[8,10]"


def run_backtest(events: Optional[list[dict]] = None) -> dict:
    if events is None:
        events = load_events()
    results = [evaluate_event(ev) for ev in events]

    n = len(results)
    launch_ready = [r for r in results if r["launch_ready"]]
    killed = [r for r in results if not r["launch_ready"]]
    would_launch = [r for r in results if r["would_launch"]]

    precision = _precision(launch_ready)

    million_events = [
        r for r in results
        if r.get("peak_mcap_usd") is not None and float(r["peak_mcap_usd"]) >= MILLION_MCAP
    ]
    million_surfaced = [r for r in million_events if r["surfaced"]]
    recall = (
        None if not million_events else len(million_surfaced) / len(million_events)
    )

    # Adversary value: hypothetical PnL of cases that would have been
    # launch_ready if adversary had passed, but were blocked.
    adv_rows = []
    for ev, r in zip(events, results):
        if r["adversary_blocked"] and r["counterfactual_launch_ready"]:
            pnl = outcome_pnl(ev.get("outcome") or {})
            adv_rows.append({"id": r["id"], "pnl": pnl, "verdict": r["verdict"]})
    adv_value = sum(x["pnl"] for x in adv_rows)
    if adv_value < 0:
        adv_interp = (
            "adversary is earning its seat (blocked net-negative hypothetical PnL)"
        )
    elif adv_value > 0:
        adv_interp = (
            "adversary is NOT earning its seat (blocked net-positive hypothetical PnL)"
        )
    else:
        adv_interp = "adversary PnL is zero (no signal either way)"

    latencies = [r["latency_minutes"] for r in launch_ready]
    median_lat = statistics.median(latencies) if latencies else None
    latency_flag = bool(median_lat is not None and median_lat > 45)

    calib_order = ["[0,3)", "[3,5)", "[5,6.5)", "[6.5,8)", "[8,10]"]
    calib = {b: {"n": 0, "winners": 0, "winner_rate": None} for b in calib_order}
    for r in results:
        b = _bucket(r["composite"])
        if b is None:
            continue
        calib[b]["n"] += 1
        if r["winner"]:
            calib[b]["winners"] += 1
    for b in calib_order:
        n_b = calib[b]["n"]
        calib[b]["winner_rate"] = (calib[b]["winners"] / n_b) if n_b else None

    even_ready = [r for r in launch_ready if id_half(r["id"]) == "even"]
    odd_ready = [r for r in launch_ready if id_half(r["id"]) == "odd"]
    prec_even = _precision(even_ready)
    prec_odd = _precision(odd_ready)

    n_winners = sum(1 for r in results if r["winner"])
    n_duds = n - n_winners

    status_counts: dict[str, int] = {}
    for r in results:
        status_counts[r["status"]] = status_counts.get(r["status"], 0) + 1

    report = {
        "n_events": n,
        "n_launch_ready": len(launch_ready),
        "n_killed": len(killed),
        "n_would_launch": len(would_launch),
        "n_winners_250k": n_winners,
        "n_duds_or_nonwinners": n_duds,
        "precision_at_launch": precision,
        "precision_at_launch_even": prec_even,
        "precision_at_launch_odd": prec_odd,
        "n_launch_ready_even": len(even_ready),
        "n_launch_ready_odd": len(odd_ready),
        "recall": recall,
        "n_million": len(million_events),
        "n_million_surfaced": len(million_surfaced),
        "adversary_value": adv_value,
        "adversary_n_blocked_counterfactual": len(adv_rows),
        "adversary_interpretation": adv_interp,
        "median_latency_minutes": median_lat,
        "latency_flag": latency_flag,
        "calibration": calib,
        "status_counts": status_counts,
        "corpus_path": str(CORPUS_PATH),
    }
    return report


def _fmt_rate(x: Optional[float]) -> str:
    if x is None:
        return "undefined (0 launch_ready)"
    return f"{x:.4f}"


def print_report(report: dict) -> None:
    print("=== ALPHA SWARM backtest ===")
    print(f"n_events:        {report['n_events']}")
    print(f"n_launch_ready:  {report['n_launch_ready']}")
    print(f"n_killed:        {report['n_killed']}")
    print(f"n_would_launch:  {report['n_would_launch']}")
    print(f"winners_250k:    {report['n_winners_250k']}")
    print(f"duds/nonwinners: {report['n_duds_or_nonwinners']}")
    print(f"Precision@launch overall: {_fmt_rate(report['precision_at_launch'])}")
    print(
        f"Precision@launch even half: {_fmt_rate(report['precision_at_launch_even'])}"
        f"  (n={report['n_launch_ready_even']})"
    )
    print(
        f"Precision@launch odd half:  {_fmt_rate(report['precision_at_launch_odd'])}"
        f"  (n={report['n_launch_ready_odd']})"
    )
    rec = report["recall"]
    rec_s = "undefined (0 million+ events)" if rec is None else f"{rec:.4f}"
    print(
        f"Recall ($1M+ surfaced): {rec_s}  "
        f"({report['n_million_surfaced']}/{report['n_million']})"
    )
    print(
        f"Adversary value: {report['adversary_value']:.4f}  "
        f"(n_blocked_cf={report['adversary_n_blocked_counterfactual']})"
    )
    print(f"  interpretation: {report['adversary_interpretation']}")
    med = report["median_latency_minutes"]
    if med is None:
        print("Latency median: undefined (0 launch_ready)")
    else:
        flag = " FLAG: median > 45 min" if report["latency_flag"] else " (ok <= 45)"
        print(f"Latency median minutes: {med:.1f}{flag}")
    print("Calibration (composite bucket vs realized winner rate):")
    for b, row in report["calibration"].items():
        wr = row["winner_rate"]
        wr_s = "n/a" if wr is None else f"{wr:.3f}"
        print(f"  {b:8s}  n={row['n']:3d}  winners={row['winners']:3d}  rate={wr_s}")
    print("status_counts:", json.dumps(report["status_counts"], sort_keys=True))


def write_report(report: dict, path: Path = OUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    serial = json.loads(json.dumps(report))
    path.write_text(json.dumps(serial, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {path}")


def main() -> int:
    events = load_events()
    report = run_backtest(events)
    print_report(report)
    write_report(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
