# Backtest corpus

`events.jsonl` holds 100+ dated trends with winners AND duds.

Each line is one fixture: signal history visible at `decision_at`, frozen
analyst/adversary scores, and a known outcome. Fixture scores are not live
Grok calls.

- `source_kind=public_record` — real cultural/memecoin events with honest
  approximate dates (and approximate measured mcaps where known).
- `source_kind=synthetic_dud` / `synthetic_near_miss` — labeled synthetic;
  `peak_mcap_usd` is null so we never pretend a made-up mcap was measured.

Regenerate (optional):

```bash
python3 /home/box/agent-data/projects/alpha-swarm/scripts/gen_corpus.py
```

Run the harness:

```bash
python3 /home/box/agent-data/projects/alpha-swarm/scripts/test_backtest.py \
  && python3 /home/box/agent-data/projects/alpha-swarm/scripts/harness.py
```

This must pass before any paper loop.
