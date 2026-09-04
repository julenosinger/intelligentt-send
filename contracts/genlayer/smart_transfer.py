# { "Depends": "py-genlayer:0.1.4" }
from genlayer import *
import json
from datetime import datetime, timezone


class SmartTransfer(gl.Contract):
    # Typed state fields
    owner: str
    token: str
    recipient: str
    amount: str
    min_balance: str
    max_amount: str
    allowlist: str  # JSON list of addresses
    oracle_condition: str
    interval: str  # "None" | "Daily" | "Weekly" | "Monthly"
    execute_at_utc: str  # ISO UTC timestamp
    source_chain_id: str
    oracle_passed: bool = False
    executed: bool = False

    def __init__(self, owner: str, token: str, recipient: str, amount: str,
                 min_balance: str, max_amount: str, allowlist: List[str],
                 oracle_condition: str, interval: str, execute_at_utc: str,
                 source_chain_id: str):
        """Constructor - stores configuration.

        Note: gl.Contract factory pattern uses __init__ for init,
        deploy_contract is separate for on-chain deployment.
        """
        self.owner = owner
        self.token = token
        self.recipient = recipient
        self.amount = amount
        self.min_balance = min_balance
        self.max_amount = max_amount
        self.allowlist = json.dumps(allowlist) if allowlist else "[]"
        self.oracle_condition = oracle_condition
        self.interval = interval
        self.execute_at_utc = execute_at_utc
        self.source_chain_id = source_chain_id
        self.oracle_passed = False
        self.executed = False

    @gl.public.view
    def can_execute(self) -> dict:
        """Check if the transfer can be executed given all conditions.

        Returns {ok: bool, reasons: ["string"]}.
        Deterministic: no web/LLM calls. Reasons only on failure.
        ok=True if no failure reasons.
        """

        reasons: List[str] = []

        # Check: owner is set
        if not self.owner:
            reasons.append("Owner not set")

        # Check: recipient is set
        if not self.recipient:
            reasons.append("Recipient not set")

        # Check: amount does not exceed max_amount
        try:
            amount_val = float(self.amount)
            max_val = float(self.max_amount)
            if amount_val > max_val:
                reasons.append(f"Amount {self.amount} exceeds max {self.max_amount}")
        except (ValueError, TypeError):
            reasons.append(f"Invalid amount format: {self.amount}")

        # Check: allowlist - if set, recipient must be in allowlist
        try:
            allowlist_set = json.loads(self.allowlist) if self.allowlist else []
            if allowlist_set and self.recipient not in allowlist_set:
                reasons.append("Recipient not in allowlist")
        except (json.JSONDecodeError, TypeError):
            pass  # if allowlist malformed, skip this check

        # Check: minimum balance to maintain
        # Backend enforces fully; just note for relayer
        reasons.append("Min balance check: enforce on relayer execution")

        # Check: oracle condition - if set, must have been verified
        if self.oracle_condition:
            if not self.oracle_passed:
                reasons.append("Oracle condition not yet verified")

        # Check: scheduled execution time
        if self.execute_at_utc:
            try:
                execute_dt = datetime.fromisoformat(self.execute_at_utc.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                # Block if execute_dt is in the future (not yet time)
                if execute_dt > now:
                    reasons.append(f"Execution time not reached: {self.execute_at_utc}")
                # If execute_dt is in the past, that's fine (already past the window)
            except (ValueError, TypeError):
                reasons.append(f"Invalid execute_at_utc format: {self.execute_at_utc}")

        # Check: recurrence interval - just note, enforce on backend
        if self.interval and self.interval != "None":
            reasons.append(f"Recurrence interval: {self.interval} - enforce on backend")

        ok = len(reasons) == 0
        return {"ok": ok, "reasons": reasons}

    @gl.public.write
    def check_oracle(self) -> dict:
        """LLM + web verify the natural language oracle condition.

        Records oracle_passed and evidence hash on-chain.
        Returns {ok: bool, evidence_hash: str}
        """

        # Use GenLayer's intelligent oracle via eq_principle
        verification = gl.eq_principle.prompt_non_comparative(
            get_input=self.oracle_condition,
            task="Verify this condition is currently true on-chain. Return only: 'PASSED' or 'FAILED', no explanation.",
            criteria="return exactly PASSED or FAILED, boolean, no explanation"
        )

        oracle_passed = verification.strip().upper() == "PASSED"
        # Generate evidence hash from condition + block number
        try:
            block = gl.nondet.get_current_block()
            evidence_hash = gl.nondet.web.hash(self.oracle_condition + str(block["number"]))
        except Exception:
            evidence_hash = gl.nondet.web.hash(self.oracle_condition)

        # Store on-chain
        self.oracle_passed = oracle_passed
        self.oracle_evidence = evidence_hash

        return {"ok": oracle_passed, "evidence_hash": evidence_hash}

    @gl.public.write
    def execute(self, sender: str) -> dict:
        """Execute the transfer if all conditions pass.

        Only executes if can_execute() returned ok AND oracle_passed.
        Sets executed=True. Does not invent EVM tx hash.
        """

        # Prerequisite: must have been deployed first
        if not self.owner:
            return {"ok": False, "error": "Contract not deployed"}

        # Check conditions deterministically
        conditions = self.can_execute()
        if not conditions["ok"]:
            return {"ok": False, "reasons": conditions["reasons"]}

        # Check oracle - must have been verified
        if not self.oracle_passed:
            return {"ok": False, "reasons": ["Oracle condition not yet verified"]}

        # Prevent double execution
        if self.executed:
            return {"ok": False, "reasons": ["Already executed"]}

        # Execute: mark as executed, do NOT invent EVM tx hash
        # The actual EVM transfer is executed by the relayer via messages
        self.executed = True

        # Return success - relayer handles the actual EVM transfer
        return {
            "ok": True,
            "executed_at": gl.nondet.get_current_block()["timestamp"],
            "note": "EVM transfer executed by relayer via message passing",
        }

    @gl.public.view
    def get_config(self) -> dict:
        """Return the current contract configuration."""
        try:
            allowlist_parsed = json.loads(self.allowlist) if self.allowlist else []
        except (json.JSONDecodeError, TypeError):
            allowlist_parsed = []

        return {
            "owner": self.owner,
            "token": self.token,
            "recipient": self.recipient,
            "amount": self.amount,
            "min_balance": self.min_balance,
            "max_amount": self.max_amount,
            "allowlist": allowlist_parsed,
            "oracle_condition": self.oracle_condition,
            "interval": self.interval,
            "execute_at_utc": self.execute_at_utc,
            "source_chain_id": self.source_chain_id,
            "executed": self.executed,
            "oracle_passed": self.oracle_passed,
        }

    @gl.public.view
    def get_status(self) -> dict:
        """Return the current status of the smart transfer."""
        return {
            "deployed": bool(self.owner),
            "executed": self.executed,
            "oracle_passed": self.oracle_passed,
            "config": self.get_config(),
        }