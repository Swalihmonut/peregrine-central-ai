"""OpenAI-compatible Provider Adapter for Jais MLX Server."""

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


class MLXJaisProviderAdapter(BaseProviderAdapter):
    """Adapter for local Jais 3 MLX OpenAI-compatible HTTP server."""

    def __init__(
        self,
        model_name: str = "IFM/Jais-3-3.7B-MLX-4bit",
        endpoint: str = "http://127.0.0.1:8080/v1",
        api_key: str = "EMPTY",
        timeout_seconds: float = 120.0,
    ):
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.endpoint = endpoint.rstrip("/")
        self.api_key = api_key

    @property
    def provider_name(self) -> str:
        return "mlx_jais"

    def is_ready(self) -> bool:
        """Check if Jais MLX server is up and listening."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/models", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def check_health(self) -> Dict[str, Any]:
        """Check status of MLX server endpoint."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/models", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "provider": self.provider_name,
                    "endpoint": self.endpoint,
                    "target_model": self.model_name,
                    "models_reported": data.get("data", []),
                }
        except Exception as e:
            return {
                "status": "stopped",
                "provider": self.provider_name,
                "endpoint": self.endpoint,
                "details": f"Jais MLX server is currently stopped or unreachable: {str(e)}",
            }

    def generate(
        self,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        start_time = time.perf_counter()
        url = f"{self.endpoint}/chat/completions"

        api_messages = [
            {"role": m.role.value, "content": m.content}
            for m in messages
        ]

        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "temperature": parameters.temperature,
            "max_tokens": parameters.max_tokens,
            "stream": False,
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

                choices = res_body.get("choices", [])
                if not choices:
                    return CentralAPIResponse(
                        request_id=request_id,
                        status="error",
                        content=None,
                        model=self.model_name,
                        provider=self.provider_name,
                        telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="empty"),
                        error=ErrorDetail(
                            code="EMPTY_CHOICES_PAYLOAD",
                            message="MLX server returned response with empty choices list.",
                        ),
                    )

                choice = choices[0]
                raw_content = choice.get("message", {}).get("content", "")
                finish_reason = choice.get("finish_reason", "stop")

                # Delimiter cleaning (strip any <|ifm|think>...</ifm|think> planning tags)
                clean_content = raw_content
                if "</ifm|think>" in raw_content:
                    parts = raw_content.split("</ifm|think>")
                    clean_content = parts[-1].strip()

                usage = res_body.get("usage", {})
                prompt_tokens = usage.get("prompt_tokens", 0)
                completion_tokens = usage.get("completion_tokens", 0)
                total_tokens = usage.get("total_tokens", prompt_tokens + completion_tokens)

                is_truncated = (finish_reason == "length")

                return CentralAPIResponse(
                    request_id=request_id,
                    status="success",
                    content=clean_content,
                    model=self.model_name,
                    provider=self.provider_name,
                    usage=UsageMetadata(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=total_tokens,
                    ),
                    telemetry=TelemetryMetadata(
                        latency_ms=round(latency_ms, 2),
                        finish_reason=finish_reason,
                        is_truncated=is_truncated,
                    ),
                    error=None,
                )

        except urllib.error.URLError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="connection_error"),
                error=ErrorDetail(
                    code="MLX_SERVER_UNREACHABLE",
                    message=(
                        f"Could not connect to Jais MLX server at {self.endpoint}. "
                        "Ensure the server is started with '.venv/bin/python -m mlx_lm.server --port 8080'."
                    ),
                ),
            )
        except Exception as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="runtime_error"),
                error=ErrorDetail(
                    code="MLX_INFERENCE_ERROR",
                    message=f"MLX generation failed: {type(e).__name__}: {str(e)}",
                ),
            )
