from pathlib import Path

p = Path("/workspace/pairfeed/write_board.py")
t = p.read_text()
if "from gate import" not in t:
    t = t.replace("from pathlib import Path\n", "from pathlib import Path\nfrom gate import filter_pairs, write_stream_boards\n")
t = t.replace(
    'rows = [p for p in (data.get("new_pairs") or []) if p.get("mint") != IGNORE]',
    'rows, _ = filter_pairs([p for p in (data.get("new_pairs") or []) if p.get("mint") != IGNORE])',
)
t = t.replace(
    'board_path = Path("/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt")\nboard_path.write_text("\\n".join(lines) + "\\n")',
    'write_stream_boards("\\n".join(lines) + "\\n")',
)
p.write_text(t)
print("write_board")

p = Path("/workspace/pairfeed/sanitize.py")
t = p.read_text()
if "from gate import" not in t:
    t = t.replace("from pathlib import Path\n", "from pathlib import Path\nfrom gate import write_stream_boards\n")
t = t.replace('BOARD.write_text("\\n".join(lines) + "\\n")', 'write_stream_boards("\\n".join(lines) + "\\n")')
p.write_text(t)
print("sanitize")
