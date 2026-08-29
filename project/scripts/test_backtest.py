#!/usr/bin/env python3
"""Unit tests for ALPHA SWARM backtest primitives. Must PASS before paper loop."""

from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent
ROOT = SCRIPTS.parent
sys.path.insert(0, str(SCRIPTS))

from clock import LeakageError, search  # noqa: E402
from composite import WEIGHTS, composite  # noqa: E402
from harness import evaluate_event, load_events  # noqa: E402
from policy import PolicyDenied, create_token, sell_position  # noqa: E402
import policy as policy_mod  # noqa: E402

CORPUS = ROOT / "data" / "corpus" / "events.jsonl"

OK_CHAIN = {
    "analyst": True,
    "adversary": "pass",
    "risk": True,
    "human": True,
}


def _base_event(**over) -> dict:
    snap = {
        "fixture_signals": {
            "volume_now": 1000,
            "volume_prior": 10,
            "accel_estimate": 5.0,
            "citations": [
                {"ref": "a", "timestamp": "2024-06-01T12:10:00Z"},
                {"ref": "b", "timestamp": "2024-06-01T12:12:00Z"},
            ],
        },
        "hard_gate": None,
        "analyst_fixture_scores": {k: 8.0 for k in WEIGHTS},
        "adversary_fixture": {"severity": "pass", "reasons": []},
        "human_approved": False,
    }
    ev = {
        "id": "test-001",
        "topic_key": "test",
        "raw_term": "test",
        "vertical": "internet-native",
        "breakout_at": "2024-06-01T12:00:00Z",
        "decision_at": "2024-06-01T12:30:00Z",
        "crypto_native": False,
        "source_kind": "synthetic_near_miss",
        "outcome": {
            "spawned_token": False,
            "peak_mcap_usd": None,
            "duration_hours": None,
            "verdict": "never_launched",
        },
        "asof_snapshot": snap,
    }
    for k, v in over.items():
        if k == "asof_snapshot" and isinstance(v, dict):
            snap.update(v)
        else:
            ev[k] = v
    return ev


class CompositeImportTests(unittest.TestCase):
    def test_all_tens_is_ten(self):
        self.assertAlmostEqual(composite({k: 10.0 for k in WEIGHTS}), 10.0, places=12)

    def test_any_zero_annihilates(self):
        for dim in WEIGHTS:
            s = {k: 10.0 for k in WEIGHTS}
            s[dim] = 0.0
            self.assertEqual(composite(s), 0.0, msg=dim)


class ClockTests(unittest.TestCase):
    def test_future_leak_raises(self):
        as_of = "2024-10-10T12:00:00Z"
        rec = {
            "kind": "future_leak",
            "timestamp": "2024-10-10T18:00:00Z",
            "text": "post after decision",
        }
        with self.assertRaises(LeakageError):
            search(as_of, [rec])

    def test_future_leak_flag_raises(self):
        as_of = "2024-10-10T12:00:00Z"
        rec = {
            "future_leak": True,
            "timestamp": "2024-10-11T00:00:00Z",
            "text": "later token print",
        }
        with self.assertRaises(LeakageError):
            search(as_of, [rec])

    def test_clips_unstamped_future_plain_records(self):
        as_of = "2024-10-10T12:00:00Z"
        past = {"timestamp": "2024-10-10T11:00:00Z", "text": "ok"}
        future = {"timestamp": "2024-10-10T13:00:00Z", "text": "too late"}
        kept = search(as_of, [past, future])
        self.assertEqual(len(kept), 1)
        self.assertEqual(kept[0]["text"], "ok")

    def test_empty_when_only_future_plain(self):
        as_of = "2024-01-01T00:00:00Z"
        future = {"timestamp": "2024-01-02T00:00:00Z", "text": "later"}
        kept = search(as_of, [future])
        self.assertEqual(kept, [])


