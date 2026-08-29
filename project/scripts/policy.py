#!/usr/bin/env python3
"""Paper-only policy layer for ALPHA SWARM.

create_token / sell_position succeed only when every gate is green:
kill-switch.off (kill-switch.on absent), venue==paper, human_approved,
approval chain complete, and size/daily/concurrent caps.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional


PROJECT_ROOT = Path("/home/box/agent-data/projects/alpha-swarm")
DATA_DIR = PROJECT_ROOT / "data"
KILL_SWITCH_ON = DATA_DIR / "kill-switch.on"

SIZE_SOL_CAP = 0.1
DAILY_DEPLOYED_CAP = 1.0
CONCURRENT_CAP = 3


class PolicyDenied(Exception):
    """Raised when a financial action is blocked by policy."""


def kill_switch_engaged() -> bool:
    return KILL_SWITCH_ON.exists()


def _as_chain(approval_chain: Optional[dict[str, Any]]) -> dict[str, Any]:
    return dict(approval_chain or {})


def _adversary_severity(chain: dict[str, Any]) -> str:
    if "adversary_severity" in chain:
        return str(chain.get("adversary_severity") or "")
    adv = chain.get("adversary")
    if isinstance(adv, dict):
        return str(adv.get("severity") or "")
    if isinstance(adv, str):
        return adv
    return ""


def _check_gates(
    *,
    venue: str,
    human_approved: bool,
    size_sol: float,
    approval_chain: Optional[dict[str, Any]],
    daily_deployed: float,
    concurrent: int,
    action: str,
) -> None:
    if kill_switch_engaged():
        raise PolicyDenied("kill-switch.on present; all financial tools halted")
    if venue != "paper":
        raise PolicyDenied(f"venue must be paper, got {venue!r}")
    if human_approved is not True:
        raise PolicyDenied("human gate required")
    chain = _as_chain(approval_chain)
    if not chain:
        raise PolicyDenied("approval chain missing")
    analyst_ok = bool(chain.get("analyst") or chain.get("analyst_approved"))
    if not analyst_ok:
        raise PolicyDenied("analyst approval missing")
    sev = _adversary_severity(chain)
    if sev == "block":
        raise PolicyDenied("adversary block")
    if sev not in ("pass", "warn"):
        raise PolicyDenied("adversary not clear (need pass or warn)")
    risk_ok = bool(chain.get("risk") or chain.get("risk_approved"))
    if not risk_ok:
        raise PolicyDenied("risk not approved")
    human_chain = chain.get("human")
    if human_chain is None:
        human_chain = chain.get("human_approved")
    if human_chain is not True:
        raise PolicyDenied("human gate missing from approval chain")
    if size_sol > SIZE_SOL_CAP:
        raise PolicyDenied(f"size_sol {size_sol} exceeds cap {SIZE_SOL_CAP}")
    if daily_deployed + size_sol > DAILY_DEPLOYED_CAP:
        raise PolicyDenied(
            f"daily deployed {daily_deployed}+{size_sol} exceeds cap {DAILY_DEPLOYED_CAP}"
        )
    if concurrent >= CONCURRENT_CAP:
        raise PolicyDenied(f"concurrent {concurrent} exceeds cap {CONCURRENT_CAP - 1}")


def create_token(
    *,
    venue: str = "paper",
    human_approved: bool = False,
    size_sol: float = 0.05,
    approval_chain: Optional[dict[str, Any]] = None,
    daily_deployed: float = 0.0,
    concurrent: int = 0,
    ticker: str = "PAPER",
    **_extra: Any,
) -> dict[str, Any]:
    _check_gates(
        venue=venue,
        human_approved=human_approved,
        size_sol=size_sol,
        approval_chain=approval_chain,
        daily_deployed=daily_deployed,
        concurrent=concurrent,
        action="create_token",
    )
    return {
        "ok": True,
        "action": "create_token",
        "venue": "paper",
        "ticker": ticker,
        "size_sol": size_sol,
    }


def sell_position(
    *,
    venue: str = "paper",
    human_approved: bool = False,
    size_sol: float = 0.05,
    approval_chain: Optional[dict[str, Any]] = None,
    daily_deployed: float = 0.0,
    concurrent: int = 0,
    ticker: str = "PAPER",
    **_extra: Any,
) -> dict[str, Any]:
    _check_gates(
        venue=venue,
        human_approved=human_approved,
        size_sol=size_sol,
        approval_chain=approval_chain,
        daily_deployed=daily_deployed,
        concurrent=concurrent,
        action="sell_position",
    )
    return {
        "ok": True,
        "action": "sell_position",
        "venue": "paper",
        "ticker": ticker,
        "size_sol": size_sol,
    }
