#!/usr/bin/python3
"""PumpPortal trade-local buy/sell. CLI args only. Never prints secrets."""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, "/workspace/alpha-venv/lib/python3.13/site-packages")
import requests
from solders.commitment_config import CommitmentLevel
from solders.keypair import Keypair
from solders.rpc.config import RpcSendTransactionConfig
from solders.rpc.requests import SendVersionedTransaction
from solders.transaction import VersionedTransaction

ENV_PATH = Path("/home/box/agent-data/projects/alpha-swarm/.env")
OUT_PATH = Path("/workspace/alpha-swarm-launch/last_trade_result.json")
KILL_ON = Path("/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on")
SLIPPAGE = 15
PRIORITY_FEE = 0.0005
POOL = "pump"


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def load_env():
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def write_result(obj):
    clean = {
        k: v
        for k, v in obj.items()
        if "key" not in k.lower() and "secret" not in k.lower()
    }
    OUT_PATH.write_text(json.dumps(clean, indent=2) + "\n")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("action", choices=["buy", "sell"])
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--mint", required=True)
    ap.add_argument("--sol", type=float, default=0.01)
    ap.add_argument("--pct", type=float, default=30.0, help="sell percent of remaining")
    ap.add_argument("--surv", type=float, default=None)
    ap.add_argument("--entry-mcap", type=float, default=None)
    ap.add_argument("--multiple", type=float, default=None)
    args = ap.parse_args()

    if KILL_ON.exists():
        write_result({"ok": False, "error": "kill-switch.on", "action": args.action})
        print("error kill-switch.on")
        return 1

    env = load_env()
    raw = env.get("SOLANA_PRIVATE_KEY", "")
    if not raw:
        write_result({"ok": False, "error": "SOLANA_PRIVATE_KEY missing", "action": args.action})
        print("error key missing")
        return 1

    rpc = env.get("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"
    wallet = Keypair.from_base58_string(raw)
    del raw
    pub = str(wallet.pubkey())

    if args.action == "buy":
        bal_r = requests.post(
            rpc,
            json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub]},
            timeout=30,
        )
        bal_r.raise_for_status()
        balance_sol = bal_r.json()["result"]["value"] / 1e9
        if balance_sol < args.sol + 0.005:
            write_result(
                {
                    "ok": False,
                    "error": "balance too low",
                    "pubkey": pub,
                    "balance_sol": round(balance_sol, 6),
                    "symbol": args.symbol,
                    "mint": args.mint,
                }
            )
            print("error balance_low", round(balance_sol, 6))
            return 1
        body = {
            "publicKey": pub,
            "action": "buy",
            "mint": args.mint,
            "denominatedInSol": "true",
            "amount": args.sol,
            "slippage": SLIPPAGE,
            "priorityFee": PRIORITY_FEE,
            "pool": POOL,
        }
    else:
        pct = args.pct
        if pct != int(pct):
            amount = f"{pct}%"
        else:
            amount = f"{int(pct)}%"
        body = {
            "publicKey": pub,
            "action": "sell",
            "mint": args.mint,
            "denominatedInSol": "false",
            "amount": amount,
            "slippage": SLIPPAGE,
            "priorityFee": PRIORITY_FEE,
            "pool": POOL,
        }
        balance_sol = None

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
                "error": "trade-local failed",
                "status": local_r.status_code,
                "body_head": local_r.text[:400],
                "pubkey": pub,
                "mint": args.mint,
                "symbol": args.symbol,
                "action": args.action,
            }
        )
        print("error trade-local", local_r.status_code)
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
                "error": "rpc send failed",
                "rpc_error": send_json.get("error"),
                "pubkey": pub,
                "mint": args.mint,
                "symbol": args.symbol,
                "action": args.action,
            }
        )
        print("error rpc_send")
        return 1

    sig = send_json["result"]
    result = {
        "ok": True,
        "action": args.action,
        "symbol": args.symbol,
        "mint": args.mint,
        "signature": sig,
        "sig": sig,
        "pubkey": pub,
        "pump_url": f"https://pump.fun/coin/{args.mint}",
        "solscan_tx": f"https://solscan.io/tx/{sig}",
        "ts": now_iso(),
    }
    if args.action == "buy":
        result["sol"] = args.sol
        result["entry_mcap_sol"] = args.entry_mcap
        result["survivability"] = args.surv
        result["balance_sol_before"] = round(balance_sol, 6) if balance_sol is not None else None
    else:
        result["pct"] = args.pct
        result["multiple"] = args.multiple
    write_result(result)
    print("ok", args.action, args.symbol, "sig", sig)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except SystemExit:
        raise
    except Exception as e:
        write_result({"ok": False, "error": type(e).__name__ + ": " + str(e)[:400]})
        print("error", type(e).__name__)
        raise SystemExit(1)
