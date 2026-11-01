"""Configuration management for Central AI Runtime & API."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class APIConfig:
    """Server-side configuration for Central AI API."""

    # Provider selection: 'mock', 'ollama', 'mlx_jais', 'hosted'
    provider: str = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_PROVIDER", "mock").lower()
    )

    # Optional fallback provider when primary provider fails
    fallback_provider: Optional[str] = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_FALLBACK_PROVIDER", None)
    )

    # Active model identifier
    model: str = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_MODEL", "qwen3:4b")
    )

    # Fallback model identifier
    fallback_model: Optional[str] = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_FALLBACK_MODEL", None)
    )

    # Provider endpoints
    ollama_endpoint: str = field(
        default_factory=lambda: os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434")
    )
    mlx_endpoint: str = field(
        default_factory=lambda: os.environ.get("MLX_ENDPOINT", "http://127.0.0.1:8080/v1")
    )
    hosted_endpoint: str = field(
        default_factory=lambda: os.environ.get("HOSTED_ENDPOINT", "")
    )
    hosted_api_key: str = field(
        default_factory=lambda: os.environ.get("HOSTED_API_KEY", "")
    )

    # Central API Authentication & Authorization
    api_key: Optional[str] = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_API_KEY", None)
    )

    # Server binding
    host: str = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_HOST", "127.0.0.1")
    )
    port: int = field(
        default_factory=lambda: int(os.environ.get("CENTRAL_AI_PORT", "8000"))
    )

    # Default inference parameters
    timeout_seconds: float = field(
        default_factory=lambda: float(os.environ.get("CENTRAL_AI_TIMEOUT", "120.0"))
    )
    default_temperature: float = 0.2
    default_max_tokens: int = 1024
    default_top_p: float = 0.95

    # Concurrency and safety limits
    sequential_lock: bool = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_SEQUENTIAL_LOCK", "true").lower() == "true"
    )
    enforce_disk_limit: bool = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_ENFORCE_DISK_LIMIT", "true").lower() == "true"
    )
    min_disk_free_gb: float = field(
        default_factory=lambda: float(os.environ.get("CENTRAL_AI_MIN_DISK_FREE_GB", "15.0"))
    )

    # Cloud Traffic and Rate Limiting
    rate_limit_enabled: bool = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_RATE_LIMIT_ENABLED", "true").lower() == "true"
    )
    rate_limit_rpm: int = field(
        default_factory=lambda: int(os.environ.get("CENTRAL_AI_RATE_LIMIT_RPM", "60"))
    )
    max_concurrency: int = field(
        default_factory=lambda: int(os.environ.get("CENTRAL_AI_MAX_CONCURRENCY", "10"))
    )

    # Data & Continuous Learning Paths
    data_dir: Path = field(
        default_factory=lambda: Path(os.environ.get("CENTRAL_AI_DATA_DIR", "data"))
    )

    # Cloud Container & Production Hardening
    environment: str = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_ENV", "development").lower()
    )
    cors_origins: list[str] = field(
        default_factory=lambda: [
            orig.strip()
            for orig in os.environ.get(
                "CENTRAL_AI_CORS_ORIGINS",
                "https://ai.peregrineacademy.in,http://localhost:3000,http://localhost:3005",
            ).split(",")
            if orig.strip()
        ]
    )
    max_request_body_bytes: int = field(
        default_factory=lambda: int(os.environ.get("CENTRAL_AI_MAX_BODY_BYTES", str(2 * 1024 * 1024)))
    )
    log_format: str = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_LOG_FORMAT", "text").lower()
    )
    worker_auto_start: bool = field(
        default_factory=lambda: os.environ.get("CENTRAL_AI_WORKER_AUTO_START", "false").lower() == "true"
    )
    worker_interval_seconds: int = field(
        default_factory=lambda: int(os.environ.get("CENTRAL_AI_WORKER_INTERVAL", "300"))
    )


def get_default_config() -> APIConfig:
    """Return default configuration populated from environment."""
    return APIConfig()
