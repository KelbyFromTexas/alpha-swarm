#!/usr/bin/python3
import sys
sys.path.insert(0, "/workspace/alpha-venv/lib/python3.13/site-packages")
from pathlib import Path
import requests
from solders.keypair import Keypair

ENV = Path("/home/box/agent-data/projects/alpha-swarm/.env")
env = {}
for line in ENV.read_text().splitlines():
    if not line or line.startswith("#") or "=" not in line:
        continue
    k, v = line.split("=", 1)
    env[k] = v.strip().strip('"').strip("'")

raw = env.get("SOLANA_PRIVATE_KEY", "")
if not raw:
    raise SystemExit("key missing")
kp = Keypair.from_base58_string(raw)
pub = str(kp.pubkey())
print("pubkey", pub)
rpc = env.get("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"
r = requests.post(rpc, json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub]}, timeout=30)
r.raise_for_status()
lamports = r.json()["result"]["value"]
bal = lamports / 1e9
print("balance_sol", round(bal, 6))
print("buy", env.get("DEV_BUY_SOL"))
print("mode", env.get("LAUNCH_MODE"))
need = float(env.get("DEV_BUY_SOL", "0")) + 0.02
print("need_sol", need)
print("enough", bal >= need)
