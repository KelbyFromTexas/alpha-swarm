#!/usr/bin/python3
"""One-shot PumpPortal trade-local BUY 0.01 SOL of Rirai. Never prints secrets."""
import json
import sys
from pathlib import Path

sys.path.insert(0, "/workspace/alpha-venv/lib/python3.13/site-packages")
import requests
from solders.commitment_config import CommitmentLevel
from solders.keypair import Keypair
from solders.rpc.config import RpcSendTransactionConfig
from solders.rpc.requests import SendVersionedTransaction
from solders.transaction import VersionedTransaction

ENV_PATH = Path("/home/box/agent-data/projects/alpha-swarm/.env")
OUT_PATH = Path("/workspace/alpha-swarm-launch/last_buy_result.json")
KILL_ON = Path("/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on")

MINT = "47wdXao2wRWB1QXcoLpoUUty3kNutCYvYkfoCp2Ppump"
SYMBOL = "Rirai"
BUY_SOL = 0.01
SLIPPAGE = 15
PRIORITY_FEE = 0.0005
POOL = "pump"
ENTRY_MCAP_SOL = 27.96
NEED_SOL = 0.015  # buy + priority + rent/fees buffer


def load_env():
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k] = v.strip().strip('"').strip("'")
    return env


def write_result(obj):
    clean = {
        k: v
        for k, v in obj.items()
        if k.lower() not in ("private_key", "secret", "secret_key", "solana_private_key")
    }
    OUT_PATH.write_text(json.dumps(clean, indent=2) + "\n")


def main():
    if KILL_ON.exists():
        write_result({"ok": False, "symbol": SYMBOL, "mint": MINT, "sol": BUY_SOL, "error": "kill-switch.on present; halt"})
        print("error kill-switch.on present")
        return 1

    env = load_env()
    raw = env.get("SOLANA_PRIVATE_KEY", "")
    if not raw:
        write_result({"ok": False, "symbol": SYMBOL, "mint": MINT, "sol": BUY_SOL, "error": "SOLANA_PRIVATE_KEY missing"})
        print("error key missing")
        return 1

    rpc = env.get("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"
    wallet = Keypair.from_base58_string(raw)
    del raw
    pub = str(wallet.pubkey())
    print("pubkey", pub)

    bal_r = requests.post(
        rpc,
        json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub]},
        timeout=30,
    )
    bal_r.raise_for_status()
    lamports = bal_r.json()["result"]["value"]
    balance_sol = lamports / 1e9
    print("balance_sol", round(balance_sol, 6))
    if balance_sol < NEED_SOL:
        write_result(
            {
                "ok": False,
                "symbol": SYMBOL,
                "mint": MINT,
                "sol": BUY_SOL,
                "error": "balance too low; not sent",
                "pubkey": pub,
                "balance_sol": round(balance_sol, 6),
                "need_sol": NEED_SOL,
            }
        )
        print("error balance too low")
        return 1

    body = {
        "publicKey": pub,
        "action": "buy",
        "mint": MINT,
        "denominatedInSol": "true",
        "amount": BUY_SOL,
        "slippage": SLIPPAGE,
        "priorityFee": PRIORITY_FEE,
        "pool": POOL,
    }
    local_r = requests.post(
        "https://pumpportal.fun/api/trade-local",
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if local_r.status_code != 200:
        write_result(
            {
                "ok": False,
                "symbol": SYMBOL,
                "mint": MINT,
                "sol": BUY_SOL,
                "error": "trade-local failed",
                "status": local_r.status_code,
                "body_head": local_r.text[:500],
                "pubkey": pub,
                "balance_sol": round(balance_sol, 6),
            }
        )
        print("error trade-local", local_r.status_code, local_r.text[:300])
        return 1

    tx = VersionedTransaction(
        VersionedTransaction.from_bytes(local_r.content).message,
        [wallet],
    )
    config = RpcSendTransactionConfig(
        skip_preflight=True,
        preflight_commitment=CommitmentLevel.Confirmed,
    )
    send_r = requests.post(
        rpc,
        headers={"Content-Type": "application/json"},
        data=SendVersionedTransaction(tx, config).to_json(),
        timeout=60,
    )
    send_json = send_r.json()
    if "error" in send_json or not send_json.get("result"):
        write_result(
            {
                "ok": False,
                "symbol": SYMBOL,
                "mint": MINT,
                "sol": BUY_SOL,
                "error": "rpc send failed",
                "rpc_error": send_json.get("error"),
                "pubkey": pub,
                "balance_sol": round(balance_sol, 6),
            }
        )
        print("error rpc send", json.dumps(send_json.get("error"))[:400])
        return 1

    sig = send_json["result"]
    write_result(
        {
            "ok": True,
            "symbol": SYMBOL,
            "mint": MINT,
            "signature": sig,
            "sig": sig,
            "sol": BUY_SOL,
            "entry_mcap_sol": ENTRY_MCAP_SOL,
            "pubkey": pub,
            "slippage": SLIPPAGE,
            "priorityFee": PRIORITY_FEE,
            "pool": POOL,
            "balance_sol_before": round(balance_sol, 6),
            "solscan_tx": f"https://solscan.io/tx/{sig}",
            "pump_url": f"https://pump.fun/{MINT}",
        }
    )
    print("signature", sig)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        write_result({"ok": False, "symbol": SYMBOL, "mint": MINT, "sol": BUY_SOL, "error": type(e).__name__ + ": " + str(e)[:400]})
        print("error", type(e).__name__, str(e)[:400])
        raise SystemExit(1)
