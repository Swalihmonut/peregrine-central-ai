"""Central AI HTTP Server implementing REST endpoints for Arabic AI applications."""

from __future__ import annotations

import hmac
import json
import logging
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, Dict, Optional
import urllib.parse

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

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("CentralAI.Server")


class CentralAPIRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request handler for Central AI Runtime API."""

    router: CentralAPIRouter
    config: APIConfig
    rate_limiter: RateLimiter

    def _check_auth(self) -> bool:
        """Verify API key when configured in APIConfig with timing attack resistance."""
        if not self.config.api_key:
            return True
        auth_header = self.headers.get("Authorization", "")
        if not auth_header:
            return False
        parts = auth_header.split(None, 1)
        if len(parts) == 2 and parts[0].lower() in ("bearer", "apikey", "token"):
            token = parts[1].strip()
        else:
            token = auth_header.strip()
        return hmac.compare_digest(token, self.config.api_key)

    def _get_cors_origin(self) -> str:
        """Evaluate origin against configured CORS allowlist."""
        req_origin = self.headers.get("Origin", "")
        if not req_origin:
            return "*"
        if "*" in self.config.cors_origins:
            return req_origin or "*"
        for allowed in self.config.cors_origins:
            if allowed == "*" or allowed == req_origin or req_origin.startswith(allowed):
                return req_origin
        if self.config.environment == "development":
            return req_origin
        return self.config.cors_origins[0] if self.config.cors_origins else "https://ai.peregrineacademy.in"

    def _send_json_response(
        self,
        status_code: int,
        payload: Dict[str, Any],
        request_id: Optional[str] = None,
        rate_limit_headers: Optional[Dict[str, str]] = None,
    ):
        """Send formatted JSON HTTP response with standard headers."""
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        cors_origin = self._get_cors_origin()
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
        if request_id:
            self.send_header("X-Request-ID", request_id)
        if rate_limit_headers:
            for k, v in rate_limit_headers.items():
                self.send_header(k, str(v))
        self.end_headers()
        self.wfile.write(data)

    def _send_error(
        self,
        status_code: int,
        code: str,
        message: str,
        request_id: str = "req-err",
        rate_limit_headers: Optional[Dict[str, str]] = None,
    ):
        """Send standardized JSON error envelope."""
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
        self._send_json_response(status_code, resp.model_dump(), request_id, rate_limit_headers)

    def do_OPTIONS(self):
        """Handle CORS pre-flight requests."""
        cors_origin = self._get_cors_origin()
        self.send_response(HTTPStatus.NO_CONTENT)
        self.send_header("Access-Control-Allow-Origin", cors_origin)
        self.send_header("Vary", "Origin")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
        self.end_headers()

    def do_GET(self):
        """Handle GET endpoints: /health, /ready."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        if path == "/health":
            health_info = self.router.manager.check_health()
            resp = HealthResponse(
                status="ok",
                version=health_info.get("version", "0.1.0-beta"),
                active_provider=health_info.get("active_provider", self.config.provider),
                active_model=health_info.get("active_model", self.config.model),
            )
            self._send_json_response(HTTPStatus.OK, resp.model_dump())

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
            resp_dict["feedback_metrics"] = self.router.feedback_store.get_queue_metrics()
            status_code = HTTPStatus.OK if is_ready else HTTPStatus.SERVICE_UNAVAILABLE
            self._send_json_response(status_code, resp_dict)

        else:
            self._send_error(
                HTTPStatus.NOT_FOUND,
                code="ENDPOINT_NOT_FOUND",
                message=f"Endpoint '{self.path}' not recognized on Central AI API.",
            )

    def do_POST(self):
        """Handle POST inference and feedback endpoints with rate limiting."""
        parsed_url = urllib.parse.urlparse(self.path)
        path = parsed_url.path.rstrip("/")

        # Extract client key for rate limiting (API key or IP)
        auth_header = self.headers.get("Authorization", "")
        client_key = auth_header if auth_header else self.client_address[0]

        # Rate Limiting & Concurrency Check
        allowed, remaining, reset_after, reason = self.rate_limiter.acquire(client_key)
        rate_headers = {
            "X-RateLimit-Limit": self.rate_limiter.rpm,
            "X-RateLimit-Remaining": remaining,
            "X-RateLimit-Reset": reset_after,
        }

        if not allowed:
            self._send_error(
                HTTPStatus.TOO_MANY_REQUESTS,
                code=reason,
                message=(
                    f"Too many requests. Limit: {self.rate_limiter.rpm} requests/minute. "
                    f"Retry in {reset_after} seconds."
                ),
                request_id="req-rate-limited",
                rate_limit_headers=rate_headers,
            )
            return

        # Check authentication if API key is configured
        if not self._check_auth():
            self._send_error(
                HTTPStatus.UNAUTHORIZED,
                code="UNAUTHORIZED",
                message="Authentication required. Provide a valid API key via Authorization header.",
                request_id=self.headers.get("X-Request-ID") or "req-unauth",
                rate_limit_headers=rate_headers,
            )
            return

        try:
            req_id_header = self.headers.get("X-Request-ID")
            content_length = int(self.headers.get("Content-Length", 0))

            if content_length == 0:
                self._send_error(
                    HTTPStatus.BAD_REQUEST,
                    code="EMPTY_REQUEST_BODY",
                    message="HTTP POST request body cannot be empty.",
                    request_id=req_id_header or "req-empty",
                    rate_limit_headers=rate_headers,
                )
                return

            if content_length > self.config.max_request_body_bytes:
                self._send_error(
                    HTTPStatus.REQUEST_ENTITY_TOO_LARGE,
                    code="PAYLOAD_TOO_LARGE",
                    message=(
                        f"Request payload size ({content_length} bytes) exceeds maximum configured limit "
                        f"({self.config.max_request_body_bytes} bytes)."
                    ),
                    request_id=req_id_header or "req-too-large",
                    rate_limit_headers=rate_headers,
                )
                return

            raw_body = self.rfile.read(content_length)
            try:
                body_dict = json.loads(raw_body.decode("utf-8"))
            except json.JSONDecodeError as e:
                self._send_error(
                    HTTPStatus.BAD_REQUEST,
                    code="INVALID_JSON",
                    message=f"Failed to parse request body as JSON: {str(e)}",
                    request_id=req_id_header or "req-bad-json",
                    rate_limit_headers=rate_headers,
                )
                return

            # Propagate header request_id if body does not specify one
            if req_id_header and "request_id" not in body_dict:
                body_dict["request_id"] = req_id_header

            # Route matching
            if path == "/api/v1/chat":
                req_obj = ChatRequest(**body_dict)
                res = self.router.handle_chat(req_obj)
                status_code = HTTPStatus.OK if res.status == "success" else HTTPStatus.INTERNAL_SERVER_ERROR
                self._send_json_response(status_code, res.model_dump(), res.request_id, rate_headers)

            elif path == "/api/v1/tutor/explain":
                req_obj = TutorExplainRequest(**body_dict)
                res = self.router.handle_tutor_explain(req_obj)
                status_code = HTTPStatus.OK if res.status == "success" else HTTPStatus.INTERNAL_SERVER_ERROR
                self._send_json_response(status_code, res.model_dump(), res.request_id, rate_headers)

            elif path == "/api/v1/speaking/respond":
                req_obj = SpeakingRespondRequest(**body_dict)
                res = self.router.handle_speaking_respond(req_obj)
                status_code = HTTPStatus.OK if res.status == "success" else HTTPStatus.INTERNAL_SERVER_ERROR
                self._send_json_response(status_code, res.model_dump(), res.request_id, rate_headers)

            elif path == "/api/v1/exams/explain":
                req_obj = ExamsExplainRequest(**body_dict)
                res = self.router.handle_exams_explain(req_obj)
                status_code = HTTPStatus.OK if res.status == "success" else HTTPStatus.INTERNAL_SERVER_ERROR
                self._send_json_response(status_code, res.model_dump(), res.request_id, rate_headers)

            elif path == "/api/v1/feedback":
                fb_req = FeedbackSubmissionRequest(**body_dict)
                fb_res = self.router.handle_feedback(fb_req)
                self._send_json_response(HTTPStatus.ACCEPTED, fb_res.model_dump(), fb_req.request_id, rate_headers)

            elif path == "/api/v1/feedback/consent/withdraw":
                user_id = body_dict.get("user_id") or body_dict.get("user_id_hash") or ""
                res = self.router.handle_withdraw_consent(user_id)
                self._send_json_response(HTTPStatus.OK, res, req_id_header or "req-withdraw", rate_headers)

            else:
                self._send_error(
                    HTTPStatus.NOT_FOUND,
                    code="ENDPOINT_NOT_FOUND",
                    message=f"POST endpoint '{self.path}' does not exist.",
                    request_id=req_id_header or "req-not-found",
                    rate_limit_headers=rate_headers,
                )

        except ValidationError as val_err:
            self._send_error(
                HTTPStatus.UNPROCESSABLE_ENTITY,
                code="SCHEMA_VALIDATION_ERROR",
                message=f"Request schema validation failed: {str(val_err)}",
                request_id=body_dict.get("request_id") or req_id_header or "req-val-err",
                rate_limit_headers=rate_headers,
            )
        except Exception as exc:
            logger.exception("Unexpected exception during request processing")
            msg = (
                f"An unhandled internal exception occurred: {type(exc).__name__}: {str(exc)}"
                if self.config.environment == "development"
                else "An internal server error occurred. Please contact support with the request ID."
            )
            self._send_error(
                HTTPStatus.INTERNAL_SERVER_ERROR,
                code="INTERNAL_SERVER_ERROR",
                message=msg,
                request_id=body_dict.get("request_id") or req_id_header or "req-exc",
                rate_limit_headers=rate_headers,
            )
        finally:
            self.rate_limiter.release(client_key)

    def log_message(self, format: str, *args: Any):
        """Custom clean logging avoiding standard stderr pollution."""
        logger.info("%s - - [%s] %s", self.client_address[0], self.log_date_time_string(), format % args)


def create_server(config: Optional[APIConfig] = None) -> ThreadingHTTPServer:
    """Create and configure the ThreadingHTTPServer instance."""
    if config is None:
        config = get_default_config()

    provider_manager = ProviderManager(config)
    feedback_store = FeedbackStore(config.data_dir)
    router = CentralAPIRouter(provider_manager, feedback_store)
    rate_limiter = RateLimiter(
        requests_per_minute=config.rate_limit_rpm,
        max_concurrency=config.max_concurrency,
        enabled=config.rate_limit_enabled,
    )

    class CustomHandler(CentralAPIRequestHandler):
        pass

    CustomHandler.router = router
    CustomHandler.config = config
    CustomHandler.rate_limiter = rate_limiter

    server_address = (config.host, config.port)
    server = ThreadingHTTPServer(server_address, CustomHandler)
    logger.info("Central AI Server initialized on %s:%d (Provider: %s, Model: %s, RPM Limit: %d)",
                config.host, config.port, config.provider, config.model, config.rate_limit_rpm)
    return server
