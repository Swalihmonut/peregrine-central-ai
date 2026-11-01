"""Production ASGI 3.0 Application for Peregrine Central Arabic AI Runtime API.

Designed for high-throughput, low-latency containerized cloud deployment
under Uvicorn, Gunicorn (UvicornWorker), or any standard ASGI server.
Zero third-party web framework lock-in: pure Python, Pydantic, and async I/O.
"""

from __future__ import annotations

import hmac
import json
import logging
import time
import urllib.parse
import uuid
from typing import Any, Callable, Dict, List, Optional, Tuple

from pydantic import ValidationError

from central_runtime_api.config import APIConfig, get_default_config
from central_runtime_api.middleware.rate_limiter import RateLimiter
from central_runtime_api.schemas import (
    CentralAPIResponse,
    ChatRequest,
    ErrorDetail,
    ExamsExplainRequest,
    FeedbackSubmissionRequest,
    HealthResponse,
    ReadyResponse,
    SpeakingRespondRequest,
    TelemetryMetadata,
    TutorExplainRequest,
    UsageMetadata,
)
from central_runtime_api.services.feedback_store import FeedbackStore
from central_runtime_api.services.provider_manager import ProviderManager
from central_runtime_api.services.router import CentralAPIRouter

logger = logging.getLogger("CentralAI.ASGI")


