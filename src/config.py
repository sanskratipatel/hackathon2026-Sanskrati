# MAX_RETRIES = 3
# CONFIDENCE_THRESHOLD = 0.60
# REFUND_ESCALATE_AMOUNT = 200
# CONCURRENT_WORKERS = 10 

from __future__ import annotations

import os
from pathlib import Path
from functools import lru_cache
from typing import Literal, Optional

from dotenv import load_dotenv
from pydantic import BaseModel, Field, ValidationError


ROOT_DIR = Path(__file__).resolve().parent.parent
ENV_PATH = ROOT_DIR / ".env"

if ENV_PATH.exists():
    load_dotenv(ENV_PATH)
else:
    load_dotenv()


class Settings(BaseModel):
    # Environment
    env: Literal["dev", "prod", "test"] = "dev"
    log_level: str = "INFO"

    # Providers
    groq_api_key: Optional[str] = None
    openrouter_api_key: Optional[str] = None
    together_api_key: Optional[str] = None
    ollama_base_url: str = "http://localhost:11434"

    # Model
    model_name: str = "llama3-8b-8192"
    fallback_model_name: str = "mixtral-8x7b"

    # Reliability
    request_timeout: int = 20
    max_retries: int = 3

    # Agent thresholds
    confidence_threshold: float = 0.60
    auto_approve_threshold: float = 0.85
    refund_escalate_amount: float = 200.0

    # Runtime
    max_workers: int = 8
    enable_critic_pass: bool = True
    enable_explanation_trace: bool = True

    # UI
    dark_mode_default: bool = True

    # Paths
    root_dir: Path = ROOT_DIR
    data_dir: Path = ROOT_DIR / "data"
    src_dir: Path = ROOT_DIR / "src"
    output_dir: Path = ROOT_DIR / "outputs"

    tickets_file: Path = ROOT_DIR / "data" / "tickets.json"
    orders_file: Path = ROOT_DIR / "data" / "orders.json"
    customers_file: Path = ROOT_DIR / "data" / "customers.json"
    products_file: Path = ROOT_DIR / "data" / "products.json"

    results_file: Path = ROOT_DIR / "outputs" / "results.json"
    audit_log_file: Path = ROOT_DIR / "audit_log.json"

    # Security
    max_ticket_chars: int = 5000
    allow_html_render: bool = False


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _build_settings() -> Settings:
    try:
        settings = Settings(
            env=os.getenv("ENV", "dev"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),

            groq_api_key=os.getenv("GROQ_API_KEY"),
            openrouter_api_key=os.getenv("OPENROUTER_API_KEY"),
            together_api_key=os.getenv("TOGETHER_API_KEY"),
            ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://localhost:11434"),

            model_name=os.getenv("MODEL_NAME", "llama3-8b-8192"),
            fallback_model_name=os.getenv("FALLBACK_MODEL_NAME", "mixtral-8x7b"),

            request_timeout=int(os.getenv("REQUEST_TIMEOUT", "20")),
            max_retries=int(os.getenv("MAX_RETRIES", "3")),

            confidence_threshold=float(os.getenv("CONFIDENCE_THRESHOLD", "0.60")),
            auto_approve_threshold=float(os.getenv("AUTO_APPROVE_THRESHOLD", "0.85")),
            refund_escalate_amount=float(os.getenv("REFUND_ESCALATE_AMOUNT", "200")),

            max_workers=int(os.getenv("max_workers", "8")),
            enable_critic_pass=_bool_env("ENABLE_CRITIC_PASS", True),
            enable_explanation_trace=_bool_env("ENABLE_EXPLANATION_TRACE", True),

            dark_mode_default=_bool_env("DARK_MODE_DEFAULT", True),
        )

        # Ensure directories exist
        settings.output_dir.mkdir(parents=True, exist_ok=True)
        settings.data_dir.mkdir(parents=True, exist_ok=True)

        return settings

    except ValidationError as e:
        raise RuntimeError(f"Invalid configuration: {e}") from e
    except Exception as e:
        raise RuntimeError(f"Failed loading config: {e}") from e



@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return _build_settings()


settings = get_settings()


def provider_available() -> str:
    """
    Select best available LLM provider in priority order.
    """
    if settings.groq_api_key:
        return "groq"
    if settings.openrouter_api_key:
        return "openrouter"
    if settings.together_api_key:
        return "together"
    return "ollama"


def is_prod() -> bool:
    return settings.env == "prod"


def is_dev() -> bool:
    return settings.env == "dev"

if __name__ == "__main__":
    print("Loaded config successfully")
    print("Environment:", settings.env)
    print("Provider:", provider_available())
    print("Model:", settings.model_name)