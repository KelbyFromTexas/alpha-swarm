#!/usr/bin/env python3
"""Mandatory stream gate. Filter BEFORE any write to board files. Never print keys."""
from __future__ import annotations

import re
from pathlib import Path

LAUNCH = Path("/workspace/alpha-swarm-launch")
BOARD = LAUNCH / "PAIR_FEED_BOARD.txt"
SCORED = LAUNCH / "SCORED_PAIRS.txt"
IGNORE_MINT = "EwvtKCZsjHZWWMirU5xvtwXcrsvHsuKoth868pujpump"

# slur/hate fragments (do not echo matches onto the board)
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


def blob_of(p: dict) -> str:
    return f"{p.get('name') or ''} {p.get('symbol') or ''} {p.get('ticker') or ''}"


def blocked_reason(p: dict) -> str | None:
    mint = str(p.get("mint") or "")
    if mint == IGNORE_MINT:
        return "house_swan"
    blob = blob_of(p)
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


def filter_pairs(rows: list) -> tuple[list, dict]:
    kept, omitted, seen = [], {}, set()
    for p in rows or []:
        if not isinstance(p, dict):
            continue
        mint = p.get("mint")
        if mint and mint in seen:
            continue
        if mint:
            seen.add(mint)
        reason = blocked_reason(p)
        if reason:
            omitted[reason] = omitted.get(reason, 0) + 1
            continue
        kept.append(p)
    return kept, omitted


def scrub_text(text: str) -> tuple[str, int]:
    """Drop any line that still matches the slur regex. Last-line defense."""
    dropped = 0
    out = []
    for line in (text or "").splitlines():
        if SLUR_RE.search(line):
            dropped += 1
            continue
        out.append(line)
    body = "\n".join(out)
    if text.endswith("\n"):
        body += "\n"
    return body, dropped


def write_stream_boards(board_body: str, scored_prefix: str | None = None) -> dict:
    """ONLY allowed writer for livestream pair boards. Filters text then writes both files."""
    board_body, n1 = scrub_text(board_body)
    prefix = scored_prefix if scored_prefix is not None else "SCORED PAIRS — third editor (refreshes every 3m)\n\n"
    scored_body, n2 = scrub_text(prefix + board_body)
    # refuse to persist if scrub missed (shouldn't happen)
    if SLUR_RE.search(board_body) or SLUR_RE.search(scored_body):
        raise RuntimeError("slur filter failed; aborting board write")
    LAUNCH.mkdir(parents=True, exist_ok=True)
    tmp_b = BOARD.with_suffix(".txt.tmp")
    tmp_s = SCORED.with_suffix(".txt.tmp")
    tmp_b.write_text(board_body, encoding="utf-8")
    tmp_s.write_text(scored_body, encoding="utf-8")
    tmp_b.replace(BOARD)
    tmp_s.replace(SCORED)
    return {"board": str(BOARD), "scored": str(SCORED), "lines_dropped": n1 + n2}


def rescrub_on_disk() -> dict:
    n = 0
    for path in (BOARD, SCORED):
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        clean, dropped = scrub_text(raw)
        if dropped:
            path.write_text(clean, encoding="utf-8")
            n += dropped
    return {"rescrubbed_lines": n}
