#!/usr/bin/python3
"""Micro trench buy via PumpPortal trade-local. Never prints secrets."""
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
OUT_PATH = Path("/workspace/alpha-swarm-launch/last_buy_result.json")
KILL_ON = Path("/home/box/agent-data/projects/alpha-swarm/data/kill-switch.on")
TALLY_JSONL = Path("/home/box/agent-data/projects/alpha-swarm/data/tally.jsonl")
TALLY_BOARD = Path("/workspace/alpha-swarm-launch/TALLY_BOARD.txt")

SYMBOL = "HighCap"
MINT = "FUWe4AhgKWXNhGFKtEicbJ5TFx27jLuqjqCvwBWgpump"
BUY_SOL = 0.01
SLIPPAGE = 15
PRIORITY_FEE = 0.0005
ENTRY_MCAP = 31.811121466293816
SURV = 7.56


def load_env():
    env = {}
    for line in ENV_PATH.read_text().splitlines():
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def write_result(obj):
    clean = {k: v for k, v in obj.items() if "key" not in k.lower() and "secret" not in k.lower()}
    OUT_PATH.write_text(json.dumps(clean, indent=2) + "\n")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def append_tally(obj):
    with TALLY_JSONL.open("a") as f:
        f.write(json.dumps(obj) + "\n")


def update_board(filled, sig=None, error=None):
    buys, spent, open_n = 0, 0.0, 0
    if TALLY_BOARD.exists():
        for line in TALLY_BOARD.read_text().splitlines():
            if line.startswith("buys:"):
                try:
                    buys = int(line.split(":", 1)[1].strip())
                except Exception:
                    pass
            if line.startswith("sol_spent:"):
                try:
                    spent = float(line.split(":", 1)[1].strip())
                except Exception:
                    pass
            if line.startswith("open:"):
                try:
                    open_n = int(line.split(":", 1)[1].strip().split()[0])
                except Exception:
                    pass
    asof = now_iso()
    if filled:
        buys += 1
        spent = round(spent + BUY_SOL, 4)
        open_n += 1
        last = f"last_action: BUY {SYMBOL} 0.01 SOL surv={SURV} sig={(sig or '')[:16]}…"
        open_row = f"OPEN {SYMBOL} mint={MINT[:6]}…{MINT[-4:]} entry_mcap_sol={ENTRY_MCAP:.2f} multiple=1.00x remaining=100%"
    else:
        last = f"last_action: BUY_FAILED {SYMBOL} err={error}"
        open_row = "(no fills yet)" if buys == 0 else ""
    lines = [
        "TALLY — micro trenches (0.01 SOL) LENIENT",
        f"asof: {asof}",
        f"buys: {buys}",
        f"sol_spent: {spent:.2f}",
        f"open: {open_n}",
        "",
        last,
        "rule: every 3m try BUY one (surv>=5 or best non-hard-fail); 2x sell 30%",
        "caps: concurrent 3, daily 1 SOL",
        "",
        open_row,
        "Kill rate is the product.",
        "",
    ]
    TALLY_BOARD.write_text("\n".join(lines))


def main():
    if KILL_ON.exists():
        write_result({"ok": False, "error": "kill-switch.on"})
        print("error kill-switch.on")
        return 1

    env = load_env()
    raw = env.get("SOLANA_PRIVATE_KEY", "")
    if not raw:
        write_result({"ok": False, "error": "SOLANA_PRIVATE_KEY missing"})
        print("error key missing")
        return 1

    rpc = env.get("SOLANA_RPC_URL") or "https://api.mainnet-beta.solana.com"
    wallet = Keypair.from_base58_string(raw)
    del raw
    pub = str(wallet.pubkey())

    bal_r = requests.post(
        rpc,
        json={"jsonrpc": "2.0", "id": 1, "method": "getBalance", "params": [pub]},
        timeout=30,
    )
    bal_r.raise_for_status()
    balance_sol = bal_r.json()["result"]["value"] / 1e9
    if balance_sol < BUY_SOL + 0.005:
        write_result({
            "ok": False,
            "error": "balance too low",
            "pubkey": pub,
            "balance_sol": round(balance_sol, 6),
            "need_sol": BUY_SOL + 0.005,
        })
        print("error balance_low", round(balance_sol, 6))
        update_board(False, error="balance_low")
        append_tally({
            "ts": now_iso(), "action": "buy", "symbol": SYMBOL, "mint": MINT,
            "sol": BUY_SOL, "survivability": SURV, "status": "failed", "error": "balance_low",
            "entry_mcap_sol": ENTRY_MCAP,
        })
        return 1

    body = {
        "publicKey": pub,
        "action": "buy",
        "mint": MINT,
        "denominatedInSol": "true",
        "amount": BUY_SOL,
        "slippage": SLIPPAGE,
        "priorityFee": PRIORITY_FEE,
        "pool": "pump",
    }
    local_r = requests.post(
        "https://pumpportal.fun/api/trade-local",
        headers={"Content-Type": "application/json"},
        json=body,
        timeout=60,
    )
    if local_r.status_code != 200:
        err = f"trade-local {local_r.status_code}"
        write_result({
            "ok": False,
            "error": "trade-local failed",
            "status": local_r.status_code,
            "body_head": local_r.text[:400],
            "pubkey": pub,
            "mint": MINT,
            "symbol": SYMBOL,
            "sol": BUY_SOL,
        })
        print("error", err)
        update_board(False, error=err)
        append_tally({
            "ts": now_iso(), "action": "buy", "symbol": SYMBOL, "mint": MINT,
            "sol": BUY_SOL, "survivability": SURV, "status": "failed", "error": err,
            "entry_mcap_sol": ENTRY_MCAP,
        })
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
        write_result({
            "ok": False,
            "error": "rpc send failed",
            "rpc_error": send_json.get("error"),
            "pubkey": pub,
            "mint": MINT,
            "symbol": SYMBOL,
            "sol": BUY_SOL,
        })
        print("error rpc_send")
        update_board(False, error="rpc_send")
        append_tally({
            "ts": now_iso(), "action": "buy", "symbol": SYMBOL, "mint": MINT,
            "sol": BUY_SOL, "survivability": SURV, "status": "failed", "error": "rpc_send",
            "entry_mcap_sol": ENTRY_MCAP,
        })
        return 1

    sig = send_json["result"]
    write_result({
        "ok": True,
        "symbol": SYMBOL,
        "mint": MINT,
        "signature": sig,
        "sol": BUY_SOL,
        "entry_mcap_sol": ENTRY_MCAP,
        "survivability": SURV,
        "pubkey": pub,
        "pump_url": f"https://pump.fun/coin/{MINT}",
        "solscan_tx": f"https://solscan.io/tx/{sig}",
        "balance_sol_before": round(balance_sol, 6),
    })
    update_board(True, sig=sig)
    append_tally({
        "ts": now_iso(), "action": "buy", "symbol": SYMBOL, "mint": MINT,
        "sol": BUY_SOL, "survivability": SURV, "sig": sig, "status": "filled",
        "entry_mcap_sol": ENTRY_MCAP, "side": "buy",
    })
    print("ok", SYMBOL, "sig", sig)
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
