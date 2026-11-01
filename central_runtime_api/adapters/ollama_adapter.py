"""Ollama Provider Adapter with strict thinking isolation."""

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


class OllamaProviderAdapter(BaseProviderAdapter):
    """Adapter for local Ollama server, enforcing strict separation of reasoning traces."""

    def __init__(
        self,
        model_name: str = "qwen3:4b",
        endpoint: str = "http://127.0.0.1:11434",
        timeout_seconds: float = 120.0,
    ):
        super().__init__(model_name=model_name, timeout_seconds=timeout_seconds)
        self.endpoint = endpoint.rstrip("/")

    @property
    def provider_name(self) -> str:
        return "ollama"

    def is_ready(self) -> bool:
        """Check if Ollama server is responsive."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                return resp.status == 200
        except Exception:
            return False

    def check_health(self) -> Dict[str, Any]:
        """Check health and list installed tags."""
        try:
            req = urllib.request.Request(f"{self.endpoint}/api/tags", method="GET")
            with urllib.request.urlopen(req, timeout=3.0) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                models = [m.get("name") for m in data.get("models", [])]
                is_target_present = any(self.model_name in m for m in models)
                return {
                    "status": "healthy" if resp.status == 200 else "degraded",
                    "provider": self.provider_name,
                    "endpoint": self.endpoint,
                    "target_model": self.model_name,
                    "target_model_installed": is_target_present,
                    "available_models": models,
                }
        except Exception as e:
            return {
                "status": "unhealthy",
                "provider": self.provider_name,
                "endpoint": self.endpoint,
                "error": str(e),
            }

    def generate(
        self,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        start_time = time.perf_counter()
        url = f"{self.endpoint}/api/chat"

        api_messages = [
            {"role": m.role.value, "content": m.content}
            for m in messages
        ]

        payload = {
            "model": self.model_name,
            "messages": api_messages,
            "stream": True,
            "options": {
                "temperature": parameters.temperature,
                "num_predict": parameters.max_tokens,
                "top_p": parameters.top_p,
            },
        }
        if parameters.seed is not None:
            payload["options"]["seed"] = parameters.seed

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        content_parts: List[str] = []
        thinking_parts: List[str] = []
        prompt_tokens = 0
        completion_tokens = 0
        done_reason = "stop"

        try:
            with urllib.request.urlopen(req, timeout=self.timeout_seconds) as resp:
                for line in resp:
                    raw_str = line.decode("utf-8").strip()
                    if not raw_str:
                        continue
                    try:
                        chunk = json.loads(raw_str)
                    except json.JSONDecodeError:
                        continue

                    msg = chunk.get("message", {})
                    # Isolate content tokens
                    if msg.get("content"):
                        content_parts.append(msg["content"])
                    # Isolate thinking tokens internally (DO NOT expose)
                    if msg.get("thinking"):
                        thinking_parts.append(msg["thinking"])

                    if chunk.get("done"):
                        prompt_tokens = chunk.get("prompt_eval_count", 0)
                        completion_tokens = chunk.get("eval_count", 0)
                        done_reason = chunk.get("done_reason", "stop")

            latency_ms = (time.perf_counter() - start_time) * 1000
            final_content = "".join(content_parts).strip()

            # Beta Rule: If model generated only thinking tokens and zero final content, return clear error
            if not final_content:
                has_thinking = len("".join(thinking_parts).strip()) > 0
                return CentralAPIResponse(
                    request_id=request_id,
                    status="error",
                    content=None,
                    model=self.model_name,
                    provider=self.provider_name,
                    usage=UsageMetadata(
                        prompt_tokens=prompt_tokens,
                        completion_tokens=completion_tokens,
                        total_tokens=prompt_tokens + completion_tokens,
                    ),
                    telemetry=TelemetryMetadata(
                        latency_ms=round(latency_ms, 2),
                        finish_reason=done_reason,
                        is_truncated=True,
                    ),
                    error=ErrorDetail(
                        code="MODEL_REASONING_ONLY" if has_thinking else "EMPTY_MODEL_RESPONSE",
                        message=(
                            "The model exhausted its token quota inside internal reasoning and generated no final Arabic answer. "
                            "Thinking traces are withheld for safety."
                            if has_thinking else "Model returned empty completion payload."
                        ),
                        details={"done_reason": done_reason, "completion_tokens": completion_tokens},
                    ),
                )

            return CentralAPIResponse(
                request_id=request_id,
                status="success",
                content=final_content,
                model=self.model_name,
                provider=self.provider_name,
                usage=UsageMetadata(
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    total_tokens=prompt_tokens + completion_tokens,
                ),
                telemetry=TelemetryMetadata(
                    latency_ms=round(latency_ms, 2),
                    finish_reason=done_reason,
                    is_truncated=(done_reason == "length"),
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
                    code="PROVIDER_CONNECTION_FAILED",
                    message=f"Could not connect to Ollama daemon at {self.endpoint}: {e.reason}",
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
                    code="INFERENCE_FAILED",
                    message=f"Inference execution failed: {type(e).__name__}: {str(e)}",
                ),
            )
