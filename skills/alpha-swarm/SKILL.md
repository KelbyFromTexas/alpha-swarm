---
name: ALPHA SWARM
description: >-
  use this when running ALPHA SWARM (Grok-bot trench pipeline: score
  accelerating culture / new pairs, buy early, no default mint)
---
# ALPHA SWARM

Use this when operating ALPHA SWARM: a Grok-bot research + trading pipeline. Primary function is **trenching** — buying early into new pairs (pump.fun / fresh Solana launches) that match accelerating cultural attention. Deploying/minting is NOT the default and requires an explicit one-off ask outside this loop.

## Runtime (this platform)

- Apex is the orchestrator. Specialized Grok bots play Scout, Historian, Analyst, Adversary, Creative, Risk, Launcher (Launcher here means trade executor: buy/sell, not create_token).
- Agents never message each other. Every handoff is Apex-routed and persisted to the audit log.
- State lives on Apex's computer: SQLite + JSONL audit under the alpha-swarm project. Kill switch on → financial tools no-op.
- Venue: pump.fun new pairs / fresh launches when `LAUNCH_MODE=pump.fun`. Caps and size from `.env` (`DEV_BUY_SOL` = default trench size unless Risk sizes smaller).
- **Scout-loop auto-trench (standing order 2026-08-29, replaces auto-deploy):** a full pipeline PASS buys the pair without a second yes. Kill switch, Adversary block, hard gates, and Risk caps still bind. Mint/create is off unless Lord Fishnu explicitly asks for a deploy.
- House coin $SWAN may still exist; creator fees can fund trench size. Do not relaunch SWAN.
- No wash trading, volume faking, fake-organic promotion, announcement sniping-as-impersonation, bundled-buy disguises, or impersonation of a real person/brand.
- X posting is manual: Apex drafts DEFECTOR copy; Lord Fishnu posts on @BLXCKSWANgrok.

## Thesis

Alpha is acceleration/jerk on culture that already (or is about to) mint a pair — not inventing the ticker. Prefer early bonding-curve entries with cultural distance. Window T+30m to T+6h from breakout. Kill rate target >95% of candidates. Avoid chasing already-saturated mcaps.

## Rubric (weighted geometric mean)

composite = Π (score_i / 10) ^ weight_i × 10

acceleration 0.25, earliness 0.20, memeability 0.15, ticker_quality 0.10, narrative_legs 0.10, cultural_distance 0.10, saturation_inverse 0.10.

Hard gates → vetoed: death/disaster/violent crime/tragedy; private individual or minor; trademarked/copyrighted character as identity; slur/hate symbol; pair already >$25k liq with no edge left / too late; impersonation plays.

Kill if composite < 6.5. Adversary severity=block kills.

## Pass → trench (buy)

PASS requires all of: Historian advance; Analyst composite >= 6.5 with no hard-gate veto; Adversary not block; Risk within caps; kill switch off; mint address / pair URL known (or freshly discoverable); `LAUNCH_MODE=pump.fun`.

On PASS: Risk attaches exit template → execute buy (size from Risk/`.env`) → report entry CA/tx/size → draft DEFECTOR disclosure post. If agent-side signing is Auto-review blocked, hand the box for user wallet approve with the trade pack ready. Do not drop a pass. Do NOT create_token.

## Caps

Read `.env` (DEV_BUY_SOL, daily, concurrent, drawdown, wallet). Exit template default: 30% at 2x, 30% at 5x, rest at T+6h. Immutable after attach.

## Loop

Scout (culture accel + new-pair firehose) → aggregate → promote. Historian → Analyst → Adversary → saturation/lateness check → Risk → **auto buy on PASS** → Risk tracks exits. Creative only for outward disclosure copy. Daily retro proposes weight changes; never auto-applies.

## Bus message

{from, to, candidate_id, payload, model, tokens, latency_ms, citations} persisted. Reconstruct any chain from the log.
