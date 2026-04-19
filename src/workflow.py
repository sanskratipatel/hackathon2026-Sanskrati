from __future__ import annotations
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, List
from src.agent import SupportAgent
from src.logger import log_info, log_error
from src.utils import safe_read_json, safe_write_json
from src.config import settings


class TicketWorkflow:
    """
    Batch orchestration layer.
    Handles concurrent processing of all tickets.
    """

    def __init__(self):
        self.agent = SupportAgent()

    # =================================================
    # SINGLE TICKET
    # =================================================
    def run_one(self, ticket: Dict[str, Any]) -> Dict[str, Any]:
        try:
            return self.agent.process_ticket(ticket)
        except Exception as e:
            log_error("workflow_run_one_failed", {"error": str(e)})
            return {
                "ticket_id": ticket.get("ticket_id", "UNKNOWN"),
                "decision": "ESCALATE",
                "reason": "Workflow execution failed",
                "confidence": 0.10,
                "requires_human": True
            }

    # =================================================
    # BATCH MODE (IMPORTANT FOR HACKATHON)
    # =================================================
    def run_batch(
        self,
        tickets: List[Dict[str, Any]],
        max_workers: int = 5
    ) -> List[Dict[str, Any]]:

        results = []

        if not tickets:
            return results

        try:
            with ThreadPoolExecutor(max_workers=max_workers) as executor:
                future_map = {
                    executor.submit(self.run_one, ticket): ticket
                    for ticket in tickets
                }

                for future in as_completed(future_map):
                    try:
                        result = future.result()
                        results.append(result)

                    except Exception as e:
                        log_error(
                            "future_ticket_failed",
                            {"error": str(e)}
                        )

            return results

        except Exception as e:
            log_error("workflow_batch_failed", {"error": str(e)})
            return results

    # =================================================
    # FILE MODE
    # =================================================
    def run_from_file(self) -> List[Dict[str, Any]]:
        try:
            tickets = safe_read_json(settings.tickets_file, [])

            log_info("tickets_loaded", {"count": len(tickets)})

            results = self.run_batch(
                tickets=tickets,
                max_workers=settings.max_workers
            )

            safe_write_json(settings.results_file, results)

            log_info("results_saved", {"count": len(results)})

            return results

        except Exception as e:
            log_error("run_from_file_failed", {"error": str(e)})
            return []

    # =================================================
    # DASHBOARD METRICS
    # =================================================
    def metrics(self, results: List[Dict[str, Any]]) -> Dict[str, Any]:
        try:
            total = len(results)

            if total == 0:
                return {
                    "total": 0,
                    "approved": 0,
                    "denied": 0,
                    "escalated": 0,
                    "avg_confidence": 0
                }

            approved = len([
                r for r in results
                if r.get("decision") == "APPROVED"
            ])

            denied = len([
                r for r in results
                if r.get("decision") == "DENIED"
            ])

            escalated = len([
                r for r in results
                if r.get("decision") in ["ESCALATE", "FLAG_FRAUD"]
            ])

            avg_conf = round(
                sum(r.get("confidence", 0) for r in results) / total,
                2
            )

            return {
                "total": total,
                "approved": approved,
                "denied": denied,
                "escalated": escalated,
                "avg_confidence": avg_conf
            }

        except Exception:
            return {
                "total": 0,
                "approved": 0,
                "denied": 0,
                "escalated": 0,
                "avg_confidence": 0
            }


# =====================================================
# GLOBAL INSTANCE
# =====================================================

workflow = TicketWorkflow()


# =====================================================
# TEST
# =====================================================

if __name__ == "__main__":
    rows = workflow.run_from_file()
    print("Processed:", len(rows))