"""Hosted Provider Adapter interface for future cloud/remote inference engines."""

from __future__ import annotations

import json
import time
from typing import Any, Dict, List
import urllib.error
import urllib.request

from central_runtime_api.adapters.base import BaseProviderAdapter
from central_runtime_api.schemas import (
    CentralAPIResponse,
    ChatMessage,
    ErrorDetail,
    GenerationParameters,
    TelemetryMetadata,
    UsageMetadata,
)


class HostedProviderAdapter(BaseProviderAdapter):
    """Adapter for remote hosted models (e.g. HUMAIN Node, OpenAI, Anthropic, or remote vLLM endpoints)."""

    def __init__(
        self,
        model_name: str = "hosted-arabic-v1",
        endpoint: str = "",
        api_key: str = "",
        timeout_seconds: float = 60.0,
    ):
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key

    @property
    def provider_name(self) -> str:
        return "hosted"

    def is_ready(self) -> bool:
        """Check if endpoint and credentials are configured."""
        return bool(self.endpoint and self.api_key)

    def check_health(self) -> Dict[str, Any]:
        """Check configuration state for hosted engine."""
        configured = self.is_ready()
        return {
            "status": "configured" if configured else "unconfigured",
            "provider": self.provider_name,
            "endpoint": self.endpoint if self.endpoint else "NOT_SET",
            "api_key_configured": bool(self.api_key),
            "target_model": self.model_name,
        }

    def generate(
        self,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        start_time = time.perf_counter()

        if not self.is_ready():
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="configuration_error"),
                error=ErrorDetail(
                    code="HOSTED_ENDPOINT_NOT_CONFIGURED",
                    message="Hosted provider endpoint or API key is not configured. Set HOSTED_ENDPOINT and HOSTED_API_KEY.",
                ),
            )

        url = f"{self.endpoint}/chat/completions"
        api_messages = [{"role": m.role.value, "content": m.content} for m in messages]
        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "temperature": parameters.temperature,
            "max_tokens": parameters.max_tokens,
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST",
        )

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                latency_ms = (time.perf_counter() - start_time) * 1000
                res_body = json.loads(resp.read().decode("utf-8"))
                choice = res_body.get("choices", [{}])[0]
                content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")

                usage = res_body.get("usage", {})
                return CentralAPIResponse(
                    request_id=request_id,
                    status="success",
                    content=content,
                    model=self.model_name,
                    provider=self.provider_name,
                    usage=UsageMetadata(
                        prompt_tokens=usage.get("prompt_tokens", 0),
                        completion_tokens=usage.get("completion_tokens", 0),
                        total_tokens=usage.get("total_tokens", 0),
                    ),
                    telemetry=TelemetryMetadata(
                        latency_ms=round(latency_ms, 2),
                        finish_reason=finish_reason,
                        is_truncated=(finish_reason == "length"),
                    ),
                    error=None,
                )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="network_error"),
                error=ErrorDetail(
                    code="HOSTED_CALL_FAILED",
                    message=f"Hosted provider call failed: {str(e)}",
                ),
            )
