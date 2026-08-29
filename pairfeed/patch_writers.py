from pathlib import Path

# --- collect_pair_feed.py ---
p = Path("/workspace/collect_pair_feed.py")
t = p.read_text()
if "from pairfeed.gate import" not in t and "import gate" not in t:
    t = t.replace(
        "BOARD_PATH = Path(\"/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt\")",
        "import sys\n"
        "sys.path.insert(0, \"/workspace\")\n"
        "from pairfeed.gate import filter_pairs, write_stream_boards\n"
        "BOARD_PATH = Path(\"/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt\")",
    )
old = '''def write_outputs(asof: str, events: list[dict], blockers: list[str]) -> None:
    board = render_board(asof, events)
    if blockers:
        board = board.rstrip() + "\\n\\nblockers:\\n" + "\\n".join(f"- {b}" for b in blockers) + "\\n"
    BOARD_PATH.write_text(board, encoding="utf-8")
'''
new = '''def write_outputs(asof: str, events: list[dict], blockers: list[str]) -> None:
    events, omitted = filter_pairs(events)
    if omitted:
        blockers = list(blockers) + ["omitted_counts:" + str(omitted)]
    board = render_board(asof, events)
    if blockers:
        board = board.rstrip() + "\\n\\nblockers:\\n" + "\\n".join(f"- {b}" for b in blockers) + "\\n"
    write_stream_boards(board)
'''
if old not in t:
    raise SystemExit("collect write_outputs pattern missing")
p.write_text(t.replace(old, new, 1))
print("patched collect_pair_feed")

# --- gate_inflated_buy.py ---
p = Path("/workspace/pairfeed/gate_inflated_buy.py")
t = p.read_text()
if "from gate import" not in t:
    t = t.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\nfrom gate import filter_pairs, write_stream_boards\n",
    )
t = t.replace("pairs = d.get(\"new_pairs\") or []", "pairs, _omit = filter_pairs(d.get(\"new_pairs\") or [])", 1)
old = '''board_body = "\\n".join(lines) + "\\n"
(LAUNCH / "PAIR_FEED_BOARD.txt").write_text(board_body)
(LAUNCH / "SCORED_PAIRS.txt").write_text(
    "SCORED PAIRS — third editor (refreshes every 3m)\\n\\n" + board_body
)
'''
new = '''board_body = "\\n".join(lines) + "\\n"
write_stream_boards(board_body)
'''
if old not in t:
    raise SystemExit("gate_inflated_buy write pattern missing")
p.write_text(t.replace(old, new, 1))
print("patched gate_inflated_buy")

# --- cycle_now.py ---
p = Path("/workspace/pairfeed/cycle_now.py")
t = p.read_text()
if "from gate import" not in t:
    t = t.replace(
        "from pathlib import Path\n",
        "from pathlib import Path\nfrom gate import write_stream_boards, filter_pairs\n",
    )
t = t.replace("BOARD.write_text(", "write_stream_boards(", 1)
# second write_text at end of scoring
# replace remaining BOARD.write_text("\\n".join(lines) + "\\n")
t = t.replace(
    '    BOARD.write_text("\\n".join(lines) + "\\n")\n',
    '    write_stream_boards("\\n".join(lines) + "\\n")\n',
)
p.write_text(t)
print("patched cycle_now, remaining BOARD.write", t.count("BOARD.write_text"))

# --- topup.py ---
p = Path("/workspace/pairfeed/topup.py")
t = p.read_text()
if "from gate import" not in t:
    t = t.replace("from pathlib import Path\n", "from pathlib import Path\nfrom gate import filter_pairs, write_stream_boards, blocked_reason\n")
# make write_board use write_stream_boards
t = t.replace("BOARD.write_text(\"\\n\".join(lines) + \"\\n\")", "write_stream_boards(\"\\n\".join(lines) + \"\\n\")")
# filter JSON pairs
old = '''        "new_pairs": [
            {
                "mint": p["mint"],
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "creator": p.get("creator"),
                "pump_url": p.get("pump_url"),
            }
            for p in pairs[:MAX_PAIRS]
        ],'''
new = '''        "new_pairs": [
            {
                "mint": p["mint"],
                "name": p.get("name"),
                "symbol": p.get("symbol"),
                "creator": p.get("creator"),
                "pump_url": p.get("pump_url"),
            }
            for p in filter_pairs(pairs[:MAX_PAIRS])[0]
        ],'''
if old in t:
    t = t.replace(old, new, 1)
p.write_text(t)
print("patched topup")

print("done")
