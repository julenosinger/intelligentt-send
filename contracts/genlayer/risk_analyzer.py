# { "Depends": "py-genlayer:1jb45aa8ynh2a9c9xn3b7qqh8sm5q93hwfp7jqmwsfhh8jpz09h6" }

from genlayer import *
import json


class RiskAnalyzer(gl.Contract):
    last_result: str = ""

    @gl.public.write
    def analyze(
        self,
        recipient: str,
        amount: str,
        token_symbol: str,
        chain_id: str,
        sender: str,
    ) -> str:
        """Analyze transfer risk with a single non-comparative LLM call.

        The input function optionally renders the target chain's explorer page for
        the recipient. If the fetch fails, the input says SOURCE_UNAVAILABLE so the
        model does not fabricate OFAC/verification facts. The result is stored in
        last_result as a JSON string.
        """

        def get_input() -> str:
            explorer = self._explorer_for(chain_id)
            source = "SOURCE_UNAVAILABLE"
            if explorer:
                try:
                    page = gl.nondet.web.render(f"{explorer}/address/{recipient}", mode="html")
                    source = page[:2000]
                except Exception:
                    source = "SOURCE_UNAVAILABLE"
            return (
                f"Token transfer risk assessment.\n"
                f"recipient: {recipient}\n"
                f"amount: {amount} {token_symbol}\n"
                f"chain_id: {chain_id}\n"
                f"sender: {sender}\n"
                f"recipient explorer page: {source}\n"
            )

        result = gl.eq_principle.prompt_non_comparative(
            get_input,
            task=(
                "Assess the risk of this token transfer and return a JSON object with keys: "
                "risk (integer 0-100), cls (one of ok|warn|err), msg (a 1-2 sentence "
                "summary), and checks (a list of objects each with ok:boolean and "
                "label:string)."
            ),
            criteria=(
                "The output must be a JSON object with: risk (integer 0-100), cls (one of "
                "ok|warn|err), msg (string), checks (list of {ok:boolean, label:string}). "
                "cls must align with risk: ok when risk<40, warn when 40<=risk<70, err when "
                "risk>=70. Checks must be honest: only assert facts that actually appear in "
                "the provided recipient explorer page. If the source is SOURCE_UNAVAILABLE, "
                "do not claim any OFAC/sanctions/verification status; instead emit a check "
                "with ok:false and label 'source unavailable'."
            ),
        )

        parsed = self._parse(result)
        self.last_result = json.dumps(parsed)
        return self.last_result

    def _parse(self, text: str) -> dict:
        try:
            data = json.loads(text)
        except Exception:
            data = {}

        risk = int(data.get("risk", 0)) if isinstance(data.get("risk"), (int, float)) else 0
        risk = max(0, min(100, risk))

        cls = data.get("cls", "ok")
        if cls not in ("ok", "warn", "err"):
            cls = "err" if risk >= 70 else ("warn" if risk >= 40 else "ok")

        msg = str(data.get("msg", ""))

        raw_checks = data.get("checks", []) if isinstance(data.get("checks"), list) else []
        checks = [
            {"ok": bool(c.get("ok", False)), "label": str(c.get("label", ""))}
            for c in raw_checks
            if isinstance(c, dict)
        ]

        return {"risk": risk, "cls": cls, "msg": msg, "checks": checks}

    def _explorer_for(self, chain_id: str) -> str:
        if chain_id == "5042002":
            return "https://testnet.arcscan.app"
        if chain_id == "11155111":
            return "https://sepolia.etherscan.io"
        return ""

    @gl.public.view
    def get_last(self) -> str:
        """Return the last risk analysis result as a JSON string."""
        return self.last_result
