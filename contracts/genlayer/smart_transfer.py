from genlayer import *


class SmartTransfer(gl.Contract):
    def __init__(self):
        pass

    @gl.public.write.payable
    def deploy(
        self,
        owner,
        token,
        recipient,
        amount,
        min_balance,
        max_amount,
        allowlist,
        oracle_condition,
        interval,
        execute_at_utc,
        source_chain_id,
    ):
        """Factory-style deploy of a SmartTransfer instance.
        
        Stores all configuration on-chain for later condition checks.
        """
        # Store all configuration as contract state
        self.owner = owner
        self.token = token
        self.recipient = recipient
        self.amount = amount
        self.min_balance = min_balance
        self.max_amount = max_amount
        self.allowlist = allowlist
        self.oracle_condition = oracle_condition
        self.interval = interval
        self.execute_at_utc = execute_at_utc
        self.source_chain_id = source_chain_id
        
        # Initialize counters/timers
        self.executed = False
        self.last_executed_round = 0
        
        # Emit deployment event
        self.emit_event(
            "TransferDeployed",
            owner=owner,
            token=token,
            recipient=recipient,
            amount=amount,
            min_balance=min_balance,
            max_amount=max_amount,
        )

    @gl.public.view
    def can_execute(self) -> dict:
        """Check if the transfer can be executed given all conditions.
        
        Returns {ok: bool, reasons: ["string"]}
        """
        reasons = []
        
        # Check: owner is valid
        if not self.owner:
            reasons.append("Owner not set")
            return {"ok": False, "reasons": reasons}
        
        # Check: recipient is valid
        if not self.recipient:
            reasons.append("Recipient not set")
            return {"ok": False, "reasons": reasons}
        
        # Check: amount does not exceed max_amount
        if self.amount > self.max_amount:
            reasons.append(f"Amount {self.amount} exceeds max {self.max_amount}")
        
        # Check: allowlist - if set, recipient must be in allowlist
        if self.allowlist and self.recipient not in self.allowlist:
            reasons.append("Recipient not in allowlist")
        
        # Check: minimum balance to maintain
        # This would require checking the sender's balance - view only can estimate
        # For now, mark as checked (backend will enforce fully)
        reasons.append("Min balance check: enforce on relayer execution")
        
        # Check: oracle condition - LLM + web verification
        if self.oracle_condition:
            # Dry-run oracle verification via GenLayer web/LLM
            oracle_check = gl.nondet.web.get(
                url="https://api.genlayer.com/oracle/verify",
                params={"condition": self.oracle_condition}
            )
            if not oracle_check.get("oracle_passed", False):
                reasons.append(f"Oracle condition not yet verified: {self.oracle_condition}")
        
        # Check: scheduled execution time
        if self.execute_at_utc:
            from datetime import datetime, timezone
            try:
                execute_dt = datetime.fromisoformat(self.execute_at_utc.replace("Z", "+00:00"))
                now = datetime.now(timezone.utc)
                if execute_dt < now:
                    reasons.append(f"Scheduled time {self.execute_at_utc} has passed")
            except (ValueError, TypeError):
                reasons.append(f"Invalid execute_at_utc format: {self.execute_at_utc}")
        
        # Check: recurrence interval - would need to verify no double-spend
        if self.interval:
            reasons.append(f"Recurrence interval: {self.interval} - enforce on backend")
        
        ok = len(reasons) == 0
        return {"ok": ok, "reasons": reasons}

    @gl.public.write
    def check_oracle(self) -> dict:
        """LLM + web verify the natural language oracle condition.
        
        Records oracle_passed and evidence hash on-chain.
        Returns {ok: bool, evidence_hash: str}
        """
        # Use GenLayer's intelligent oracle to verify the NL condition
        verification = gl.nondet.exec_prompt(
            prompt_non_comparative(
                get_input=self.oracle_condition,
                task="Verify this condition is currently true on-chain. Return only: 'PASSED' or 'FAILED', no explanation.",
                criteria="return exactly PASSED or FAILED, boolean, no explanation"
            )
        )
        
        oracle_passed = verification.strip().upper() == "PASSED"
        evidence_hash = gl.nondet.web.hash(self.oracle_condition + str(gl.nondet.get_current_block()["number"]))
        
        # Store on-chain
        self.oracle_passed = oracle_passed
        self.oracle_evidence = evidence_hash
        
        return {"ok": oracle_passed, "evidence_hash": evidence_hash}

    @gl.public.write
    def execute(self, sender) -> dict:
        """Execute the transfer if all conditions pass.
        
        Only executes if can_execute() returned ok AND oracle_passed.
        Emits event and returns transaction hash.
        """
        # Prerequisite: must have been deployed first
        if not hasattr(self, "owner"):
            return {"ok": False, "error": "Contract not deployed"}
        
        # Check conditions
        conditions = self.can_execute()
        if not conditions["ok"]:
            return {"ok": False, "reasons": conditions["reasons"]}
        
        # Check oracle
        if not getattr(self, "oracle_passed", False):
            return {"ok": False, "reasons": ["Oracle condition not yet verified"]}
        
        # Prevent double execution
        if getattr(self, "executed", False):
            return {"ok": False, "reasons": ["Already executed"]}
        
        # Execute the EVM transfer via relayer
        # In a real implementation, this would emit an external message
        # for the relayer to execute the EVM transfer
        self.executed = True
        
        # Emit execution event
        self.emit_event(
            "TransferExecuted",
            sender=sender,
            recipient=self.recipient,
            amount=self.amount,
            token=self.token,
        )
        
        # Schedule next recurrence if applicable
        if self.interval:
            # Backend will handle recurrence scheduling
            pass
        
        return {
            "ok": True,
            "tx_hash": "0x" + gl.nondet.get_current_block()["hash"][-16:],
            "executed_at": gl.nondet.get_current_block()["timestamp"],
        }

    @gl.public.view
    def get_config(self) -> dict:
        """Return the current contract configuration."""
        return {
            "owner": self.owner,
            "token": self.token,
            "recipient": self.recipient,
            "amount": self.amount,
            "min_balance": self.min_balance,
            "max_amount": self.max_amount,
            "allowlist": self.allowlist,
            "oracle_condition": self.oracle_condition,
            "interval": self.interval,
            "execute_at_utc": self.execute_at_utc,
            "source_chain_id": self.source_chain_id,
            "executed": getattr(self, "executed", False),
            "oracle_passed": getattr(self, "oracle_passed", False),
        }

    @gl.public.view
    def get_status(self) -> dict:
        """Return the current status of the smart transfer."""
        return {
            "deployed": hasattr(self, "owner"),
            "executed": getattr(self, "executed", False),
            "oracle_passed": getattr(self, "oracle_passed", False),
            "config": self.get_config(),
        }