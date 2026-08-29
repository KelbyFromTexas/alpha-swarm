# Anti-rug trench formula

Clinical heuristic for ALPHA SWARM early buys. Not financial advice.

## Hard fails (rug_flag=true → do not buy)
1. Creator sold >70% of initial holdings in first 15m
2. Top wallet (ex curve) >35% supply
3. Serial rugger: ≥3 creator dumps >80% in 30m within 24h
4. Bot-only tape: 0 unique buyers in 2m + creator sell
5. Impersonation / trademark identity
6. Parasite copy of existing >$25k liq pair
7. Freeze/mint authority still with creator post-migrate
8. Wash cycling (>5 wallets, same size, net ~0)

## Soft score
survivability = 10 * Π (c_i/10)^w_i
- holder_dispersion 0.20
- buy_persistence 0.20
- creator_skin 0.15
- tape_quality 0.15
- metadata_legibility 0.10
- cultural_hook 0.10
- lateness 0.10

## Shortlist
rug_flag=false AND survivability>=6.5 AND age ~2–45m; then full swarm PASS still required.
