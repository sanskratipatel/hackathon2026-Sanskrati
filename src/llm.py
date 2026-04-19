from __future__ import annotations

import json
from typing import Dict, Any, Optional

import requests

from src.config import settings, provider_available
from src.logger import log_error, log_info
from src.utils import retry_call, sanitize_text


# =====================================================
# SYSTEM PROMPT
# =====================================================

SYSTEM_PROMPT = """
You are ShopWave Support AI.

STRICT RULES:
1. Use ONLY provided facts.
2. Never invent policy.
3. Never override deterministic decisions.
4. If data missing, say NEED_MORE_INFO.
5. Return valid JSON only.

Required JSON format:
{
  "summary":"short reasoning",
  "customer_reply":"professional concise reply",
  "confidence":0.0
}
"""


# =====================================================
# MAIN WRAPPER
# =====================================================

class LLMClient:
    def __init__(self):
        self.provider = provider_available()
        self.timeout = settings.request_timeout
        self.max_retries = settings.max_retries

    # -------------------------------------------------
    # PUBLIC METHOD
    # -------------------------------------------------
    def generate_decision_text(
        self,
        ticket: dict,
        policy_result: dict,
        kb_context: str,
        tool_context: dict
    ) -> Dict[str, Any]:
        """
        Generate grounded response text only.
        """
        try:
            prompt = self._build_prompt(
                ticket=ticket,
                policy_result=policy_result,
                kb_context=kb_context,
                tool_context=tool_context
            )

            result = retry_call(
                self._dispatch,
                prompt,
                retries=self.max_retries
            )

            parsed = self._safe_parse(result)

            if parsed:
                return parsed

            return self._fallback_response(policy_result)

        except Exception as e:
            log_error("llm_generate_failed", {"error": str(e)})
            return self._fallback_response(policy_result)

    # -------------------------------------------------
    # PROVIDER ROUTER
    # -------------------------------------------------
    def _dispatch(self, prompt: str) -> str:
        if self.provider == "groq":
            return self._groq(prompt)

        if self.provider == "openrouter":
            return self._openrouter(prompt)

        if self.provider == "together":
            return self._together(prompt)

        return self._ollama(prompt)

    # -------------------------------------------------
    # PROVIDERS
    # -------------------------------------------------
    def _groq(self, prompt: str) -> str:
        url = "https://api.groq.com/openai/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.groq_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.model_name,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }

        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()

        return r.json()["choices"][0]["message"]["content"]

    def _openrouter(self, prompt: str) -> str:
        url = "https://openrouter.ai/api/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.openrouter_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.model_name,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }

        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()

        return r.json()["choices"][0]["message"]["content"]

    def _together(self, prompt: str) -> str:
        url = "https://api.together.xyz/v1/chat/completions"

        headers = {
            "Authorization": f"Bearer {settings.together_api_key}",
            "Content-Type": "application/json"
        }

        payload = {
            "model": settings.model_name,
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt}
            ]
        }

        r = requests.post(url, headers=headers, json=payload, timeout=self.timeout)
        r.raise_for_status()

        return r.json()["choices"][0]["message"]["content"]

    def _ollama(self, prompt: str) -> str:
        url = f"{settings.ollama_base_url}/api/generate"

        payload = {
            "model": settings.model_name,
            "prompt": SYSTEM_PROMPT + "\n\n" + prompt,
            "stream": False
        }

        r = requests.post(url, json=payload, timeout=self.timeout)
        r.raise_for_status()

        return r.json()["response"]

    # -------------------------------------------------
    # PROMPT BUILDER
    # -------------------------------------------------
    def _build_prompt(
        self,
        ticket: dict,
        policy_result: dict,
        kb_context: str,
        tool_context: dict
    ) -> str:

        msg = sanitize_text(ticket.get("message", ""))

        return f"""
CUSTOMER MESSAGE:
{msg}

POLICY DECISION:
{json.dumps(policy_result, indent=2)}

TOOL FACTS:
{json.dumps(tool_context, indent=2)}

KNOWLEDGE BASE:
{kb_context}

Generate short professional customer reply aligned with policy decision.
Return JSON only.
"""

    # -------------------------------------------------
    # SAFE PARSER
    # -------------------------------------------------
    def _safe_parse(self, text: str) -> Optional[dict]:
        try:
            text = text.strip()

            # strip markdown fences
            text = text.replace("```json", "").replace("```", "").strip()

            obj = json.loads(text)

            return {
                "summary": str(obj.get("summary", "")),
                "customer_reply": str(obj.get("customer_reply", "")),
                "confidence": float(obj.get("confidence", 0.75))
            }

        except Exception:
            return None

    # -------------------------------------------------
    # FALLBACK RESPONSE
    # -------------------------------------------------
    def _fallback_response(self, policy_result: dict):
        decision = policy_result.get("decision", "NEED_MORE_INFO")
        reason = policy_result.get("reason", "")

        templates = {
            "APPROVED":
                "Your request has been approved. Our team is processing it now.",

            "DENIED":
                f"We reviewed your request. Unfortunately it cannot be approved at this time. {reason}",

            "ESCALATE":
                "Your request needs specialist review. Our team will contact you shortly.",

            "FLAG_FRAUD":
                "Your request requires additional verification before we can proceed.",

            "NEED_MORE_INFO":
                "We need a few more details to continue processing your request."
        }

        return {
            "summary": reason,
            "customer_reply": templates.get(decision, templates["NEED_MORE_INFO"]),
            "confidence": 0.1
        }


# =====================================================
# SINGLETON
# =====================================================

llm_client = LLMClient()


# =====================================================
# PUBLIC API
# =====================================================

def generate_response(ticket, policy_result, kb_context, tool_context):
    return llm_client.generate_decision_text(
        ticket,
        policy_result,
        kb_context,
        tool_context
    )


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":
    sample = generate_response(
        {"message": "I want refund"},
        {"decision": "APPROVED", "reason": "Eligible"},
        "Refunds take 5-7 business days.",
        {"order_found": True}
    )

    print(sample)