class GateTests(unittest.TestCase):
    def test_hard_gates_kill_without_scoring(self):
        for gate in ("tragedy", "minor", "trademark", "slur", "saturated"):
            ev = _base_event(asof_snapshot={"hard_gate": gate})
            r = evaluate_event(ev)
            self.assertEqual(r["status"], "vetoed_gate", msg=gate)
            self.assertIsNone(r["composite"], msg=gate)
            self.assertFalse(r["analyzed"], msg=gate)
            self.assertFalse(r["launch_ready"], msg=gate)
            self.assertTrue(r["surfaced"], msg=gate)

    def test_uncited_scout_discarded(self):
        ev = _base_event(
            asof_snapshot={
                "fixture_signals": {
                    "volume_now": 10,
                    "volume_prior": 1,
                    "accel_estimate": 1,
                    "citations": [{"ref": "only-one", "timestamp": "2024-06-01T12:10:00Z"}],
                }
            }
        )
        r = evaluate_event(ev)
        self.assertEqual(r["status"], "discarded_uncited")
        self.assertFalse(r["surfaced"])
        self.assertFalse(r["launch_ready"])
        self.assertIsNone(r["composite"])

    def test_empty_citations_discarded(self):
        ev = _base_event(
            asof_snapshot={
                "fixture_signals": {
                    "volume_now": 10,
                    "volume_prior": 1,
                    "accel_estimate": 1,
                    "citations": [],
                }
            }
        )
        r = evaluate_event(ev)
        self.assertEqual(r["status"], "discarded_uncited")

    def test_missing_adversary_does_not_launch(self):
        ev = _base_event()
        ev["asof_snapshot"]["adversary_fixture"] = None
        r = evaluate_event(ev)
        self.assertFalse(r["launch_ready"])
        self.assertEqual(r["status"], "vetoed_no_adversary")
        self.assertTrue(r["analyzed"])
        self.assertIsNotNone(r["composite"])
        self.assertGreaterEqual(r["composite"], 6.5)

    def test_adversary_is_separate_step_after_analyst(self):
        # Composite computed even when adversary later blocks.
        ev = _base_event(
            asof_snapshot={"adversary_fixture": {"severity": "block", "reasons": ["x"]}}
        )
        r = evaluate_event(ev)
        self.assertTrue(r["analyzed"])
        self.assertIsNotNone(r["composite"])
        self.assertTrue(r["adversary_blocked"])
        self.assertFalse(r["launch_ready"])
        self.assertEqual(r["status"], "vetoed_adversary")


class PolicyTests(unittest.TestCase):
    def test_kill_switch_blocks_create_token(self):
        ks = Path(policy_mod.KILL_SWITCH_ON)
        self.assertFalse(ks.exists(), "kill-switch.on must not be left engaged")
        try:
            ks.write_text("halt\n", encoding="utf-8")
            with self.assertRaises(PolicyDenied):
                create_token(
                    venue="paper",
                    human_approved=True,
                    size_sol=0.05,
                    approval_chain=OK_CHAIN,
                )
        finally:
            if ks.exists():
                ks.unlink()
        self.assertFalse(ks.exists())

    def test_human_gate_required(self):
        with self.assertRaises(PolicyDenied):
            create_token(
                venue="paper",
                human_approved=False,
                size_sol=0.05,
                approval_chain=OK_CHAIN,
            )
        chain = dict(OK_CHAIN)
        chain["human"] = False
        with self.assertRaises(PolicyDenied):
            create_token(
                venue="paper",
                human_approved=True,
                size_sol=0.05,
                approval_chain=chain,
            )

    def test_non_paper_venue_denied(self):
        with self.assertRaises(PolicyDenied):
            create_token(
                venue="live",
                human_approved=True,
                size_sol=0.05,
                approval_chain=OK_CHAIN,
            )
        with self.assertRaises(PolicyDenied):
            sell_position(
                venue="mainnet",
                human_approved=True,
                size_sol=0.05,
                approval_chain=OK_CHAIN,
            )

    def test_paper_happy_path(self):
        out = create_token(
            venue="paper",
            human_approved=True,
            size_sol=0.05,
            approval_chain=OK_CHAIN,
        )
        self.assertTrue(out["ok"])
        out2 = sell_position(
            venue="paper",
            human_approved=True,
            size_sol=0.05,
            approval_chain=OK_CHAIN,
        )
        self.assertTrue(out2["ok"])


class CorpusTests(unittest.TestCase):
    def test_corpus_size_and_mix(self):
        self.assertTrue(CORPUS.exists(), f"missing {CORPUS}")
        events = load_events(CORPUS)
        self.assertGreaterEqual(len(events), 100)
        winners = [
            e for e in events
            if (e.get("outcome") or {}).get("peak_mcap_usd") is not None
            and float(e["outcome"]["peak_mcap_usd"]) >= 250000
        ]
        duds = [
            e for e in events
            if (e.get("outcome") or {}).get("verdict")
            in ("dud", "never_launched", "flat", "rugged_by_market")
            and not (
                (e.get("outcome") or {}).get("peak_mcap_usd") is not None
                and float(e["outcome"]["peak_mcap_usd"]) >= 250000
            )
        ]
        self.assertGreater(len(winners), 0, "corpus of only duds/no winners is invalid")
        self.assertGreater(len(duds), 0, "corpus of only winners is a failed deliverable")
        verts = {e["vertical"] for e in events}
        self.assertEqual(
            verts,
            {
                "sports",
                "politics-and-courts",
                "music-and-celebrity",
                "gaming-and-anime",
                "tech-and-ai",
                "internet-native",
            },
        )
        kinds = {e["source_kind"] for e in events}
        self.assertTrue(kinds <= {"public_record", "synthetic_dud", "synthetic_near_miss"})
        self.assertIn("public_record", kinds)
        for e in events:
            self.assertLess(e["breakout_at"], e["decision_at"], msg=e["id"])
            snap = e["asof_snapshot"]
            self.assertIn("fixture_signals", snap)
            self.assertIn("analyst_fixture_scores", snap)
            self.assertIn("adversary_fixture", snap)


if __name__ == "__main__":
    unittest.main(verbosity=2)
