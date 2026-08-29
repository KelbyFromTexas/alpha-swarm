from pathlib import Path
from gate import write_stream_boards, rescrub_on_disk, SLUR_RE

r = rescrub_on_disk()
board = Path("/workspace/alpha-swarm-launch/PAIR_FEED_BOARD.txt")
body = board.read_text(encoding="utf-8", errors="replace") if board.exists() else "PAIR FEED — live\nasof: pending\ncount: 0\n"
info = write_stream_boards(body)
hits = []
for p in [board, Path("/workspace/alpha-swarm-launch/SCORED_PAIRS.txt")]:
    t = p.read_text(encoding="utf-8", errors="replace")
    hits.append((p.name, bool(SLUR_RE.search(t)), p.stat().st_size))
print({"rescrub": r, "write": info, "hits": hits})
