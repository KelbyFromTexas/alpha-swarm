#!/usr/bin/env python3
"""3m cycle using .env.score only (no private key). Never print secrets."""
from pathlib import Path
import sys
sys.path.insert(0, "/workspace/pairfeed")
import cycle_3m
cycle_3m.ENV_PATH = Path("/workspace/pairfeed/.env.score")
if __name__ == "__main__":
    cycle_3m.main()
