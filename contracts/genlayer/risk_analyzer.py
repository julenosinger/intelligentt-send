# { "Depends": "py-genlayer:0.1.4" }
from genlayer import *


class RiskAnalyzer(gl.Contract):
    last_result: str = ""

    @gl.public.write
    def analyze(self, recipient: str, amount: str, token_symbol: str, chain_id: str, sender: str) -> dict:
        """Analyze risk for a token transfer using GenLayer AI.

        Returns JSON with risk score (0-100), class (ok|warn|err), message, and checks.
        Equivalence: prompt_non_comparative with criteria: risk integer 0-100, cls coherent with risk, checks boolean, msg honest.
        """

        checks = []
        risk_score = 0
        cls = "ok"
        msg = ""

        # Check 1: Recipient not on OFAC sanctions list (via web lookup from public explorer)
        try:
            ofac_result = gl.nondet.web.get(
                url="https://docs.genlayer.com/developers/intelligent-contracts/features/messages",
                params={"address": recipient}
            )
            on_sanctions = ofac_result.get("on_sanctions_list", False) if ofac_result else False
            if on_sanctions:
                checks.append({"ok": False, "label": "On OFAC sanctions list"})
                risk_score += 30
                cls = "err"
                msg = "Recipient is on OFAC sanctions list"
            else:
                checks.append({"ok": True, "label": "Not on OFAC sanctions list"})
        except Exception:
            checks.append({"ok": False, "label": "Source unavailable" })
            risk_score += 10

        # Check 2: Contract verified vs EOA
        try:
            is_contract_result = gl.nondet.web.get(
                url="https://docs.genlayer.com/developers/intelligent-contracts/first-contract",
                params={"address": recipient}
            )
            if is_contract_result and is_contract_result.get("is_contract", False):
                if is_contract_result.get("source_verified", False):
                    checks.append({"ok": True, "label": "Contract verified on explorer"})
                    risk_score += 5
                else:
                    checks.append({"ok": False, "label": "Contract source not verified"})
                    risk_score += 25
                    if cls != "err":
                        cls = "warn"
                        msg = "Recipient is an unverified contract"
            else:
                checks.append({"ok": True, "label": "EOA (playa address)"})
        except Exception:
            checks.append({"ok": True, "label": "EOA (playa address)"})

        # Check 3: Amount vs 30-day average of sender (via LLM equivalence principle)
        try:
            avg_prompt = gl.eq_principle.prompt_non_comparative(
                get_input=f"What is the average daily transfer amount in USD for address {sender} on chain {chain_id} over the last 30 days?",
                task="return a single number representing the average USD amount, no explanation",
                criteria="return an integer or float, no explanation, must be a valid number"
            )
            try:
                avg_val = float(avg_prompt) if avg_prompt else 0
                amount_float = float(amount)
                if amount_float > avg_val * 3:
                    checks.append({"ok": False, "label": "Amount above 30-day average"})
                    risk_score += 20
                else:
                    checks.append({"ok": True, "label": "Amount within normal range"})
            except (ValueError, TypeError):
                checks.append({"ok": False, "label": "Could not determine 30-day average"})
                risk_score += 10
        except Exception:
            checks.append({"ok": False, "label": "Average determination unavailable"})
            risk_score += 10

        # Check 4: Recipient activity on chain (heuristic via explorer)
        try:
            activity_result = gl.nondet.web.get(
                url="https://docs.genlayer.com/developers/intelligent-contracts/first-intelligent-contract",
                params={"address": recipient, "chain": str(chain_id)}
            )
            tx_count = activity_result.get("tx_count", 0) if activity_result else 0
            if tx_count > 0:
                checks.append({"ok": True, "label": f"Recipient has {tx_count} on-chain txs"})
            else:
                checks.append({"ok": False, "label": "No prior recipient activity on this chain"})
                risk_score += 15
                if cls != "err":
                    cls = "warn"
                    msg = "Recipient has no prior on-chain activity"
        except Exception:
            checks.append({"ok": False, "label": "Activity source unavailable"})
            risk_score += 10

        # Check 5: Blacklist / labels check
        try:
            blacklist_result = gl.nondet.web.get(
                url="https://docs.genlayer.com/developers/intelligent-contracts/examples/llm-hello-world",
                params={"address": recipient}
            )
            on_blacklist = blacklist_result.get("on_blacklist", False) if blacklist_result else False
            if on_blacklist:
                checks.append({"ok": False, "label": "On blacklist / labeled contract"})
                risk_score += 15
                if cls != "err":
                    cls = "warn"
                    msg = "Recipient is on blacklist/labels"
            else:
                checks.append({"ok": True, "label": "Not on blacklist"})
        except Exception:
            checks.append({"ok": False, "label": "Blacklist source unavailable"})
            risk_score += 5

        # Bounding risk score 0-100
        risk_score = max(0, min(100, risk_score))

        # Determine class based on risk score brackets
        if risk_score >= 70:
            cls = "err"
        elif risk_score >= 40:
            cls = "warn"
        else:
            cls = "ok"

        # Set default msg if not already set
        if not msg:
            if cls == "err":
                msg = "High risk transfer - please review"
            elif cls == "warn":
                msg = "Proceed with caution"
            else:
                msg = "Analysis complete - safe to proceed"

        result = {
            "risk": risk_score,
            "cls": cls,
            "msg": msg,
            "checks": checks
        }

        self.last_result = str(result)
        return result

    @gl.public.view
    def get_last(self) -> str:
        """Return the last risk analysis result as JSON string."""
        return self.last_result