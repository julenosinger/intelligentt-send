# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json
from datetime import datetime, timezone


class SmartTransfer(gl.Contract):
    owner: str
    token: str
    recipient: str
    amount: str
    min_balance: str
    max_amount: str
    allowlist: str  # JSON-encoded list of addresses
    oracle_condition: str
    interval: str
    execute_at_utc: str
    source_chain_id: str
    oracle_passed: bool = False
    oracle_evidence: str = ""
    executed: bool = False

    def __init__(
        self,
        owner: str,
        token: str,
        recipient: str,
        amount: str,
        min_balance: str,
        max_amount: str,
        allowlist: str,
        oracle_condition: str,
        interval: str,
        execute_at_utc: str,
        source_chain_id: str,
    ):
        self.owner = owner
        self.token = token
        self.recipient = recipient
        self.amount = amount
        self.min_balance = min_balance
        self.max_amount = max_amount
        self.allowlist = allowlist  # JSON string
        self.oracle_condition = oracle_condition
        self.interval = interval
        self.execute_at_utc = execute_at_utc
        self.source_chain_id = source_chain_id
        self.oracle_passed = False
        self.oracle_evidence = ""
        self.executed = False

    @gl.public.view
    def can_execute(self) -> dict:
        """Deterministic condition check. Reasons only when a condition fails.

        min_balance and interval/recurrence are enforced off-chain by the relayer
        and intentionally do NOT block can_execute.
        """
        reasons = []

        if not self.owner:
            reasons.append("Owner not set")

        if not self.recipient:
            reasons.append("Recipient not set")

        try:
            if float(self.amount) > float(self.max_amount):
                reasons.append(f"Amount {self.amount} exceeds max {self.max_amount}")
        except (ValueError, TypeError):
            reasons.append("Invalid amount format")

        try:
            allow = json.loads(self.allowlist) if self.allowlist else []
            if allow and self.recipient not in allow:
                reasons.append("Recipient not in allowlist")
        except Exception:
            pass  # malformed allowlist: skip, relayer enforces

        if self.execute_at_utc:
            try:
                execute_dt = datetime.fromisoformat(self.execute_at_utc.replace("Z", "+00:00"))
                if datetime.now(timezone.utc) < execute_dt:
                    reasons.append(f"Execution time not reached: {self.execute_at_utc}")
            except (ValueError, TypeError):
                reasons.append(f"Invalid execute_at_utc format: {self.execute_at_utc}")

        return {"ok": len(reasons) == 0, "reasons": reasons}

    @gl.public.write
    def check_oracle(self) -> dict:
        """Verify the natural-language oracle condition via a single LLM call."""

        def get_input() -> str:
            return self.oracle_condition

        verification = gl.eq_principle.prompt_non_comparative(
            get_input,
            task="Determine whether this condition is currently true. Answer PASSED or FAILED.",
            criteria="Answer must be exactly PASSED or FAILED (uppercase), nothing else.",
        )

        passed = verification.strip().upper() == "PASSED"
        self.oracle_passed = passed
        # Evidence is the LLM's own short text (no invented hashing API).
        self.oracle_evidence = verification.strip()[:200]
        return {"ok": passed, "evidence": self.oracle_evidence}

    @gl.public.write
    def execute(self, sender: str) -> dict:
        """Execute the transfer if conditions pass. Sets executed=True.

        The actual EVM transfer is carried out by the off-chain relayer; this
        contract does not mint or invent an EVM tx hash.
        """
        if not self.owner:
            return {"ok": False, "error": "Contract not configured"}

        conditions = self.can_execute()
        if not conditions["ok"]:
            return {"ok": False, "reasons": conditions["reasons"]}

        # Oracle only required when an oracle condition was set
        if self.oracle_condition and not self.oracle_passed:
            return {"ok": False, "reasons": ["Oracle condition not verified"]}

        if self.executed:
            return {"ok": False, "reasons": ["Already executed"]}

        self.executed = True
        return {"ok": True}

    @gl.public.view
    def get_config(self) -> dict:
        try:
            allow = json.loads(self.allowlist) if self.allowlist else []
        except Exception:
            allow = []
        return {
            "owner": self.owner,
            "token": self.token,
            "recipient": self.recipient,
            "amount": self.amount,
            "min_balance": self.min_balance,
            "max_amount": self.max_amount,
            "allowlist": allow,
            "oracle_condition": self.oracle_condition,
            "interval": self.interval,
            "execute_at_utc": self.execute_at_utc,
            "source_chain_id": self.source_chain_id,
            "executed": self.executed,
            "oracle_passed": self.oracle_passed,
        }

    @gl.public.view
    def get_status(self) -> dict:
        return {
            "configured": bool(self.owner),
            "executed": self.executed,
            "oracle_passed": self.oracle_passed,
            "config": self.get_config(),
        }
