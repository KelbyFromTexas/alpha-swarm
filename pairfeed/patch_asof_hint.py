from pathlib import Path
p = Path("/workspace/pairfeed/cycle_3m.py")
t = p.read_text()
old = "    asof = now_iso()\n    prefix = f\"SCORED PAIRS — cycle {asof} (every 3m)\\n\\n\"\n"
new = "    asof = now_iso()\n    if buy_candidate and isinstance(buy_candidate.get(\"entry_hints\"), dict):\n        buy_candidate[\"entry_hints\"][\"asof_sample\"] = asof\n    prefix = f\"SCORED PAIRS — cycle {asof} (every 3m)\\n\\n\"\n"
if old not in t:
    raise SystemExit("asof block missing")
p.write_text(t.replace(old, new, 1))
print("patched")
