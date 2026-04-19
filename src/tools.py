from __future__ import annotations

from typing import Any, Dict, List, Optional

from src.config import settings
from src.logger import audit_tool_call, log_error
from src.utils import (
    days_between,
    retry_call,
    safe_read_json,
    safe_email,
)


# =====================================================
# LOAD DATA SOURCES
# =====================================================
def _load_data():
    try:
        customers = safe_read_json(settings.customers_file, [])
        orders = safe_read_json(settings.orders_file, [])
        products = safe_read_json(settings.products_file, [])
        return customers, orders, products
    except Exception:
        return [], [], []


CUSTOMERS, ORDERS, PRODUCTS = _load_data()


# =====================================================
# HELPERS
# =====================================================
def refresh_data() -> None:
    """
    Reload JSON files.
    Useful during Streamlit live updates.
    """
    global CUSTOMERS, ORDERS, PRODUCTS
    CUSTOMERS, ORDERS, PRODUCTS = _load_data()


def _safe_list(data: Any) -> list:
    return data if isinstance(data, list) else []


# =====================================================
# LOOKUP FUNCTIONS
# =====================================================
def get_customer(customer_id: str, ticket_id: str = "SYSTEM") -> Optional[dict]:
    try:
        rows = _safe_list(CUSTOMERS)

        for row in rows:
            if str(row.get("customer_id")) == str(customer_id):
                audit_tool_call(ticket_id, "get_customer", {"customer_id": customer_id}, row)
                return row

        audit_tool_call(ticket_id, "get_customer", {"customer_id": customer_id}, {}, False)
        return None

    except Exception as e:
        log_error("get_customer_failed", {"error": str(e)})
        return None


def lookup_by_email(email: str, ticket_id: str = "SYSTEM") -> Optional[dict]:
    try:
        target = safe_email(email)
        print(target , "lookup_by_email_failed*****************")
        for row in _safe_list(CUSTOMERS):
            if safe_email(row.get("email", "")) == target:
                audit_tool_call(ticket_id, "lookup_by_email", {"email": email}, row)
                return row
        print("**************************")
        audit_tool_call(ticket_id, "lookup_by_email", {"email": email}, {}, False)
        return None

    except Exception as e:
        log_error("lookup_by_email_failed", {"error": str(e)})
        return None


def get_order(order_id: str, ticket_id: str = "SYSTEM") -> Optional[dict]:
    try:
        for row in _safe_list(ORDERS):
            if str(row.get("order_id")) == str(order_id):
                audit_tool_call(ticket_id, "get_order", {"order_id": order_id}, row)
                return row

        audit_tool_call(ticket_id, "get_order", {"order_id": order_id}, {}, False)
        return None

    except Exception as e:
        log_error("get_order_failed", {"error": str(e)})
        return None


def get_product(product_id: str, ticket_id: str = "SYSTEM") -> Optional[dict]:
    try:
        for row in _safe_list(PRODUCTS):
            if str(row.get("product_id")) == str(product_id):
                audit_tool_call(ticket_id, "get_product", {"product_id": product_id}, row)
                return row
        print("get_product ))))))))))))" , product_id)
        audit_tool_call(ticket_id, "get_product", {"product_id": product_id}, {}, False)
        return None

    except Exception as e:
        log_error("get_product_failed", {"error": str(e)})
        return None


# =====================================================
# BUSINESS LOGIC TOOLS
# =====================================================
def check_return_window(
    delivered_at: str,
    category: str,
    ticket_id: str = "SYSTEM",
    order_at: str = None,
     order: dict = None
) -> Dict[str, Any]:
    """
    Return eligibility by category policy.
    """
    try:  
        print(delivered_at , order , order_at , "check_return_window )))))))))))))))))))))))))))") 
        order_at= order_at or order.get("order_date") if order else None
        print(order_at , "check_return_window order_at)))))))))))))))))))))))))))") 
        delivered_at = delivered_at or order.get("delivery_date") if order else None
        print(delivered_at , "check_return_window delivered_at))))))))))))))))))))))))))))")
        age_days = days_between( order_at,delivered_at)
        cat = (category or "").lower()
        print(age_days , cat , "check_return_window )))))))))))))))))))))))))))")
        limit = 30

        if "accessor" in cat:
            limit = 60
        elif any(x in cat for x in ["laptop", "tablet", "watch", "high-value"]):
            limit = 15
        elif "footwear" in cat:
            limit = 30
        elif "sports" in cat:
            limit = 30

        eligible = age_days <= limit

        result = {
            "eligible": eligible,
            "age_days": age_days,
            "window_days": limit,
        }

        audit_tool_call(ticket_id, "check_return_window", {
            "delivered_at": delivered_at,
            "category": category
        }, result)

        return result

    except Exception as e:
        log_error("check_return_window_failed", {"error": str(e)})
        return {"eligible": False, "reason": "tool_error"}


