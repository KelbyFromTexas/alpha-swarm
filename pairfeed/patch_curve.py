from pathlib import Path
p = Path("/workspace/pairfeed/cycle_now.py")
t = p.read_text()
a = "    rows.sort(reverse=True)\n    return rows[0] / total\n"
b = (
    "    rows.sort(reverse=True)\n"
    "    rest = rows[1:] if len(rows) > 1 else []\n"
    "    if not rest:\n"
    "        return 0.0\n"
    "    return rest[0] / total\n"
)
if a not in t:
    raise SystemExit("pattern missing")
p.write_text(t.replace(a, b, 1))
print("patched")
