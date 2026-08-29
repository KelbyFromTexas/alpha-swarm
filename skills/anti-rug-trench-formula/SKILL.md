---
name: Anti-rug trench formula
description: >-
  use this when scoring pump.fun / new-pair candidates for ALPHA SWARM trench
  buys (filter likely rugs before Risk/Trench)
---
# Anti-rug trench formula

Clinical heuristic for ALPHA SWARM early buys. Not financial advice. Kill rate should stay high. Numbers come from Pair Feed / on-chain reads only — never invent.

## Goal

`survivability` in `[0, 10]`. Prefer high score. **Hard-fail (rug_flag=true) overrides score → do not buy.**

## Hard fails (instant rug_flag)

Any one → reject:

1. Creator sold >70% of initial holdings in first 15 minutes (or creator wallet emptied into sells).
2. Top 1 wallet (ex-bonding curve / known program) holds >35% of supply after create.
3. Same creator minted ≥3 tokens in last 24h that all dumped >80% from peak within 30m (serial rugger).
4. Zero unique buyers after first 2 minutes with nonzero creator sell (bot-only tape).
5. Metadata impersonates a living person / major brand / trademarked character as identity.
6. Name/ticker is a copy of an existing pair with >$25k liq (parasite/sniper-bait) and no new cultural object.
7. Mint authority / freeze authority still held by creator when that applies off bonding curve (post-migrate red flag).
8. Obvious wash: >5 wallets cycling same size buys/sells with net ~0 unique profit-takers.

## Soft score (0–10)

Each component `c_i ∈ [0,10]`. Weights:

- holder_dispersion 0.20
- buy_persistence 0.20
- creator_skin 0.15
- tape_quality 0.15
- metadata_legibility 0.10
- cultural_hook 0.10
- lateness 0.10

`survivability = 10 * Π (c_i/10)^w_i`

## Pass band (shortlist)

- rug_flag == false
- survivability >= 6.5
- Age typically 2–45 minutes
- Not $SWAN house mint

## Output JSON

mint, symbol, rug_flag, hard_fails[], components{}, survivability, recommend advance|kill, notes.

## Join to swarm pass

Anti-rug pass is necessary but not sufficient. Full trench PASS still needs Historian advance, Analyst composite ≥ 6.5, Adversary not block, Risk caps, kill switch off.