def check_refund_eligibility(
    order: dict,
    product: dict,
    ticket_id: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Conservative refund validator.
    """
    try:
        if not order:
            return {"eligible": False, "reason": "missing_order"}

        status = str(order.get("status", "")).lower()
        amount = float(order.get("amount", 0))

        if amount > settings.refund_escalate_amount:
            result = {"eligible": False, "reason": "high_amount_escalate"}
            audit_tool_call(ticket_id, "check_refund_eligibility", {}, result)
            return result

        if status == "processing":
            result = {"eligible": True, "reason": "pre_shipment"}
            audit_tool_call(ticket_id, "check_refund_eligibility", {}, result)
            return result

        category = product.get("category", "") if product else ""
        delivered_at = order.get("delivery_date")  
        print(delivered_at , category , "check_refund_eligibility delivered_at)))))))))))))))))))))))))))")
        if not delivered_at:
            return {
                "eligible": False,
                "age_days": None,
                "window_days": 7,
                "reason": "missing_delivery_date"
            } 
        order_at = order.get("order_date") 
        print(order_at , "check_refund_eligibility order_at)))))))))))))))))))))))))))")
        if not order_at:
            return {
                "eligible": False,
                "age_days": None,
                "window_days": 7,
                "reason": "missing_order_date"
            }
        print(delivered_at , category , order_at , "check_refund_eligibility )))))))))))))))))))))))))))")
        rw = check_return_window(delivered_at, category, ticket_id,order_at, order)
        print(rw , "check_refund_eligibility )))))))))))))))))))))))))))")
        result = {
            "eligible": bool(rw["eligible"]),
            "reason": "within_window" if rw["eligible"] else "outside_window"
        }

        audit_tool_call(ticket_id, "check_refund_eligibility", {}, result)
        return result

    except Exception as e:
        log_error("check_refund_eligibility_failed", {"error": str(e)})
        return {"eligible": False, "reason": "tool_error"}


def check_warranty(
    order: dict,
    product: dict,
    ticket_id: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Warranty claims always escalate, but validate active period.
    """
    try:
        category = str(product.get("category", "")).lower()
        delivered_at = order.get("delivery_date", "") 
        order_at = order.get("order_date", "")
        print(delivered_at , category , order_at , "check_warranty )))))))))))))))))))))))))))")
        age_days = days_between(order_at, delivered_at)

        months = 0

        if any(x in category for x in ["headphone", "speaker", "watch", "electronics"]):
            months = 12
        elif any(x in category for x in ["coffee", "kitchen", "appliance"]):
            months = 24
        elif "accessor" in category:
            months = 6
        else:
            months = 0

        covered = age_days <= (months * 30) if months > 0 else False

        result = {
            "covered": covered,
            "months": months,
            "age_days": age_days,
            "escalate": True
        }

        audit_tool_call(ticket_id, "check_warranty", {}, result)
        return result

    except Exception as e:
        log_error("check_warranty_failed", {"error": str(e)})
        return {"covered": False, "escalate": True}

   
def get_orders_by_customer(customer_id: str):
    results = []

    for row in _safe_list(ORDERS):
        if str(row.get("customer_id")) == str(customer_id):
            results.append(row)

    return results
def detect_fraud(
    ticket: dict,
    customer: Optional[dict],
    ticket_id: str = "SYSTEM"
) -> Dict[str, Any]:
    """
    Simple fraud heuristics.
    """
    try:
        text = str(ticket.get("body", "")).lower()

        flags = []
        print(text , "detect_fraud )))))))))))))))))))))))))))")
        if "vip" in text and customer:
            tier = str(customer.get("tier", "standard")).lower()
            if tier != "vip":
                flags.append("false_vip_claim")

        suspicious_words = [
            "legal action",
            "chargeback now",
            "refund immediately or else",
            "hack",
            "gift card only"
        ]

        for word in suspicious_words:
            if word in text:
                flags.append(word)

        result = {
            "fraud_risk": len(flags) > 0,
            "flags": flags
        }

        audit_tool_call(ticket_id, "detect_fraud", {}, result)
        return result

    except Exception as e:
        log_error("detect_fraud_failed", {"error": str(e)})
        return {"fraud_risk": False, "flags": []}


# =====================================================
# BULK HELPERS
# =====================================================
def resolve_customer_from_ticket(ticket: dict, ticket_id: str) -> Optional[dict]:
    """
    Resolve customer by customer_id or email.
    """
    try:
        if ticket.get("customer_id"):
            row = get_customer(ticket["customer_id"], ticket_id)
            if row:
                return row
        print(ticket,"resolve_customer_from_ticket ticket )))))))))))))))))) ")
        if ticket.get("customer_email"):
            row = lookup_by_email(ticket["customer_email"], ticket_id)
            if row:
                return row

        return None

    except Exception as e : 
        print("exception inresolve_customer_from_ticket " , str(e))
        raise e


# =====================================================
# SAFE RETRY WRAPPERS
# =====================================================
def safe_get_order(order_id: str, ticket_id: str):
    return retry_call(get_order, order_id, ticket_id=ticket_id)


def safe_get_customer(customer_id: str, ticket_id: str):
    return retry_call(get_customer, customer_id, ticket_id=ticket_id)


# =====================================================
# TEST
# =====================================================
if __name__ == "__main__":
    print("Customers:", len(CUSTOMERS))
    print("Orders:", len(ORDERS))
    print("Products:", len(PRODUCTS))