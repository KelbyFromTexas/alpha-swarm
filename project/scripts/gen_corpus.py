#!/usr/bin/env python3
"""Build data/corpus/events.jsonl — 100+ mixed winners and duds."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("/home/box/agent-data/projects/alpha-swarm")
OUT = ROOT / "data" / "corpus" / "events.jsonl"
VERTICALS = [
    "sports", "politics-and-courts", "music-and-celebrity",
    "gaming-and-anime", "tech-and-ai", "internet-native",
]
GATES = ("tragedy", "minor", "private_individual", "trademark", "slur", "saturated")


def iso(dt: datetime) -> str:
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse(s: str) -> datetime:
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def cites(decision_at: str, n: int, term: str) -> list:
    t0 = parse(decision_at)
    out = []
    for i in range(n):
        ts = t0 - timedelta(minutes=8 + i * 6)
        out.append({
            "source": "x.com" if i % 2 == 0 else "web",
            "ref": f"https://example.invalid/cite/{term}/{i}",
            "title": f"{term} mention {i+1}",
            "timestamp": iso(ts),
        })
    return out


def scores(**kw) -> dict:
    base = {k: 6.0 for k in (
        "acceleration", "earliness", "memeability", "ticker_quality",
        "narrative_legs", "cultural_distance", "saturation_inverse",
    )}
    base.update({k: float(v) for k, v in kw.items()})
    return base


def ev(eid, topic_key, raw_term, vertical, breakout_at, decision_min,
       crypto_native, source_kind, spawned, peak, duration, verdict,
       volume_now, volume_prior, accel, n_cites, hard_gate, sc, adv_sev,
       adv_reasons, existing=None, human_approved=False, leak=False):
    b = parse(breakout_at)
    d = b + timedelta(minutes=decision_min)
    decision_at = iso(d)
    snap = {
        "fixture_signals": {
            "volume_now": volume_now,
            "volume_prior": volume_prior,
            "accel_estimate": accel,
            "citations": cites(decision_at, n_cites, topic_key) if n_cites else [],
        },
        "hard_gate": hard_gate,
        "analyst_fixture_scores": sc,
        "adversary_fixture": {"severity": adv_sev, "reasons": list(adv_reasons)},
        "human_approved": bool(human_approved),
    }
    if existing is not None:
        snap["existing_tokens"] = existing
    obj = {
        "id": eid,
        "topic_key": topic_key,
        "raw_term": raw_term,
        "vertical": vertical,
        "breakout_at": iso(b),
        "decision_at": decision_at,
        "crypto_native": crypto_native,
        "source_kind": source_kind,
        "outcome": {
            "spawned_token": spawned,
            "peak_mcap_usd": peak,
            "duration_hours": duration,
            "verdict": verdict,
        },
        "asof_snapshot": snap,
    }
    if leak:
        leak_ts = iso(d + timedelta(hours=6))
        obj["future_leak"] = {
            "kind": "future_leak",
            "timestamp": leak_ts,
            "posts": [{"timestamp": leak_ts, "text": f"post-decision chatter about {raw_term}"}],
            "tokens": [{
                "timestamp": iso(d + timedelta(hours=8)),
                "name": raw_term,
                "ticker": topic_key.upper()[:8],
                "note": "token print that did not exist at decision_at",
            }],
        }
    return obj


def high(**over):
    s = scores(acceleration=8.0, earliness=8.0, memeability=8.0,
               ticker_quality=8.0, narrative_legs=7.5,
               cultural_distance=8.0, saturation_inverse=8.0)
    s.update({k: float(v) for k, v in over.items()})
    return s


def build():
    e = []

    # Public-record million+ / 250k+ winners and known duds (honest approx dates/mcaps)
    pubs = [
        dict(eid="evt-0001", topic_key="goat", raw_term="Goatseus Maximus", vertical="tech-and-ai",
             breakout_at="2024-10-10T16:20:00Z", decision_min=32, crypto_native=False,
             source_kind="public_record", spawned=True, peak=1.2e9, duration=720, verdict="winner",
             volume_now=18400, volume_prior=410, accel=8.7, n_cites=4, hard_gate=None,
             sc=high(acceleration=9.0, earliness=8.5, memeability=9.0, narrative_legs=9.0, cultural_distance=8.5),
             adv_sev="pass", adv_reasons=["fresh AI-cult narrative; no prior liquid ticker"],
             human_approved=True, leak=True),
        dict(eid="evt-0002", topic_key="pnut", raw_term="Peanut the squirrel", vertical="internet-native",
             breakout_at="2024-11-01T16:05:00Z", decision_min=28, crypto_native=False,
             source_kind="public_record", spawned=True, peak=1.5e9, duration=480, verdict="winner",
             volume_now=22000, volume_prior=90, accel=9.4, n_cites=5, hard_gate="tragedy",
             sc=high(acceleration=9.5, earliness=9.0),
             adv_sev="block", adv_reasons=["animal euthanasia; do not monetize death"]),
        dict(eid="evt-0003", topic_key="moodeng", raw_term="Moo Deng pygmy hippo", vertical="internet-native",
             breakout_at="2024-09-11T08:15:00Z", decision_min=41, crypto_native=False,
             source_kind="public_record", spawned=True, peak=3.2e8, duration=600, verdict="winner",
             volume_now=9100, volume_prior=320, accel=7.1, n_cites=3, hard_gate=None,
             sc=high(memeability=9.5, ticker_quality=8.5, cultural_distance=9.0, saturation_inverse=8.5),
             adv_sev="pass", adv_reasons=["living zoo animal, not a death event"], human_approved=True),
        dict(eid="evt-0004", topic_key="wif", raw_term="dogwifhat", vertical="internet-native",
             breakout_at="2023-11-20T18:40:00Z", decision_min=36, crypto_native=False,
             source_kind="public_record", spawned=True, peak=4.5e9, duration=8000, verdict="winner",
             volume_now=5400, volume_prior=180, accel=6.8, n_cites=3, hard_gate=None,
             sc=high(earliness=9.0, memeability=9.0, ticker_quality=9.0, saturation_inverse=9.0),
             adv_sev="pass", adv_reasons=["novel hat-dog image, no liquid original at as_of"], leak=True),
        dict(eid="evt-0005", topic_key="gigachad", raw_term="Gigachad", vertical="internet-native",
             breakout_at="2024-06-15T14:10:00Z", decision_min=44, crypto_native=False,
             source_kind="public_record", spawned=True, peak=8.0e8, duration=4000, verdict="winner",
             volume_now=7200, volume_prior=900, accel=5.4, n_cites=3, hard_gate=None,
             sc=high(acceleration=7.5, earliness=7.0, cultural_distance=6.5, saturation_inverse=7.0),
             adv_sev="warn", adv_reasons=["meme is old; confirm no large incumbent ticker"]),
        dict(eid="evt-0006", topic_key="fartcoin", raw_term="Fartcoin", vertical="tech-and-ai",
             breakout_at="2024-10-20T15:30:00Z", decision_min=38, crypto_native=False,
             source_kind="public_record", spawned=True, peak=1.4e9, duration=2500, verdict="winner",
             volume_now=11000, volume_prior=600, accel=6.9, n_cites=3, hard_gate=None,
             sc=high(ticker_quality=6.5, narrative_legs=8.5),
             adv_sev="warn", adv_reasons=["vulgar ticker; still original at as_of"], human_approved=True),
        dict(eid="evt-0007", topic_key="bome", raw_term="Book of Meme", vertical="internet-native",
             breakout_at="2024-03-14T13:05:00Z", decision_min=29, crypto_native=False,
             source_kind="public_record", spawned=True, peak=1.1e9, duration=2000, verdict="winner",
             volume_now=16000, volume_prior=500, accel=8.1, n_cites=4, hard_gate=None,
             sc=high(acceleration=8.5),
             adv_sev="pass", adv_reasons=["artist-led drop, first print"]),
        dict(eid="evt-0008", topic_key="neiro", raw_term="Neiro", vertical="internet-native",
             breakout_at="2024-07-27T12:20:00Z", decision_min=55, crypto_native=False,
             source_kind="public_record", spawned=True, peak=8.0e8, duration=3000, verdict="winner",
             volume_now=6400, volume_prior=1100, accel=3.2, n_cites=3, hard_gate=None,
             sc=scores(acceleration=5.0, earliness=5.5, memeability=6.0, ticker_quality=6.5,
                       narrative_legs=5.0, cultural_distance=4.5, saturation_inverse=5.5),
             adv_sev="pass", adv_reasons=["dog-successor narrative; scores look soft"], leak=True),
        dict(eid="evt-0009", topic_key="popcat", raw_term="POPCAT", vertical="internet-native",
             breakout_at="2024-07-01T12:00:00Z", decision_min=900, crypto_native=True,
             source_kind="public_record", spawned=True, peak=1.8e9, duration=5000, verdict="winner",
             volume_now=19000, volume_prior=12000, accel=1.1, n_cites=3, hard_gate=None,
             sc=scores(acceleration=6.0, earliness=2.0, memeability=8.0, ticker_quality=8.0,
                       narrative_legs=6.0, cultural_distance=3.0, saturation_inverse=2.0),
             adv_sev="block", adv_reasons=["incumbent already liquid; late wave"],
             existing=[{"name": "POPCAT", "ticker": "POPCAT", "liq_usd": 4_200_000}]),
        dict(eid="evt-0010", topic_key="ai16z", raw_term="ai16z", vertical="tech-and-ai",
             breakout_at="2024-10-25T17:00:00Z", decision_min=48, crypto_native=True,
             source_kind="public_record", spawned=True, peak=2.1e9, duration=2800, verdict="winner",
             volume_now=8800, volume_prior=400, accel=7.0, n_cites=1, hard_gate=None,
             sc=high(acceleration=8.5, narrative_legs=8.5),
             adv_sev="pass", adv_reasons=["would have been interesting if cited"]),
        dict(eid="evt-0011", topic_key="luce", raw_term="Luce Vatican mascot", vertical="music-and-celebrity",
             breakout_at="2024-10-28T10:40:00Z", decision_min=34, crypto_native=False,
             source_kind="public_record", spawned=True, peak=8.5e5, duration=72, verdict="winner",
             volume_now=3100, volume_prior=140, accel=5.9, n_cites=3, hard_gate=None,
             sc=high(narrative_legs=6.5, cultural_distance=8.5),
             adv_sev="warn", adv_reasons=["religious mascot; taste/PR risk"]),
        dict(eid="evt-0012", topic_key="boden-early", raw_term="BODEN", vertical="politics-and-courts",
             breakout_at="2024-03-18T14:15:00Z", decision_min=40, crypto_native=False,
             source_kind="public_record", spawned=True, peak=7.2e5, duration=96, verdict="winner",
             volume_now=2700, volume_prior=80, accel=6.4, n_cites=2, hard_gate=None,
             sc=high(acceleration=7.0, memeability=7.0, narrative_legs=6.0, cultural_distance=7.0),
             adv_sev="warn", adv_reasons=["political caricature; election-adjacent"]),
        dict(eid="evt-0013", topic_key="tremp-early", raw_term="TREMP", vertical="politics-and-courts",
             breakout_at="2024-03-18T14:45:00Z", decision_min=25, crypto_native=False,
             source_kind="public_record", spawned=True, peak=6.1e5, duration=80, verdict="winner",
             volume_now=2500, volume_prior=70, accel=6.2, n_cites=2, hard_gate=None,
             sc=high(acceleration=7.0, memeability=7.0, ticker_quality=7.0, narrative_legs=6.0, cultural_distance=6.5),
             adv_sev="pass", adv_reasons=["parody spelling, not impersonation of a private person"]),
        dict(eid="evt-0014", topic_key="gta6-trailer-sol", raw_term="GTA 6 trailer coin", vertical="gaming-and-anime",
             breakout_at="2023-12-04T16:05:00Z", decision_min=22, crypto_native=False,
             source_kind="public_record", spawned=True, peak=4.4e5, duration=18, verdict="winner",
             volume_now=4100, volume_prior=50, accel=8.0, n_cites=3, hard_gate=None,
             sc=high(acceleration=8.5, earliness=9.0, memeability=7.0, ticker_quality=6.0, narrative_legs=5.5, cultural_distance=5.0, saturation_inverse=7.5),
             adv_sev="warn", adv_reasons=["game IP adjacent; first-wave only"], leak=True),
        dict(eid="evt-0015", topic_key="notlikeus-early", raw_term="Not Like Us", vertical="music-and-celebrity",
             breakout_at="2024-05-04T20:10:00Z", decision_min=50, crypto_native=False,
             source_kind="public_record", spawned=True, peak=3.8e5, duration=30, verdict="winner",
             volume_now=3600, volume_prior=200, accel=5.8, n_cites=3, hard_gate=None,
             sc=high(acceleration=7.5, earliness=7.5, ticker_quality=6.5, narrative_legs=7.0, cultural_distance=6.0, saturation_inverse=7.5),
             adv_sev="pass", adv_reasons=["song-title meme"]),
        dict(eid="evt-0016", topic_key="olympics-breakdance", raw_term="Olympic breaking 2024", vertical="sports",
             breakout_at="2024-08-09T18:30:00Z", decision_min=35, crypto_native=False,
             source_kind="public_record", spawned=True, peak=2.9e5, duration=24, verdict="winner",
             volume_now=1800, volume_prior=90, accel=5.1, n_cites=2, hard_gate=None,
             sc=high(acceleration=7.0, earliness=7.5, memeability=7.5, ticker_quality=6.5, narrative_legs=6.0, cultural_distance=7.0),
             adv_sev="pass", adv_reasons=["sports meme window"]),
        dict(eid="evt-0017", topic_key="dandadan-szn", raw_term="Dandadan", vertical="gaming-and-anime",
             breakout_at="2024-10-04T11:00:00Z", decision_min=60, crypto_native=False,
             source_kind="public_record", spawned=True, peak=5.1e5, duration=48, verdict="winner",
             volume_now=2200, volume_prior=150, accel=4.8, n_cites=3, hard_gate=None,
             sc=high(acceleration=7.0, earliness=7.0, ticker_quality=7.5, narrative_legs=7.0, saturation_inverse=7.5),
             adv_sev="pass", adv_reasons=["seasonal anime breakout"]),
        dict(eid="evt-0018", topic_key="michi-early", raw_term="MICHI", vertical="internet-native",
             breakout_at="2024-04-10T15:20:00Z", decision_min=33, crypto_native=False,
             source_kind="public_record", spawned=True, peak=9.4e5, duration=200, verdict="winner",
             volume_now=2900, volume_prior=120, accel=5.6, n_cites=2, hard_gate=None,
             sc=high(acceleration=7.5, narrative_legs=6.5, cultural_distance=6.5, saturation_inverse=7.5),
             adv_sev="pass", adv_reasons=["cat-with-hat still early"]),
        dict(eid="evt-0019", topic_key="slerf", raw_term="SLERF", vertical="internet-native",
             breakout_at="2024-03-17T15:10:00Z", decision_min=27, crypto_native=True,
             source_kind="public_record", spawned=True, peak=2.5e8, duration=12, verdict="rugged_by_market",
             volume_now=15000, volume_prior=200, accel=9.0, n_cites=3, hard_gate=None,
             sc=scores(acceleration=9.0, earliness=8.0, memeability=6.0, ticker_quality=4.0,
                       narrative_legs=4.0, cultural_distance=5.0, saturation_inverse=7.0),
             adv_sev="block", adv_reasons=["dev opsec / LP-burn risk; thin cultural legs"]),
        dict(eid="evt-0020", topic_key="hawk-tuah-late", raw_term="Hawk Tuah copy", vertical="internet-native",
             breakout_at="2024-06-12T12:00:00Z", decision_min=960, crypto_native=False,
             source_kind="public_record", spawned=True, peak=None, duration=6, verdict="dud",
             volume_now=8000, volume_prior=7000, accel=0.4, n_cites=2, hard_gate=None,
             sc=scores(acceleration=4.0, earliness=2.0, memeability=6.0, ticker_quality=5.0,
                       narrative_legs=3.0, cultural_distance=3.0, saturation_inverse=2.0),
             adv_sev="block", adv_reasons=["original already dumped; copy-wave"],
             existing=[{"name": "HAWK", "ticker": "HAWK", "liq_usd": 180000}]),
        dict(eid="evt-0021", topic_key="goat-copy-1", raw_term="GOAT2", vertical="tech-and-ai",
             breakout_at="2024-10-11T09:00:00Z", decision_min=80, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=4, verdict="dud",
             volume_now=5000, volume_prior=4000, accel=0.8, n_cites=2, hard_gate="saturated",
             sc=scores(acceleration=5.0, earliness=3.0, memeability=6.0, ticker_quality=3.0,
                       narrative_legs=2.0, cultural_distance=2.0, saturation_inverse=0.0),
             adv_sev="block", adv_reasons=["clone after price discovery"],
             existing=[{"name": "GOAT", "ticker": "GOAT", "liq_usd": 12_000_000}]),
        dict(eid="evt-0022", topic_key="pnut-copy-1", raw_term="PNUT2", vertical="internet-native",
             breakout_at="2024-11-02T08:00:00Z", decision_min=70, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=3, verdict="dud",
             volume_now=4200, volume_prior=3000, accel=0.9, n_cites=2, hard_gate="saturated",
             sc=scores(saturation_inverse=0.0, earliness=2.0),
             adv_sev="block", adv_reasons=["original already liquid"],
             existing=[{"name": "PNUT", "ticker": "PNUT", "liq_usd": 8_000_000}]),
        dict(eid="evt-0023", topic_key="pepe-sol-copy", raw_term="PEPE on Solana", vertical="internet-native",
             breakout_at="2024-04-02T11:00:00Z", decision_min=45, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=8, verdict="dud",
             volume_now=9000, volume_prior=8500, accel=0.3, n_cites=3, hard_gate=None,
             sc=scores(acceleration=5.0, earliness=3.0, memeability=8.0, ticker_quality=8.0,
                       narrative_legs=4.0, cultural_distance=1.0, saturation_inverse=0.0),
             adv_sev="block", adv_reasons=["crypto-native already-priced meme"],
             existing=[{"name": "PEPE", "ticker": "PEPE", "liq_usd": 50_000_000}]),
        dict(eid="evt-0024", topic_key="harambe-2024", raw_term="HARAMBE", vertical="internet-native",
             breakout_at="2024-05-28T16:00:00Z", decision_min=40, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=5, verdict="dud",
             volume_now=3000, volume_prior=2500, accel=0.5, n_cites=2, hard_gate="saturated",
             sc=scores(saturation_inverse=0.0, cultural_distance=1.0, earliness=1.0),
             adv_sev="block", adv_reasons=["2016 meme, endlessly recapitalized"]),
        dict(eid="evt-0025", topic_key="chillguy", raw_term="Just a chill guy", vertical="internet-native",
             breakout_at="2024-11-09T18:20:00Z", decision_min=42, crypto_native=False,
             source_kind="public_record", spawned=True, peak=2.5e8, duration=400, verdict="winner",
             volume_now=7600, volume_prior=200, accel=7.2, n_cites=3, hard_gate="trademark",
             sc=high(acceleration=8.0, earliness=8.5, memeability=9.0, saturation_inverse=8.5),
             adv_sev="block", adv_reasons=["illustrator IP; artist did not consent"]),
        dict(eid="evt-0026", topic_key="mother-iggy", raw_term="MOTHER Iggy", vertical="music-and-celebrity",
             breakout_at="2024-10-09T19:00:00Z", decision_min=58, crypto_native=False,
             source_kind="public_record", spawned=True, peak=None, duration=72, verdict="flat",
             volume_now=2100, volume_prior=400, accel=3.4, n_cites=2, hard_gate=None,
             sc=scores(acceleration=6.0, earliness=6.5, memeability=6.5, ticker_quality=7.0,
                       narrative_legs=5.5, cultural_distance=5.0, saturation_inverse=6.0),
             adv_sev="warn", adv_reasons=["celebrity-issued coins often round-trip"]),
        dict(eid="evt-0027", topic_key="doge-already", raw_term="DOGE", vertical="internet-native",
             breakout_at="2024-01-15T12:00:00Z", decision_min=30, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=None, verdict="never_launched",
             volume_now=50000, volume_prior=48000, accel=0.2, n_cites=4, hard_gate=None,
             sc=scores(acceleration=3.0, earliness=1.0, memeability=9.0, ticker_quality=9.0,
                       narrative_legs=3.0, cultural_distance=0.0, saturation_inverse=0.0),
             adv_sev="block", adv_reasons=["already-priced crypto-native bluechip"],
             existing=[{"name": "Dogecoin", "ticker": "DOGE", "liq_usd": 1_000_000_000}]),
        dict(eid="evt-0028", topic_key="maga-late-nov", raw_term="MAGA election late", vertical="politics-and-courts",
             breakout_at="2024-11-06T05:00:00Z", decision_min=800, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=10, verdict="dud",
             volume_now=12000, volume_prior=11000, accel=0.3, n_cites=2, hard_gate="saturated",
             sc=scores(earliness=1.0, saturation_inverse=0.0),
             adv_sev="block", adv_reasons=["election already called; tickers saturated"],
             existing=[{"name": "MAGA", "ticker": "TRUMP", "liq_usd": 20_000_000}]),
        dict(eid="evt-0029", topic_key="fwog-late", raw_term="FWOG late copy", vertical="internet-native",
             breakout_at="2024-07-22T12:00:00Z", decision_min=1100, crypto_native=True,
             source_kind="public_record", spawned=True, peak=None, duration=5, verdict="dud",
             volume_now=4000, volume_prior=3800, accel=0.2, n_cites=2, hard_gate=None,
             sc=scores(acceleration=4.0, earliness=1.5, memeability=7.0, ticker_quality=7.0,
                       narrative_legs=3.0, cultural_distance=3.0, saturation_inverse=1.0),
             adv_sev="block", adv_reasons=["second-wave after price discovery"],
             existing=[{"name": "FWOG", "ticker": "FWOG", "liq_usd": 900_000}]),
        dict(eid="evt-0030", topic_key="act-i", raw_term="Act I The AI Prophecy", vertical="tech-and-ai",
             breakout_at="2024-11-08T16:40:00Z", decision_min=47, crypto_native=True,
             source_kind="public_record", spawned=True, peak=3.0e8, duration=900, verdict="winner",
             volume_now=6700, volume_prior=800, accel=5.0, n_cites=3, hard_gate=None,
             sc=high(acceleration=7.0, earliness=6.5, memeability=6.5, ticker_quality=7.0,
                     narrative_legs=8.0, cultural_distance=6.0, saturation_inverse=6.5),
             adv_sev="pass", adv_reasons=["adjacent lore but distinct ticker"]),
    ]
    for p in pubs:
        e.append(ev(**p))

    # Hard gates (synthetic) — kill without scoring. Include all six gate types.
    gate_rows = [
        ("evt-0031", "bridge-memorial", "bridge collapse memorial", "sports", "tragedy"),
        ("evt-0032", "school-incident", "school incident trend", "politics-and-courts", "minor"),
        ("evt-0033", "studio-mouse", "famous studio mouse coin", "music-and-celebrity", "trademark"),
        ("evt-0034", "blocked-word-ticker", "blocked-word ticker attempt", "internet-native", "slur"),
        ("evt-0035", "sat-tick", "already saturated ticker", "tech-and-ai", "saturated"),
        ("evt-0036", "neighbor-kid", "local child celebrity", "music-and-celebrity", "minor"),
        ("evt-0037", "private-nurse", "viral private nurse name", "politics-and-courts", "private_individual"),
        ("evt-0038", "crime-suspect-trend", "crime-suspect name trend", "politics-and-courts", "tragedy"),
        ("evt-0039", "console-plumber", "console plumber coin", "gaming-and-anime", "trademark"),
        ("evt-0040", "grief-hashtag", "funeral hashtag", "sports", "tragedy"),
    ]
    for i, (eid, key, term, vert, gate) in enumerate(gate_rows):
        e.append(ev(
            eid, key, term, vert, f"2024-{(i%12)+1:02d}-{(i%27)+1:02d}T12:00:00Z",
            30+i, False, "synthetic_dud", False, None, None, "never_launched",
            2000+i*100, 100, 6.0, 2, gate, high(acceleration=9.0, earliness=9.0, memeability=9.0),
            "pass", ["gate should fire before adversary"],
        ))

    # Bot-farm: analyst over-scores, adversary blocks (adversary-value cases)
    farms = [
        ("evt-0041", "farm-glorp", "GLORP bot farm", "internet-native", "dud", False),
        ("evt-0042", "farm-zorp", "ZORP engagement pod", "tech-and-ai", "dud", True),
        ("evt-0043", "farm-blip", "BLIP telegram raid", "gaming-and-anime", "rugged_by_market", True),
        ("evt-0044", "farm-qwe1", "QWE1 recycled ticker", "sports", "dud", False),
    ]
    for eid, key, term, vert, verd, spawned in farms:
        e.append(ev(
            eid, key, term, vert, "2024-08-14T09:10:00Z", 28, False, "synthetic_dud",
            spawned, None, 2 if spawned else None, verd, 22000, 40, 9.6, 4, None,
            high(acceleration=9.2, earliness=9.0, memeability=8.0, ticker_quality=8.0,
                 narrative_legs=7.8, cultural_distance=7.8, saturation_inverse=8.6),
            "block", ["manufactured / botnet signal; no organic authors"],
        ))

    # Low-accel high-volume noise
    for i, vert in enumerate(VERTICALS):
        e.append(ev(
            f"evt-{45+i:04d}", f"noise-vol-{vert[:4]}", f"high volume {vert} noise", vert,
            f"2024-{(i%9)+1:02d}-{10+i:02d}T10:00:00Z", 50+i*3, False, "synthetic_dud",
            False, None, None, "never_launched", 25000+i*1000, 24000, 0.15, 3, None,
            scores(acceleration=2.0, earliness=4.0, memeability=4.0, ticker_quality=5.0,
                   narrative_legs=3.0, cultural_distance=4.0, saturation_inverse=5.0),
            "pass", ["volume without acceleration"],
        ))

    # Second-wave timing traps (>12h)
    traps = [
        ("evt-0051", "moodeng-wave2", "MOODENG second wave", "internet-native", "2024-09-12T08:00:00Z"),
        ("evt-0052", "goat-wave2", "GOAT 18h later", "tech-and-ai", "2024-10-11T10:00:00Z"),
        ("evt-0053", "wif-wave2", "WIF anniversary", "internet-native", "2024-11-20T18:00:00Z"),
        ("evt-0054", "nba-finals-late", "NBA finals late ticker", "sports", "2024-06-18T02:00:00Z"),
        ("evt-0055", "album-drop-late", "album drop +16h", "music-and-celebrity", "2024-05-17T04:00:00Z"),
    ]
    for eid, key, term, vert, br in traps:
        e.append(ev(
            eid, key, term, vert, br, 14*60+20, True, "synthetic_dud", True, None, 3, "dud",
            9000, 8000, 0.6, 2, None,
            scores(acceleration=5.0, earliness=1.0, memeability=7.0, ticker_quality=7.0,
                   narrative_legs=4.0, cultural_distance=3.0, saturation_inverse=2.0),
            "warn", ["decision window is >12h after breakout"],
            existing=[{"name": key, "ticker": key[:8].upper(), "liq_usd": 80000}], leak=True,
        ))

    # Analyst miscalibrated earliness; adversary catches
    e.append(ev(
        "evt-0056", "late-miscal", "18h old anime clip", "gaming-and-anime",
        "2024-08-01T01:00:00Z", 18*60, False, "synthetic_near_miss", False, None, None, "never_launched",
        7000, 6500, 0.5, 3, None,
        high(acceleration=8.0, earliness=9.0, memeability=8.0),
        "block", ["analyst earliness is inconsistent with 18h-old first post"],
    ))

    # Crypto-native already-priced
    for i, (eid, key, term) in enumerate([
        ("evt-0057", "btc-pizza", "Bitcoin pizza day"),
        ("evt-0058", "eth-merge-mem", "ETH merge anniversary"),
        ("evt-0059", "pumpfun-meta", "launchpad meta coin"),
        ("evt-0060", "sol-speed", "solana speed narrative"),
    ]):
        e.append(ev(
            eid, key, term, "tech-and-ai", "2024-05-22T12:00:00Z", 40+i, True, "synthetic_dud",
            False, None, None, "never_launched", 6000, 5500, 0.4, 3, None,
            scores(acceleration=4.0, earliness=3.0, memeability=5.0, ticker_quality=6.0,
                   narrative_legs=3.0, cultural_distance=1.0, saturation_inverse=2.0),
            "block", ["crypto-native already-priced narrative"],
        ))

    # Uncited scout discards
    for i, vert in enumerate(VERTICALS):
        e.append(ev(
            f"evt-{61+i:04d}", f"uncited-{vert[:5]}", f"thin {vert} rumor", vert,
            f"2024-07-{5+i:02d}T08:00:00Z", 20+i, False, "synthetic_dud",
            False, None, None, "never_launched", 400, 10, 3.0, i % 2, None,
            scores(acceleration=8.0, earliness=8.0), "pass", [],
        ))

    # Genuine-looking early non-crypto breakouts (some launch_ready false positives)
    genuines = [
        ("evt-0067", "march-madness-buzzer", "buzzer-beater GIFs", "sports", "2024-03-24T02:15:00Z", 28, "pass"),
        ("evt-0068", "viral-dance-x", "kitchen dance original", "music-and-celebrity", "2024-02-11T21:40:00Z", 37, "pass"),
        ("evt-0069", "indie-game-clip", "unknown indie boss clip", "gaming-and-anime", "2024-01-19T16:05:00Z", 43, "warn"),
        ("evt-0070", "court-sketch-meme", "court sketch goes meme", "politics-and-courts", "2024-04-22T17:30:00Z", 52, "pass"),
        ("evt-0071", "new-model-joke", "non-crypto model nickname", "tech-and-ai", "2024-12-01T13:10:00Z", 21, "pass"),
    ]
    for i, (eid, key, term, vert, br, dmin, adv) in enumerate(genuines):
        e.append(ev(
            eid, key, term, vert, br, dmin, False, "synthetic_near_miss", False, None, None, "never_launched",
            3500+i*300, 50, 6.8, 2+i%2, None,
            high(acceleration=7.8, earliness=8.3, memeability=7.6, ticker_quality=7.3,
                 narrative_legs=6.5, cultural_distance=7.8, saturation_inverse=8.2),
            adv, ["organic early breakout"], leak=(eid=="evt-0071"),
        ))

    # Composite calibration: zeros and low/mid bands
    e.append(ev("evt-0072", "zero-sat", "zero saturation_inverse", "tech-and-ai",
                "2024-02-02T12:00:00Z", 30, True, "synthetic_dud", False, None, None, "never_launched",
                1000, 900, 0.1, 2, None, scores(saturation_inverse=0.0, acceleration=8.0, earliness=8.0),
                "pass", []))
    e.append(ev("evt-0073", "zero-meme", "unmemeable jargon", "politics-and-courts",
                "2024-02-03T12:00:00Z", 33, False, "synthetic_dud", False, None, None, "dud",
                800, 200, 1.0, 2, None, scores(memeability=0.0, acceleration=7.0), "pass", []))

    low_band = [
        dict(acc=4.0, ear=4.0, mem=4.0, tic=4.0, nar=4.0, cul=4.0, sat=4.0),
        dict(acc=5.0, ear=3.0, mem=4.0, tic=5.0, nar=3.5, cul=4.0, sat=4.5),
        dict(acc=3.5, ear=5.0, mem=3.0, tic=4.0, nar=4.0, cul=5.0, sat=4.0),
        dict(acc=4.5, ear=4.5, mem=5.0, tic=3.5, nar=4.0, cul=3.5, sat=4.0),
        dict(acc=6.0, ear=6.0, mem=6.0, tic=6.0, nar=6.0, cul=6.0, sat=6.0),
        dict(acc=7.0, ear=5.5, mem=6.0, tic=5.0, nar=6.0, cul=5.5, sat=6.0),
        dict(acc=6.5, ear=6.5, mem=5.5, tic=6.0, nar=5.5, cul=6.0, sat=5.5),
        dict(acc=8.0, ear=6.0, mem=5.0, tic=5.0, nar=5.0, cul=5.0, sat=6.0),
        dict(acc=6.2, ear=6.2, mem=6.2, tic=6.2, nar=6.2, cul=6.2, sat=6.2),
        dict(acc=7.0, ear=7.0, mem=5.0, tic=5.0, nar=5.0, cul=5.0, sat=5.0),
    ]
    for i, scd in enumerate(low_band):
        e.append(ev(
            f"evt-{74+i:04d}", f"cali-low-{i}", f"calibration filler {i}", VERTICALS[i%6],
            f"2024-03-{(i%27)+1:02d}T09:00:00Z", 35+i, False, "synthetic_dud",
            False, None, None, "never_launched" if i%2==0 else "dud",
            1000+i*50, 400, 1.5+i*0.2, 2, None,
            scores(acceleration=scd["acc"], earliness=scd["ear"], memeability=scd["mem"],
                   ticker_quality=scd["tic"], narrative_legs=scd["nar"],
                   cultural_distance=scd["cul"], saturation_inverse=scd["sat"]),
            "pass" if i%3 else "warn", ["calibration filler"],
        ))

    more = [
        ("evt-0084", "nfl-catch-copy", "NFL catch copy ticker", "sports", "dud", 4.0, "pass", False, 40, None),
        ("evt-0085", "debate-clip", "debate clip 9h later", "politics-and-courts", "dud", 5.0, "warn", True, 560, 40000),
        ("evt-0086", "tour-fit", "celebrity tour outfit", "music-and-celebrity", "never_launched", 5.5, "pass", False, 70, None),
        ("evt-0087", "gacha-banner", "gacha banner rage", "gaming-and-anime", "dud", 4.5, "pass", False, 55, None),
        ("evt-0088", "oss-drama", "github drama", "tech-and-ai", "never_launched", 5.8, "pass", False, 32, None),
        ("evt-0089", "ratio-joke", "ratio joke format", "internet-native", "flat", 6.0, "warn", False, 48, None),
        ("evt-0090", "soccer-own-goal", "own goal clip", "sports", "never_launched", 6.3, "pass", False, 29, None),
        ("evt-0091", "filing-pdf", "court pdf screenshot", "politics-and-courts", "dud", 3.5, "pass", False, 61, None),
        ("evt-0092", "feat-rumor", "unconfirmed feature rumor", "music-and-celebrity", "dud", 5.2, "block", False, 44, None),
        ("evt-0093", "patch-notes", "patch notes meme", "gaming-and-anime", "never_launched", 6.1, "pass", False, 38, None),
        ("evt-0094", "benchmark-chart", "benchmark screenshot", "tech-and-ai", "dud", 4.8, "pass", False, 66, None),
        ("evt-0095", "copypasta-old", "old copypasta revival", "internet-native", "dud", 2.5, "block", False, 75, None),
        ("evt-0096", "mascot-fail", "team mascot fail", "sports", "never_launched", 6.8, "pass", False, 27, None),
        ("evt-0097", "injunction-joke", "injunction joke", "politics-and-courts", "never_launched", 5.9, "warn", False, 49, None),
        ("evt-0098", "red-carpet-bug", "red carpet bug", "music-and-celebrity", "dud", 6.4, "pass", False, 36, None),
        ("evt-0099", "speedrun-wr", "speedrun WR clip", "gaming-and-anime", "never_launched", 7.1, "pass", False, 31, None),
        ("evt-0100", "paper-abstract", "viral paper abstract", "tech-and-ai", "never_launched", 6.6, "warn", False, 54, None),
        ("evt-0101", "ascii-art", "new ascii art", "internet-native", "never_launched", 7.4, "pass", False, 23, None),
        ("evt-0102", "walkoff", "walk-off homer", "sports", "never_launched", 6.9, "pass", False, 26, None),
        ("evt-0103", "depo-quote", "deposition quote", "politics-and-courts", "dud", 5.4, "pass", False, 62, None),
        ("evt-0104", "remix-leak-claim", "remix leak claim", "music-and-celebrity", "dud", 4.2, "block", False, 41, None),
        ("evt-0105", "fan-anim", "fan animation", "gaming-and-anime", "never_launched", 7.0, "pass", False, 34, None),
        ("evt-0106", "hardware-teardown", "hardware teardown gag", "tech-and-ai", "never_launched", 5.1, "pass", False, 58, None),
        ("evt-0107", "deep-fried-fmt", "deep-fried format", "internet-native", "dud", 3.8, "pass", False, 72, None),
        ("evt-0108", "locker-room", "locker room chalkboard", "sports", "never_launched", 6.0, "warn", False, 45, None),
        ("evt-0109", "amicus-meme", "amicus brief meme", "politics-and-courts", "never_launched", 5.7, "pass", False, 53, None),
        ("evt-0110", "karaoke-fail", "karaoke fail original", "music-and-celebrity", "never_launched", 7.2, "pass", False, 28, None),
        ("evt-0111", "boss-hitbox", "boss hitbox joke", "gaming-and-anime", "dud", 4.6, "pass", False, 64, None),
        ("evt-0112", "ctx-window", "context window joke", "tech-and-ai", "never_launched", 6.7, "pass", False, 39, None),
        ("evt-0113", "reaction-png", "new reaction png", "internet-native", "never_launched", 7.3, "warn", False, 22, None),
        ("evt-0114", "penalty-miss", "penalty miss copium", "sports", "dud", 5.3, "pass", False, 47, None),
        ("evt-0115", "mugshot-copy", "mugshot copy ticker", "politics-and-courts", "dud", 2.0, "block", True, 900, 60000),
        ("evt-0116", "awards-bit", "awards show bit", "music-and-celebrity", "never_launched", 6.5, "pass", False, 42, None),
        ("evt-0117", "anime-op", "new anime OP clip", "gaming-and-anime", "never_launched", 7.6, "pass", False, 30, None),
        ("evt-0118", "weights-joke", "open weights joke", "tech-and-ai", "never_launched", 6.4, "warn", False, 51, None),
        ("evt-0119", "wojak-variant", "new wojak variant", "internet-native", "flat", 7.0, "pass", False, 35, None),
        ("evt-0120", "mascot-rebrand", "team rebrand mascot", "sports", "never_launched", 6.8, "pass", False, 33, None),
        ("evt-0121", "local-band-riff", "unsigned band riff", "music-and-celebrity", "never_launched", 7.7, "pass", False, 19, None),
        ("evt-0122", "rookie-stare", "rookie press-conference stare", "sports", "never_launched", 8.0, "pass", False, 24, None),
    ]
    for (eid, key, term, vert, verdict, mid, adv, sat_exist, dmin, liq) in more:
        sc = scores(
            acceleration=max(0.0, mid + 0.4),
            earliness=max(0.0, mid - 0.3),
            memeability=max(0.0, mid + 0.2),
            ticker_quality=max(0.0, mid - 0.5),
            narrative_legs=max(0.0, mid - 0.2),
            cultural_distance=max(0.0, mid + 0.1),
            saturation_inverse=0.0 if sat_exist else max(0.0, mid + 0.3),
        )
        existing = None
        if liq is not None:
            existing = [{"name": term, "ticker": key[:8].upper(), "liq_usd": liq}]
        src = "synthetic_dud" if verdict in ("dud", "flat") else "synthetic_near_miss"
        e.append(ev(
            eid, key, term, vert, "2024-08-08T12:00:00Z", dmin, sat_exist, src,
            verdict in ("dud", "flat"), None, 4 if verdict == "dud" else None, verdict,
            1500, 200, max(0.1, mid/3), 2, None, sc, adv, ["synthetic filler"],
            existing=existing, leak=(eid in ("evt-0099", "evt-0113", "evt-0101", "evt-0122")),
        ))
    return e


def main():
    events = build()
    ids = [x["id"] for x in events]
    assert len(ids) == len(set(ids)), "duplicate ids"
    assert len(events) >= 100, len(events)
    verts = {x["vertical"] for x in events}
    assert verts == set(VERTICALS), verts
    kinds = {x["source_kind"] for x in events}
    assert kinds <= {"public_record", "synthetic_dud", "synthetic_near_miss"}
    winners = [x for x in events if (x["outcome"]["peak_mcap_usd"] or 0) >= 250000]
    millions = [x for x in events if (x["outcome"]["peak_mcap_usd"] or 0) >= 1e6]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8") as f:
        for obj in events:
            f.write(json.dumps(obj, ensure_ascii=False) + "\n")
    n = len(events)
    print(f"wrote {n} events to {OUT}")
    print(f"winners_250k={len(winners)} ({len(winners)/n:.1%})")
    print(f"millions={len(millions)} ({len(millions)/n:.1%})")
    print(f"verticals={sorted(verts)}")
    print(f"source_kinds={sorted(kinds)}")
    print(f"future_leak_events={sum(1 for x in events if 'future_leak' in x)}")
    print(f"hard_gated={sum(1 for x in events if x['asof_snapshot']['hard_gate'])}")
    print(f"human_approved={sum(1 for x in events if x['asof_snapshot'].get('human_approved'))}")


if __name__ == "__main__":
    main()
