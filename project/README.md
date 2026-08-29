# ALPHA SWARM store

Local swarm store for Grok bots. Not a Bun service. Not a launcher.

This directory holds the paper-trading signal/candidate/outcome sqlite, JSONL
bus logs, and backtest corpus. Bots read and write here. There is no HTTP
server, no Solana client, and no live mint path in this tree.

## Backtest (must pass before any paper loop)

The harness is a local deterministic pipeline. Fixture scores in the corpus
are **not** live Grok calls — they are frozen analyst/adversary fixtures so
the backtest can run without LLM keys.

```bash
python3 /home/box/agent-data/projects/alpha-swarm/scripts/test_backtest.py \
  && python3 /home/box/agent-data/projects/alpha-swarm/scripts/harness.py
```

- Tests: composite annihilation, leakage-proof clock, hard gates, uncited
  scout discard, adversary as a separate step, kill-switch, human gate,
  paper-only venue, corpus mix.
- Harness: walks `data/corpus/events.jsonl` using only `asof_snapshot` at
  `decision_at` (enforced by `scripts/clock.py`). Writes metrics to
  `data/corpus/last_backtest.json`.
- Composite formula is imported from `scripts/composite.py`. Do not
  reimplement it.
- `launch_ready` is pre-human (the swarm would have launched if the human
  said yes). `would_launch` is post-human. Primary metrics use `launch_ready`.

Do not start a scout loop, do not touch Solana, private keys, live launch,
or external APIs until this backtest is green.

## Inspect sqlite

```bash
sqlite3 /home/box/agent-data/projects/alpha-swarm/data/alpha-swarm.sqlite
.tables
.schema
SELECT * FROM signals ORDER BY observed_at DESC LIMIT 20;
```

Canonical DDL lives in `schema.sql` and has already been applied to the db.

## Kill-switch

- `data/kill-switch.off` — financial tools may run (paper only).
- `data/kill-switch.on`  — financial tools MUST halt. Presence of this file
  is the halt signal; do not rely on process state.

## Paper only

All launches and PnL in this store are paper. Assume the swarm loses money.
Get a lawyer before real money. Do not wire private keys, RPC, or live
launch code to this store.
