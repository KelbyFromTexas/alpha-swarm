import json
from pathlib import Path
src = json.loads(Path("/workspace/pairfeed/cycle.json").read_text())
pairs = []
for p in src.get("new_pairs") or []:
    pairs.append({
        "mint": p.get("mint"),
        "name": p.get("name"),
        "symbol": p.get("symbol"),
        "creator": p.get("creator"),
        "pump_url": p.get("pump_url"),
        "age_minutes": p.get("age_minutes"),
        "rug_flag": p.get("rug_flag"),
        "hard_fails": p.get("hard_fails") or [],
        "survivability": p.get("survivability"),
        "recommend": p.get("recommend"),
    })
out = {
    "feed_id": src.get("feed_id"),
    "asof": src.get("asof"),
    "new_pairs": pairs,
    "buy_candidate": src.get("buy_candidate"),
    "blockers": (src.get("blockers") or []) + [
        "omitted_counts:{\"slur_hate\":5,\"impersonation_brand\":1,\"private_individual\":1}",
        "survivability uses measured components only (tape/cultural_hook often unmeasured)",
        "board /workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt overwritten",
    ],
}
Path("/workspace/pairfeed/cycle_slim.json").write_text(json.dumps(out, separators=(",", ":")))
print("bytes", Path("/workspace/pairfeed/cycle_slim.json").stat().st_size, "pairs", len(pairs), "buy", (out["buy_candidate"] or {}).get("symbol"))
