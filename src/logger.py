from __future__ import annotations

import json
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

from src.config import settings


# =====================================================
# Thread-safe in-memory audit collector
# =====================================================
_AUDIT_LOCK = Lock()
_AUDIT_BUFFER: List[Dict[str, Any]] = []


# =====================================================
# Helpers
# =====================================================
def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def safe_json(data: Any) -> Any:
    """
    Ensure all values are JSON serializable.
    """
    try:
        json.dumps(data)
        return data
    except Exception:
        return str(data)


# =====================================================
# Logging setup
# =====================================================
def _build_logger() -> logging.Logger:
    logger = logging.getLogger("shopwave_agent")

    if logger.handlers:
        return logger

    logger.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))

    logs_dir = settings.output_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)

    log_file = logs_dir / "app.log"

    file_handler = RotatingFileHandler(
        filename=log_file,
        maxBytes=2_000_000,
        backupCount=5,
        encoding="utf-8"
    )

    console_handler = logging.StreamHandler()

    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    file_handler.setFormatter(formatter)
    console_handler.setFormatter(formatter)

    logger.addHandler(file_handler)
    logger.addHandler(console_handler)

    logger.propagate = False
    return logger


logger = _build_logger()


# =====================================================
# Standard Logs
# =====================================================
def log_info(message: str, extra: Optional[dict] = None) -> None:
    try:
        payload = f"{message} | {safe_json(extra)}" if extra else message
        logger.info(payload)
    except Exception:
        pass


def log_warning(message: str, extra: Optional[dict] = None) -> None:
    try:
        payload = f"{message} | {safe_json(extra)}" if extra else message
        logger.warning(payload)
    except Exception:
        pass


def log_error(message: str, extra: Optional[dict] = None) -> None:
    try:
        payload = f"{message} | {safe_json(extra)}" if extra else message
        logger.error(payload)
    except Exception:
        pass


# =====================================================
# Audit Logs (Per Ticket Trace)
# =====================================================
def audit_event(
    ticket_id: str,
    step: str,
    status: str,
    data: Optional[dict] = None
) -> None:
    """
    Add structured trace event.
    """
    try:
        event = {
            "timestamp": utc_now(),
            "ticket_id": str(ticket_id),
            "step": step,
            "status": status,
            "data": safe_json(data or {})
        }
        print(event , "event")
        with _AUDIT_LOCK:
            _AUDIT_BUFFER.append(event)

    except Exception as e:
        log_error("audit_event_failed", {"error": str(e)})


def audit_tool_call(
    ticket_id: str,
    tool_name: str,
    inputs: Optional[dict] = None,
    outputs: Optional[dict] = None,
    success: bool = True
) -> None: 
    print(ticket_id , tool_name , "&&&&&&&&&&&&&&&&&&&")
    audit_event(
        ticket_id=ticket_id,
        step=f"tool:{tool_name}",
        status="success" if success else "failed",
        data={
            "inputs": inputs or {},
            "outputs": outputs or {}
        }
    )


def audit_reasoning(
    ticket_id: str,
    explanation: str,
    confidence: float
) -> None:
    audit_event(
        ticket_id=ticket_id,
        step="reasoning",
        status="ok",
        data={
            "explanation": explanation,
            "confidence": round(float(confidence), 3)
        }
    )


def audit_decision(
    ticket_id: str,
    decision: str,
    confidence: float,
    response: str
) -> None:
    audit_event(
        ticket_id=ticket_id,
        step="final_decision",
        status=decision,
        data={
            "confidence": round(float(confidence), 3),
            "response": response
        }
    )


# =====================================================
# Persist audit logs
# =====================================================
def save_audit_log(path: Optional[Path] = None) -> None:
    try:
        output_path = path or settings.audit_log_file

        with _AUDIT_LOCK:
            data = list(_AUDIT_BUFFER)

        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        log_info("audit_log_saved", {"path": str(output_path), "events": len(data)})

    except Exception as e:
        log_error("save_audit_log_failed", {"error": str(e)})


def load_audit_log(path: Optional[Path] = None) -> List[Dict[str, Any]]:
    try:
        target = path or settings.audit_log_file
        if not target.exists():
            return []

        with open(target, "r", encoding="utf-8") as f:
            return json.load(f)

    except Exception as e:
        log_error("load_audit_log_failed", {"error": str(e)})
        return []


# =====================================================
# Metrics
# =====================================================
def summarize_audit() -> Dict[str, Any]:
    try:
        with _AUDIT_LOCK:
            rows = list(_AUDIT_BUFFER)

        tickets = {x["ticket_id"] for x in rows}
        decisions = [x for x in rows if x["step"] == "final_decision"]
        escalated = [x for x in decisions if x["status"] == "ESCALATE"]

        return {
            "events": len(rows),
            "tickets": len(tickets),
            "decisions": len(decisions),
            "escalated": len(escalated)
        }

    except Exception as e:
        log_error("summarize_audit_failed", {"error": str(e)})
        return {}


# =====================================================
# Manual Test
# =====================================================
if __name__ == "__main__":
    log_info("logger_initialized")

    audit_event("T1001", "received", "ok", {"msg": "refund request"})
    audit_tool_call("T1001", "get_order", {"order_id": "O1"}, {"found": True})
    audit_reasoning("T1001", "Eligible under return policy", 0.91)
    audit_decision("T1001", "APPROVED", 0.91, "Refund approved.")

    save_audit_log()

    print(summarize_audit())