class CentralAIASGIApp:
    """Enterprise ASGI 3.0 application implementation for Central Arabic AI API."""

    def __init__(self, config: Optional[APIConfig] = None):
        self.config = config or get_default_config()
        self.provider_manager = ProviderManager(self.config)
        self.feedback_store = FeedbackStore(self.config.data_dir)
        self.router = CentralAPIRouter(self.provider_manager, self.feedback_store)
        self.rate_limiter = RateLimiter(
            requests_per_minute=self.config.rate_limit_rpm,
            max_concurrency=self.config.max_concurrency,
            enabled=self.config.rate_limit_enabled,
        )
        self._is_shutting_down = False

    async def __call__(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        scope_type = scope.get("type")
        if scope_type == "lifespan":
            await self._handle_lifespan(scope, receive, send)
        elif scope_type == "http":
            await self._handle_http(scope, receive, send)
        else:
            # WebSocket or other scope type: reject cleanly
            pass

    async def _handle_lifespan(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        """Handle ASGI lifespan events for graceful container startup and shutdown."""
        while True:
            message = await receive()
            msg_type = message.get("type")
            if msg_type == "lifespan.startup":
                logger.info(
                    "ASGI application starting up (Provider: %s, Model: %s, Env: %s)",
                    self.config.provider,
                    self.config.model,
                    self.config.environment,
                )
                await send({"type": "lifespan.startup.complete"})
            elif msg_type == "lifespan.shutdown":
                logger.info("ASGI application received shutdown signal; draining in-flight requests...")
                self._is_shutting_down = True
                await send({"type": "lifespan.shutdown.complete"})
                return

    def _get_cors_origin(self, origin: str) -> str:
        """Check client origin against configured CORS allowlist."""
        if not origin:
            return "*"
        if "*" in self.config.cors_origins:
            return origin or "*"
        for allowed in self.config.cors_origins:
            if allowed == "*" or allowed == origin or origin.startswith(allowed):
                return origin
        if self.config.environment == "development":
            return origin
        return self.config.cors_origins[0] if self.config.cors_origins else "https://ai.peregrineacademy.in"

    def _check_auth(self, headers_dict: Dict[str, str]) -> bool:
        """Verify API key using constant-time comparison to prevent timing attacks."""
        if not self.config.api_key:
            return True
        auth_header = headers_dict.get("authorization", "")
        if not auth_header:
            return False
        parts = auth_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() in ("bearer", "apikey", "token"):
            token = parts[1].strip()
        else:
            token = auth_header.strip()
        return hmac.compare_digest(token, self.config.api_key)

    async def _handle_http(self, scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
        start_time = time.perf_counter()
        raw_path = scope.get("path", "/")
        path = raw_path.rstrip("/")
        method = scope.get("method", "GET").upper()

        # Parse headers
        headers_dict: Dict[str, str] = {}
        for k_bytes, v_bytes in scope.get("headers", []):
            headers_dict[k_bytes.decode("latin1").lower()] = v_bytes.decode("latin1")

        req_origin = headers_dict.get("origin", "")
        cors_origin = self._get_cors_origin(req_origin)
        request_id = headers_dict.get("x-request-id") or f"req-{uuid.uuid4().hex[:12]}"
        client_host = scope.get("client", ["127.0.0.1", 0])[0]

        # Extract client key for rate limiting
        auth_header = headers_dict.get("authorization", "")
        client_key = auth_header if auth_header else client_host

        # Handle CORS pre-flight OPTIONS
        if method == "OPTIONS":
            await self._send_options_response(send, cors_origin)
            return

        # Rate Limiting & Concurrency Guard
        allowed, remaining, reset_after, reason = self.rate_limiter.acquire(client_key)
        rate_headers = {
            "x-ratelimit-limit": str(self.rate_limiter.rpm),
            "x-ratelimit-remaining": str(remaining),
            "x-ratelimit-reset": str(reset_after),
        }

        if not allowed:
            await self._send_error_response(
                send,
                status=429,
                code=reason,
                message=(
                    f"Too many requests. Limit: {self.rate_limiter.rpm} requests/minute. "
                    f"Retry in {reset_after} seconds."
                ),
                request_id=request_id,
                cors_origin=cors_origin,
                extra_headers=rate_headers,
            )
            return

        try:
            # Service draining check
            if self._is_shutting_down:
                await self._send_error_response(
                    send,
                    status=503,
                    code="SERVICE_SHUTTING_DOWN",
                    message="Service is shutting down. Please retry shortly on a different instance.",
                    request_id=request_id,
                    cors_origin=cors_origin,
                    extra_headers=rate_headers,
                )
                return

            # GET Endpoints: /health, /ready
            if method == "GET":
                if path == "/health":
                    health_info = self.router.manager.check_health()
                    resp = HealthResponse(
                        status="ok",
                        version=health_info.get("version", "0.1.0-beta"),
                        active_provider=health_info.get("active_provider", self.config.provider),
                        active_model=health_info.get("active_model", self.config.model),
                    )
                    await self._send_json_response(send, 200, resp.model_dump(), request_id, cors_origin, rate_headers)
                    return

                elif path == "/ready":
                    is_ready = self.router.manager.is_ready()
                    disk_free = self.router.manager.get_disk_free_gb()
                    mem_pct = self.router.manager.get_memory_free_pct()
                    status_desc = "ready" if is_ready else "not_ready_or_provider_stopped"

                    resp = ReadyResponse(
                        ready=is_ready,
                        active_provider=self.config.provider,
                        active_model=self.config.model,
                        provider_status=status_desc,
                        disk_free_gb=disk_free,
                        memory_free_pct=mem_pct,
                        sequential_lock_idle=not self.router.manager._lock.locked(),
                    )
                    resp_dict = resp.model_dump()
                    resp_dict["feedback_metrics"] = self.feedback_store.get_queue_metrics()
                    status_code = 200 if is_ready else 503
                    await self._send_json_response(send, status_code, resp_dict, request_id, cors_origin, rate_headers)
                    return

                else:
                    await self._send_error_response(
                        send,
                        status=404,
                        code="ENDPOINT_NOT_FOUND",
                        message=f"GET endpoint '{raw_path}' not recognized on Central AI API.",
                        request_id=request_id,
                        cors_origin=cors_origin,
                        extra_headers=rate_headers,
                    )
                    return

            # POST Endpoints: Require authentication if configured
            if method == "POST":
                if not self._check_auth(headers_dict):
                    await self._send_error_response(
                        send,
                        status=401,
                        code="UNAUTHORIZED",
                        message="Authentication required. Provide a valid API key via Authorization header.",
                        request_id=request_id,
                        cors_origin=cors_origin,
                        extra_headers=rate_headers,
                    )
                    return

                # Read request body with streaming size enforcement
                body_bytes = bytearray()
                while True:
                    msg = await receive()
                    chunk = msg.get("body", b"")
                    body_bytes.extend(chunk)
                    if len(body_bytes) > self.config.max_request_body_bytes:
                        await self._send_error_response(
                            send,
                            status=413,
                            code="PAYLOAD_TOO_LARGE",
                            message=f"Request payload exceeds max limit of {self.config.max_request_body_bytes} bytes.",
                            request_id=request_id,
                            cors_origin=cors_origin,
                            extra_headers=rate_headers,
                        )
                        return
                    if not msg.get("more_body", False):
                        break

                if len(body_bytes) == 0:
                    await self._send_error_response(
                        send,
                        status=400,
                        code="EMPTY_REQUEST_BODY",
                        message="HTTP POST request body cannot be empty.",
                        request_id=request_id,
                        cors_origin=cors_origin,
                        extra_headers=rate_headers,
                    )
                    return

                try:
                    body_dict = json.loads(body_bytes.decode("utf-8"))
                except json.JSONDecodeError as jde:
                    await self._send_error_response(
                        send,
                        status=400,
                        code="INVALID_JSON",
                        message=f"Failed to parse request body as JSON: {str(jde)}",
                        request_id=request_id,
                        cors_origin=cors_origin,
                        extra_headers=rate_headers,
                    )
                    return

                if "request_id" not in body_dict:
                    body_dict["request_id"] = request_id

                # Route Dispatch
                if path == "/api/v1/chat":
                    req_obj = ChatRequest(**body_dict)
                    res = self.router.handle_chat(req_obj)
                    status_code = 200 if res.status == "success" else 500
                    await self._send_json_response(send, status_code, res.model_dump(), res.request_id, cors_origin, rate_headers)
                    return

                elif path == "/api/v1/tutor/explain":
                    req_obj = TutorExplainRequest(**body_dict)
                    res = self.router.handle_tutor_explain(req_obj)
                    status_code = 200 if res.status == "success" else 500
                    await self._send_json_response(send, status_code, res.model_dump(), res.request_id, cors_origin, rate_headers)
                    return

                elif path == "/api/v1/speaking/respond":
                    req_obj = SpeakingRespondRequest(**body_dict)
                    res = self.router.handle_speaking_respond(req_obj)
                    status_code = 200 if res.status == "success" else 500
                    await self._send_json_response(send, status_code, res.model_dump(), res.request_id, cors_origin, rate_headers)
                    return

                elif path == "/api/v1/exams/explain":
                    req_obj = ExamsExplainRequest(**body_dict)
                    res = self.router.handle_exams_explain(req_obj)
                    status_code = 200 if res.status == "success" else 500
                    await self._send_json_response(send, status_code, res.model_dump(), res.request_id, cors_origin, rate_headers)
                    return

                elif path == "/api/v1/feedback":
                    fb_req = FeedbackSubmissionRequest(**body_dict)
                    fb_res = self.router.handle_feedback(fb_req)
                    await self._send_json_response(send, 202, fb_res.model_dump(), fb_req.request_id, cors_origin, rate_headers)
                    return

                elif path == "/api/v1/feedback/consent/withdraw":
                    user_id = body_dict.get("user_id") or body_dict.get("user_id_hash") or ""
                    res = self.router.handle_withdraw_consent(user_id)
                    await self._send_json_response(send, 200, res, request_id, cors_origin, rate_headers)
                    return

                else:
                    await self._send_error_response(
                        send,
                        status=404,
                        code="ENDPOINT_NOT_FOUND",
                        message=f"POST endpoint '{raw_path}' does not exist.",
                        request_id=request_id,
                        cors_origin=cors_origin,
                        extra_headers=rate_headers,
                    )
                    return

            # Disallowed HTTP method
            await self._send_error_response(
                send,
                status=405,
                code="METHOD_NOT_ALLOWED",
                message=f"HTTP method '{method}' not allowed on endpoint '{raw_path}'.",
                request_id=request_id,
                cors_origin=cors_origin,
                extra_headers=rate_headers,
            )

        except ValidationError as val_err:
            await self._send_error_response(
                send,
                status=422,
                code="SCHEMA_VALIDATION_ERROR",
                message=f"Request schema validation failed: {str(val_err)}",
                request_id=request_id,
                cors_origin=cors_origin,
                extra_headers=rate_headers,
            )
        except Exception as exc:
            logger.exception("Unhandled server exception in ASGI request handler")
            msg = (
                f"An unhandled internal exception occurred: {type(exc).__name__}: {str(exc)}"
                if self.config.environment == "development"
                else "An internal server error occurred. Please contact support with the request ID."
            )
            await self._send_error_response(
                send,
                status=500,
                code="INTERNAL_SERVER_ERROR",
                message=msg,
                request_id=request_id,
                cors_origin=cors_origin,
                extra_headers=rate_headers,
            )
        finally:
            self.rate_limiter.release(client_key)
            latency_ms = round((time.perf_counter() - start_time) * 1000, 2)
            if self.config.log_format == "json":
                log_entry = {
                    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                    "request_id": request_id,
                    "client_ip": client_host,
                    "method": method,
                    "path": raw_path,
                    "latency_ms": latency_ms,
                }
                print(json.dumps(log_entry))

    async def _send_json_response(
        self,
        send: Callable,
        status: int,
        payload: Dict[str, Any],
        request_id: str,
        cors_origin: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send formatted JSON HTTP response via ASGI send callable."""
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(body)).encode("ascii")),
            (b"access-control-allow-origin", cors_origin.encode("utf-8")),
            (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
            (b"access-control-allow-headers", b"Content-Type, Authorization, X-Request-ID"),
            (b"vary", b"Origin"),
            (b"x-request-id", request_id.encode("utf-8")),
        ]
        if extra_headers:
            for k, v in extra_headers.items():
                headers.append((k.lower().encode("ascii"), str(v).encode("utf-8")))

        await send({"type": "http.response.start", "status": status, "headers": headers})
        await send({"type": "http.response.body", "body": body})

    async def _send_options_response(self, send: Callable, cors_origin: str) -> None:
        """Respond to CORS preflight with HTTP 204 No Content."""
        headers = [
            (b"access-control-allow-origin", cors_origin.encode("utf-8")),
            (b"access-control-allow-methods", b"GET, POST, OPTIONS"),
            (b"access-control-allow-headers", b"Content-Type, Authorization, X-Request-ID"),
            (b"vary", b"Origin"),
            (b"content-length", b"0"),
        ]
        await send({"type": "http.response.start", "status": 204, "headers": headers})
        await send({"type": "http.response.body", "body": b""})

    async def _send_error_response(
        self,
        send: Callable,
        status: int,
        code: str,
        message: str,
        request_id: str,
        cors_origin: str,
        extra_headers: Optional[Dict[str, str]] = None,
    ) -> None:
        """Send standardized JSON error envelope via ASGI."""
        resp = CentralAPIResponse(
            request_id=request_id,
            status="error",
            content=None,
            model=self.config.model,
            provider=self.config.provider,
            usage=UsageMetadata(),
            telemetry=TelemetryMetadata(finish_reason="error"),
            error=ErrorDetail(code=code, message=message),
        )
        await self._send_json_response(send, status, resp.model_dump(), request_id, cors_origin, extra_headers)


# Lazy application singleton for Uvicorn: uvicorn central_runtime_api.asgi:app
_default_app: Optional[CentralAIASGIApp] = None


def get_app() -> CentralAIASGIApp:
    global _default_app
    if _default_app is None:
        _default_app = CentralAIASGIApp()
    return _default_app


async def app(scope: Dict[str, Any], receive: Callable, send: Callable) -> None:
    application = get_app()
    await application(scope, receive, send)
