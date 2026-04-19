from __future__ import annotations

from typing import Dict, Any, Optional

from src.logger import (
    audit_event,
    audit_reasoning,
    audit_decision,
    log_error,
)
from src.tools import (
    get_orders_by_customer,
    resolve_customer_from_ticket,
    get_order,
    get_product,
    check_refund_eligibility,
    check_return_window,
    check_warranty,
    detect_fraud,
)
from src.kb import get_kb_context
from src.policy import (
    evaluate_ticket,
    critic_review,
)
from src.llm import generate_response
from src.utils import confidence_from_signals, sanitize_text


class SupportAgent:
    """
    Main production support agent.
    Deterministic logic first, LLM second.
    """

    def __init__(self):
        self.name = "ShopWave Support Agent v1"

   
    def process_ticket(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        ticket_id = str(ticket.get("ticket_id", "UNKNOWN"))

        try:
            audit_event(ticket_id, "ticket_received", "ok", ticket)

           
            ticket = self._normalize_ticket(ticket)

            # -----------------------------------------
            # Load customer
            # -----------------------------------------
            customer = resolve_customer_from_ticket(ticket, ticket_id)
            print(customer , "customer *************** ")
            # -----------------------------------------
            # Load order
            # -----------------------------------------
            order = self._resolve_order(ticket, customer, ticket_id)
            print(order , "order ******************************** ")
            # -----------------------------------------
            # Load product
            # -----------------------------------------
            product = self._resolve_product(order, ticket_id)
            print(product , " product ************************")
            # -----------------------------------------
            # Run tools
            # -----------------------------------------
            tool_outputs = self._run_tools(
                ticket=ticket,
                customer=customer,
                order=order,
                product=product,
                ticket_id=ticket_id
            )

            # -----------------------------------------
            # Knowledge base retrieval
            # -----------------------------------------
            kb_context = get_kb_context(ticket["message"], top_k=3)

            # -----------------------------------------
            # Policy engine
            # -----------------------------------------
            policy_result = evaluate_ticket(
                ticket=ticket,
                customer=customer,
                order=order,
                product=product,
                tool_outputs=tool_outputs
            )

            # -----------------------------------------
            # Critic pass
            # -----------------------------------------
            critic = critic_review(policy_result)

            if not critic["passed"]:
                policy_result["decision"] = critic["override_decision"]
                policy_result["reason"] += " | Critic override"

            # -----------------------------------------
            # Confidence score
            # -----------------------------------------
            confidence = self._score_confidence(
                policy_result=policy_result,
                tool_outputs=tool_outputs
            )

            # -----------------------------------------
            # LLM final response
            # -----------------------------------------
            llm_output = generate_response(
                ticket=ticket,
                policy_result=policy_result,
                kb_context=kb_context,
                tool_context=tool_outputs
            )

            # -----------------------------------------
            # Reasoning log
            # -----------------------------------------
            audit_reasoning(
                ticket_id,
                policy_result.get("reason", ""),
                confidence
            )

            # -----------------------------------------
            # Final payload
            # -----------------------------------------
            result = {
                "ticket_id": ticket_id,
                "decision": policy_result["decision"],
                "reason": policy_result["reason"],
                "priority": policy_result.get("priority", "medium"),
                "requires_human": policy_result.get("requires_human", False),
                "confidence": confidence,
                "summary": llm_output["summary"],
                "customer_reply": llm_output["customer_reply"],
                "tool_outputs": tool_outputs,
                "critic_comment": critic["comment"],
            }

            audit_decision(
                ticket_id,
                result["decision"],
                confidence,
                result["customer_reply"]
            )

            return result

        except Exception as e:
            log_error("process_ticket_failed", {
                "ticket_id": ticket_id,
                "error": str(e)
            })

            fail_result = {
                "ticket_id": ticket_id,
                "decision": "ESCALATE",
                "reason": "System exception during processing",
                "priority": "high",
                "requires_human": True,
                "confidence": 0.20,
                "summary": "Unhandled processing exception.",
                "customer_reply":
                    "Your request needs manual review. Our support team will contact you shortly."
            }

            audit_decision(
                ticket_id,
                "ESCALATE",
                0.20,
                fail_result["customer_reply"]
            )

            return fail_result

    # =================================================
    # HELPERS
    # =================================================
    def _normalize_ticket(self, ticket: dict) -> dict:
        ticket["message"] = sanitize_text(ticket.get("body", ""))
        return ticket
 

    def _resolve_order(
    self,
    ticket: dict,
    customer: Optional[dict],
    ticket_id: str
    ):
        order_id = ticket.get("order_id")

        # 1. Direct order_id in ticket (best case)
        if order_id:
            return get_order(order_id, ticket_id)

        # 2. Try from expected_action or body (optional future NLP hook)
        # (you can extend later)

        # 3. fallback → customer_id → fetch ALL orders
        if customer:
            customer_id = customer.get("customer_id")

            # IMPORTANT: you MUST have a function like this
            orders = get_orders_by_customer(customer_id)

            if not orders:
                return None

            # if single order → use it
            if len(orders) == 1:
                return orders[0]

            # if multiple → choose latest delivered or latest order_date
            orders_sorted = sorted(
                orders,
                key=lambda x: x.get("delivery_date") or x.get("order_date"),
                reverse=True
            )

            return orders_sorted[0]

        return None
    # def _resolve_order(
    #     self,
    #     ticket: dict,
    #     customer: Optional[dict],
    #     ticket_id: str
    # ):
    #     order_id = ticket.get("order_id")

    #     if not order_id and customer:
    #         order_id = customer.get("customer_id")

    #     if not order_id:
    #         return None
    #     print("customer_id )))))))" , order_id)
    #     return get_order(order_id, ticket_id)

    def _resolve_product(
        self,
        order: Optional[dict],
        ticket_id: str
    ):
        if not order:
            return None

        product_id = order.get("product_id")

        if not product_id:
            return None

        return get_product(product_id, ticket_id)

    def _run_tools(
        self,
        ticket: dict,
        customer: Optional[dict],
        order: Optional[dict],
        product: Optional[dict],
        ticket_id: str
    ) -> dict:

        outputs = {}

        try:
            outputs["fraud"] = detect_fraud(ticket, customer, ticket_id)
        except Exception:
            outputs["fraud"] = {}

        try:
            if order and product: 
                print(order , product , "check_refund_eligibility agents )))))))))))))))))))))))))))")
                outputs["refund"] = check_refund_eligibility(
                    order, product, ticket_id
                )
        except Exception:
            outputs["refund"] = {}

        try:
            if order and product:
                outputs["return_window"] = check_return_window(
                    order.get("delivery_date", ""),
                    product.get("category", ""),
                    ticket_id,
                    order.get("order_date", ""),
                    order
                )
        except Exception:
            outputs["return_window"] = {}

        try:
            if order and product:
                outputs["warranty"] = check_warranty(
                    order, product, ticket_id
                )
        except Exception:
            outputs["warranty"] = {}

        return outputs

    def _score_confidence(
        self,
        policy_result: dict,
        tool_outputs: dict
    ) -> float:

        tool_count = len(tool_outputs)
        success_count = len([
            x for x in tool_outputs.values()
            if isinstance(x, dict) and x != {}
        ])

        ratio = success_count / tool_count if tool_count else 0.5

        conflict = policy_result["decision"] == "ESCALATE"
        fraud = policy_result["decision"] == "FLAG_FRAUD"

        return confidence_from_signals(
            matched_policy=True,
            tool_success_ratio=ratio,
            conflicting_data=conflict,
            llm_parse_ok=True,
            fraud_risk=fraud
        )