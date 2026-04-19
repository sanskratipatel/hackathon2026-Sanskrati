from __future__ import annotations

from typing import Dict, Any, Optional, List

from src.config import settings
from src.utils import days_between, sanitize_text


# =====================================================
# ENUM DECISIONS
# =====================================================

APPROVED = "APPROVED"
DENIED = "DENIED"
ESCALATE = "ESCALATE"
NEED_MORE_INFO = "NEED_MORE_INFO"
FLAG_FRAUD = "FLAG_FRAUD"


# =====================================================
# INTENT DETECTION (RULE FIRST)
# =====================================================

def detect_intent(message: str) -> str:
    """
    Deterministic intent classification.
    """
    text = sanitize_text(message).lower()

    rules = {
        "refund": [
            "refund", "money back", "return money"
        ],
        "return": [
            "return item", "want to return", "send back"
        ],
        "cancel": [
            "cancel", "stop order", "cancel order"
        ],
        "exchange": [
            "exchange", "wrong size", "wrong colour", "replace size"
        ],
        "warranty": [
            "warranty", "manufacturing defect", "not working after months"
        ],
        "damaged": [
            "damaged", "broken", "cracked", "arrived broken"
        ],
        "wrong_item": [
            "wrong item", "received different", "incorrect product"
        ],
        "tracking": [
            "where is my order", "late", "tracking", "not delivered"
        ],
        "vip_claim": [
            "i am vip", "vip customer", "premium customer"
        ]
    }

    for intent, phrases in rules.items():
        for p in phrases:
            if p in text:
                return intent

    return "general"


# =====================================================
# CORE POLICY ENGINE
# =====================================================

def evaluate_ticket(
    ticket: dict,
    customer: Optional[dict],
    order: Optional[dict],
    product: Optional[dict],
    tool_outputs: Optional[dict] = None
) -> Dict[str, Any]:
    """
    Master deterministic decision engine.
    """
    tool_outputs = tool_outputs or {}

    message = ticket.get("message", "")
    intent = detect_intent(message)

    result = {
        "intent": intent,
        "decision": NEED_MORE_INFO,
        "reason": "",
        "priority": "medium",
        "requires_human": False,
        "flags": [],
    }

    # -------------------------------------------------
    # Missing critical data
    # -------------------------------------------------
    if not customer:
        result["reason"] = "Customer record not found"
        result["decision"] = ESCALATE
        result["requires_human"] = True
        return result

    if not order and intent not in ["general"]:
        result["reason"] = "Order record missing"
        result["decision"] = ESCALATE
        result["requires_human"] = True
        return result

    # -------------------------------------------------
    # Fraud Check
    # -------------------------------------------------
    fraud = tool_outputs.get("fraud", {})
    if fraud.get("fraud_risk"):
        result["decision"] = FLAG_FRAUD
        result["reason"] = "Suspicious activity detected"
        result["flags"] = fraud.get("flags", [])
        result["priority"] = "high"
        result["requires_human"] = True
        return result

    # -------------------------------------------------
    # VIP False Claim
    # -------------------------------------------------
    if intent == "vip_claim":
        tier = str(customer.get("tier", "standard")).lower()
        if tier != "vip":
            result["decision"] = FLAG_FRAUD
            result["reason"] = "Unverified VIP privilege claim"
            result["requires_human"] = True
            return result

   
    if intent == "cancel":
        return cancellation_policy(order)

  
    if intent == "refund":
        return refund_policy(customer, order, product, tool_outputs)

  
    if intent == "return":
        return return_policy(customer, order, product, tool_outputs)

    if intent == "warranty":
        return warranty_policy(tool_outputs)

    if intent == "damaged":
        return damaged_policy()

   
    if intent == "wrong_item":
        return wrong_item_policy()

    
    if intent == "exchange":
        return exchange_policy()

   
    if intent == "tracking":
        return tracking_policy(order)

    result["decision"] = NEED_MORE_INFO
    result["reason"] = "Unable to determine exact request"
    return result



def cancellation_policy(order: dict) -> dict:
    status = str(order.get("status", "")).lower()

    if status == "processing":
        return _ok(APPROVED, "Order can be cancelled before shipment")

    if status == "shipped":
        return _ok(DENIED, "Order already shipped. Use return after delivery")

    if status == "delivered":
        return _ok(DENIED, "Delivered orders cannot be cancelled")

    return _ok(ESCALATE, "Unknown order status")


def refund_policy(customer, order, product, tool_outputs):
    amount = float(order.get("amount", 0))

    if amount > settings.refund_escalate_amount:
        return _ok(ESCALATE, "Refund exceeds allowed auto-limit")

    refund = tool_outputs.get("refund", {})

    if refund.get("eligible"):
        return _ok(APPROVED, "Refund eligible under policy")

    return _ok(DENIED, refund.get("reason", "Refund not eligible"))


def return_policy(customer, order, product, tool_outputs):
    ret = tool_outputs.get("return_window", {})

    if ret.get("eligible"):
        return _ok(APPROVED, "Return within allowed policy window")

    tier = str(customer.get("tier", "standard")).lower()

    # Premium/VIP borderline exception
    if tier in ["premium", "vip"]:
        age = ret.get("age_days", 999)

        if age <= ret.get("window_days", 30) + 3:
            return _ok(
                ESCALATE,
                "Borderline premium/VIP exception needs approval"
            )

    return _ok(DENIED, "Outside return window")


def warranty_policy(tool_outputs):
    return {
        "decision": ESCALATE,
        "reason": "Warranty claims handled by specialist team",
        "priority": "high",
        "requires_human": True
    }


def damaged_policy():
    return {
        "decision": ESCALATE,
        "reason": "Damaged item may need replacement/refund review",
        "priority": "high",
        "requires_human": True
    }


def wrong_item_policy():
    return _ok(APPROVED, "Free return pickup and replacement/refund available")


def exchange_policy():
    return _ok(APPROVED, "Exchange allowed subject to stock availability")


def tracking_policy(order):
    status = str(order.get("status", "")).lower()

    if status == "processing":
        return _ok(APPROVED, "Order is being prepared")

    if status == "shipped":
        return _ok(APPROVED, "Order shipped and in transit")

    if status == "delivered":
        return _ok(APPROVED, "Order marked delivered")

    return _ok(NEED_MORE_INFO, "Tracking information unavailable")


# =====================================================
# HELPERS
# =====================================================

def _ok(decision: str, reason: str):
    return {
        "decision": decision,
        "reason": reason,
        "priority": "medium",
        "requires_human": decision in [ESCALATE, FLAG_FRAUD]
    }


# =====================================================
# SELF CHECK / CRITIC PASS
# =====================================================

def critic_review(policy_result: dict) -> dict:
    """
    Safety reviewer checks contradictions.
    """
    decision = policy_result.get("decision")
    reason = policy_result.get("reason", "").lower()

    # suspicious approval contradictions
    if decision == APPROVED and "exceeds" in reason:
        return {
            "passed": False,
            "override_decision": ESCALATE,
            "comment": "Approval contradicts risk threshold"
        }

    return {
        "passed": True,
        "override_decision": decision,
        "comment": "Passed policy consistency check"
    }


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":
    sample = {
        "message": "Please cancel my order"
    }

    order = {"status": "processing"}

    print(evaluate_ticket(sample, {"tier": "standard"}, order, {}, {}))