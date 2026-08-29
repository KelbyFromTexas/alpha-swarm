# ALPHA SWARM — trench desk (Grok Bot)

Autonomous research + micro-trench workflow for pump.fun, orchestrated by Apex (Grok Bot) with specialist agents.

## What this is
- **Primary function:** trench (buy early new pairs), not mint
- **House coin:** $SWAN (documented; do not store keys in this repo)
- **Cadence:** pair scan every 3 minutes; stream asides every 90s
- **Size:** 0.01 SOL micro buys (lenient anti-rug shortlist)
- **Exits:** sell 30% at 2x; flatten if no buys/sells for 5 minutes; flatten if down >30%
- **Caps:** concurrent 3, daily 1 SOL (launch-count caps waived for micros)
- **Outward voice:** DEFECTOR via PostOnce → @BLXCKSWANgrok (draft/publish from bot)

## Layout
- `project/` — SQLite schema, scripts, anti-rug docs, audit layout
- `pairfeed/` — PumpPortal sampling + board writers + slur gate
- `stream-desk/` — livestream Mousepad board helpers / micro trade helpers

## Secrets (NOT in this repo)
Put on the bot machine only:
- `SOLANA_PRIVATE_KEY`
- `PUMPPORTAL_API_KEY`
- RPC URL if non-default

Copy from `.env.example` in `project/`.

## Hard rules
- Never navigate away from a shared pump.fun livestream tab
- Hard-filter hate-slur tickers from on-screen boards
- No private keys in chat or git
