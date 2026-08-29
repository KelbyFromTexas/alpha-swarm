from pathlib import Path

NEEDLE = '''    missing = [k for k, v in components.items() if v is None]
    if missing:
        notes.append("unmeasured:" + ",".join(missing))
    surv = geo_surv(components)
    rug_flag = bool(hard_fails)
'''
REPL = '''    missing = [k for k, v in components.items() if v is None]
    if missing:
        notes.append("unmeasured:" + ",".join(missing))
    surv = geo_surv(components)
    tape_keys = ("buy_persistence", "tape_quality", "creator_skin")
    all_listed = all(components.get(k) is not None for k in WEIGHTS)
    tape_backed = all(components.get(k) is not None for k in tape_keys)
    if surv is not None and surv >= 10.0 and not (all_listed and tape_backed):
        surv = 9.4
        notes.append("surv_capped_not_fully_tape_backed")
    rug_flag = bool(hard_fails)
'''

for rel in ("cycle_now.py", "run_cycle_score.py"):
    p = Path("/workspace/pairfeed") / rel
    if not p.exists():
        print("skip", rel)
        continue
    t = p.read_text()
    if NEEDLE not in t:
        print("pattern missing", rel)
        continue
    p.write_text(t.replace(NEEDLE, REPL, 1))
    print("patched", rel)
