"""Provider Manager ensuring safe, sequential inference dispatch and resource guards."""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger("CentralAI.ProviderManager")

from central_runtime_api.adapters.base import BaseProviderAdapter
from central_runtime_api.adapters.hosted_adapter import HostedProviderAdapter
from central_runtime_api.adapters.mlx_adapter import MLXJaisProviderAdapter
from central_runtime_api.adapters.mock_adapter import MockProviderAdapter
from central_runtime_api.adapters.ollama_adapter import OllamaProviderAdapter
from central_runtime_api.config import APIConfig
from central_runtime_api.schemas import (
    CentralAPIResponse,
    ChatMessage,
    ErrorDetail,
    GenerationParameters,
    TelemetryMetadata,
)


class ProviderManager:
    """Manages adapter lifecycle, enforcing mutual exclusion, fallback, and resource safety."""

    def __init__(self, config: APIConfig):
        self.config = config
        self._lock = threading.Lock()
        self.adapter = self._initialize_adapter(config.provider, config.model)
        self.fallback_adapter: Optional[BaseProviderAdapter] = None
        if config.fallback_provider:
            self.fallback_adapter = self._initialize_adapter(
                config.fallback_provider,
                config.fallback_model or config.model,
            )

    def _initialize_adapter(self, provider_type: str, model_name: Optional[str] = None) -> BaseProviderAdapter:
        p = provider_type.lower()
        model = model_name or self.config.model
        if p == "ollama":
            return OllamaProviderAdapter(
                model_name=model,
                endpoint=self.config.ollama_endpoint,
                timeout_seconds=self.config.timeout_seconds,
            )
        elif p == "mlx_jais" or p == "mlx":
            return MLXJaisProviderAdapter(
                model_name=model,
                endpoint=self.config.mlx_endpoint,
                timeout_seconds=self.config.timeout_seconds,
            )
        elif p == "hosted":
            return HostedProviderAdapter(
                model_name=model,
                endpoint=self.config.hosted_endpoint,
                api_key=self.config.hosted_api_key,
                timeout_seconds=self.config.timeout_seconds,
            )
        else:
            return MockProviderAdapter(
                model_name=model,
                timeout_seconds=self.config.timeout_seconds,
            )

    def set_provider(self, provider_type: str, model_name: Optional[str] = None):
        """Dynamically switch active provider (e.g. for testing or controlled deployment)."""
        with self._lock:
            self.config.provider = provider_type.lower()
            if model_name:
                self.config.model = model_name
            self.adapter = self._initialize_adapter(self.config.provider, self.config.model)

    def set_fallback_provider(self, provider_type: Optional[str], model_name: Optional[str] = None):
        """Dynamically configure fallback provider."""
        with self._lock:
            self.config.fallback_provider = provider_type.lower() if provider_type else None
            if model_name:
                self.config.fallback_model = model_name
            if self.config.fallback_provider:
                self.fallback_adapter = self._initialize_adapter(
                    self.config.fallback_provider,
                    self.config.fallback_model or self.config.model,
                )
            else:
                self.fallback_adapter = None

    def get_disk_free_gb(self) -> float:
        """Inspect available space on host volume."""
        try:
            total, used, free = shutil.disk_usage("/System/Volumes/Data")
            return round(free / (1024 ** 3), 2)
        except Exception:
            try:
                total, used, free = shutil.disk_usage("/")
                return round(free / (1024 ** 3), 2)
            except Exception:
                return 999.0

    def get_memory_free_pct(self) -> Optional[float]:
        """Query kernel memory pressure free percentage if available."""
        try:
            res = subprocess.run(
                ["memory_pressure"],
                capture_output=True,
                text=True,
                timeout=2.0,
            )
            for line in res.stdout.splitlines():
                if "free percentage:" in line:
                    parts = line.split("free percentage:")
                    val = parts[-1].replace("%", "").strip()
                    return float(val)
        except Exception:
            pass
        return None

    def _dispatch_under_lock(
        self,
        adapter: BaseProviderAdapter,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        """Execute adapter generation respecting sequential hardware lock."""
        if self.config.sequential_lock:
            with self._lock:
                return adapter.generate(messages, parameters, request_id)
        else:
            return adapter.generate(messages, parameters, request_id)

    def execute_inference(
        self,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        """Execute inference through active adapter with resource guard, empty-output detection, and provider fallback."""
        # 1. Resource safety guard
        if self.config.enforce_disk_limit:
            disk_free = self.get_disk_free_gb()
            if disk_free < self.config.min_disk_free_gb:
                return CentralAPIResponse(
                    request_id=request_id,
                    status="error",
                    content=None,
                    model=self.config.model,
                    provider=self.adapter.provider_name,
                    telemetry=TelemetryMetadata(finish_reason="safety_abort"),
                    error=ErrorDetail(
                        code="DISK_SAFETY_THRESHOLD_BREACHED",
                        message=(
                            f"Execution aborted: Available disk space ({disk_free} GB) is below "
                            f"the mandatory safety threshold ({self.config.min_disk_free_gb} GB)."
                        ),
                        details={"disk_free_gb": disk_free, "threshold_gb": self.config.min_disk_free_gb},
                    ),
                )

        # 2. Dispatch to primary adapter
        try:
            resp = self._dispatch_under_lock(self.adapter, messages, parameters, request_id)
        except Exception as exc:
            logger.exception("Exception during primary adapter execution: %s", exc)
            resp = CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.config.model,
                provider=self.adapter.provider_name,
                telemetry=TelemetryMetadata(finish_reason="exception"),
                error=ErrorDetail(
                    code="PROVIDER_ERROR",
                    message=f"Primary provider execution failed: {type(exc).__name__}: {str(exc)}",
                ),
            )

        # 3. Detect empty or whitespace model response
        if resp.status == "success" and (resp.content is None or not resp.content.strip()):
            resp = CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=resp.model,
                provider=resp.provider,
                usage=resp.usage,
                telemetry=TelemetryMetadata(finish_reason="empty_output"),
                error=ErrorDetail(
                    code="EMPTY_MODEL_RESPONSE",
                    message="Model concluded without returning valid content.",
                ),
            )

        # 4. Fallback dispatch if primary failed and fallback adapter configured
        if resp.status == "error" and self.fallback_adapter is not None:
            primary_code = resp.error.code if resp.error else "UNKNOWN_ERROR"
            logger.warning(
                "Primary provider '%s' failed with '%s'. Attempting fallback to '%s'.",
                self.adapter.provider_name,
                primary_code,
                self.fallback_adapter.provider_name,
            )
            try:
                fb_resp = self._dispatch_under_lock(self.fallback_adapter, messages, parameters, request_id)
                # Check if fallback produced valid output
                if fb_resp.status == "success" and (fb_resp.content is not None and fb_resp.content.strip()):
                    return fb_resp
                elif fb_resp.status == "error":
                    logger.warning("Fallback provider also failed with '%s'.", fb_resp.error.code if fb_resp.error else "UNKNOWN")
            except Exception as fb_exc:
                logger.error("Exception during fallback adapter execution: %s", fb_exc)

        return resp

    def check_health(self) -> Dict[str, Any]:
        """Aggregate system and provider health status."""
        health = {
            "version": "0.1.0-beta",
            "active_provider": self.adapter.provider_name,
            "active_model": self.config.model,
            "provider_health": self.adapter.check_health(),
            "disk_free_gb": self.get_disk_free_gb(),
            "memory_free_pct": self.get_memory_free_pct(),
            "sequential_lock_active": self._lock.locked(),
        }
        if self.fallback_adapter:
            health["fallback_provider"] = self.fallback_adapter.provider_name
            health["fallback_model"] = self.config.fallback_model or self.config.model
        return health

    def is_ready(self) -> bool:
        """Return True if system is ready to accept requests."""
        if self.config.enforce_disk_limit and self.get_disk_free_gb() < self.config.min_disk_free_gb:
            return False
        return self.adapter.is_ready()
