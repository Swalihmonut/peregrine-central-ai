"""Cloud Container Readiness and ASGI Verification Suite for Central Arabic AI API."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import shutil
import tempfile
import unittest
from typing import Any, Dict, List, Optional, Tuple

from central_runtime_api.asgi import CentralAIASGIApp
from central_runtime_api.config import APIConfig
from central_runtime_api.schemas import (
    ChatMessage,
    ChatRequest,
    FeedbackCategory,
    FeedbackSubmissionRequest,
    MessageRole,
)


class ASGIInMemoryClient:
    """Zero-socket in-memory test client dispatching ASGI scope/receive/send."""

    def __init__(self, app: CentralAIASGIApp):
        self.app = app

    async def request(
        self,
        method: str,
        path: str,
        body: Optional[Dict[str, Any] | bytes] = None,
        headers: Optional[Dict[str, str]] = None,
        origin: Optional[str] = None,
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        req_headers = {}
        if headers:
            for k, v in headers.items():
                req_headers[k.lower()] = v
        if origin:
            req_headers["origin"] = origin

        raw_body = b""
        if body is not None:
            if isinstance(body, bytes):
                raw_body = body
            else:
                raw_body = json.dumps(body, ensure_ascii=False).encode("utf-8")
                req_headers["content-type"] = "application/json; charset=utf-8"
            req_headers["content-length"] = str(len(raw_body))

        asgi_headers = [
            (k.encode("latin1"), v.encode("latin1")) for k, v in req_headers.items()
        ]

        scope = {
            "type": "http",
            "asgi": {"version": "3.0"},
            "http_version": "1.1",
            "method": method.upper(),
            "scheme": "http",
            "path": path,
            "raw_path": path.encode("ascii"),
            "query_string": b"",
            "headers": asgi_headers,
            "client": ("127.0.0.1", 54321),
            "server": ("127.0.0.1", 8000),
        }

        body_sent = False

        async def receive():
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {"type": "http.request", "body": raw_body, "more_body": False}
            return {"type": "http.request", "body": b"", "more_body": False}

        status_code = 0
        response_headers: Dict[str, str] = {}
        response_body = bytearray()

        async def send(message):
            nonlocal status_code
            m_type = message.get("type")
            if m_type == "http.response.start":
                status_code = message.get("status", 200)
                for k, v in message.get("headers", []):
                    response_headers[k.decode("latin1").lower()] = v.decode("latin1")
            elif m_type == "http.response.body":
                response_body.extend(message.get("body", b""))

        await self.app(scope, receive, send)

        parsed_json: Dict[str, Any] = {}
        if response_body:
            try:
                parsed_json = json.loads(response_body.decode("utf-8"))
            except Exception:
                parsed_json = {"raw": response_body.decode("utf-8", errors="replace")}

        return status_code, parsed_json, response_headers


class TestCloudContainerReadiness(unittest.TestCase):
    """Test suite executing in-memory against production ASGI app without OS socket permissions."""

    temp_dir: str
    config: APIConfig
    app: CentralAIASGIApp
    client: ASGIInMemoryClient

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="cloud_container_test_")
        cls.config = APIConfig(
            host="0.0.0.0",
            port=8000,
            provider="mock",
            model="qwen3:4b",
            environment="staging",
            api_key="secret-staging-key-12345",
            data_dir=Path(cls.temp_dir),
            cors_origins=["https://ai.peregrineacademy.in", "http://localhost:3000"],
            max_request_body_bytes=1024 * 1024,  # 1 MB
            rate_limit_enabled=True,
            rate_limit_rpm=60,
            min_disk_free_gb=0.5,
        )
        cls.app = CentralAIASGIApp(cls.config)
        cls.client = ASGIInMemoryClient(cls.app)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def test_01_lifespan_startup_and_shutdown(self):
        """ASGI lifespan startup and shutdown must complete cleanly."""
        scope = {"type": "lifespan", "asgi": {"version": "3.0"}}
        events_received = []
        isolated_app = CentralAIASGIApp(self.config)

        async def run_lifespan():
            queue = asyncio.Queue()
            await queue.put({"type": "lifespan.startup"})
            await queue.put({"type": "lifespan.shutdown"})

            async def receive():
                return await queue.get()

            async def send(msg):
                events_received.append(msg.get("type"))

            await isolated_app(scope, receive, send)

        asyncio.run(run_lifespan())
        self.assertIn("lifespan.startup.complete", events_received)
        self.assertIn("lifespan.shutdown.complete", events_received)
        self.assertTrue(isolated_app._is_shutting_down)

    def test_02_health_liveness_probe(self):
        """GET /health must return 200 OK without requiring authentication."""
        status, body, headers = asyncio.run(self.client.request("GET", "/health"))
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("active_provider"), "mock")
        self.assertEqual(body.get("active_model"), "qwen3:4b")

    def test_03_ready_probe_with_queue_telemetry(self):
        """GET /ready must report readiness, disk headroom, and feedback queue metrics."""
        status, body, headers = asyncio.run(self.client.request("GET", "/ready"))
        self.assertEqual(status, 200)
        self.assertTrue(body.get("ready"))
        self.assertIn("feedback_metrics", body)
        metrics = body["feedback_metrics"]
        self.assertIn("learning_queue_depth", metrics)
        self.assertIn("operational_feedback_count", metrics)

    def test_04_cors_allowlist_matching_origin(self):
        """Requests from https://ai.peregrineacademy.in must receive exact matching CORS header."""
        status, body, headers = asyncio.run(
            self.client.request("GET", "/health", origin="https://ai.peregrineacademy.in")
        )
        self.assertEqual(status, 200)
        self.assertEqual(headers.get("access-control-allow-origin"), "https://ai.peregrineacademy.in")
        self.assertEqual(headers.get("vary"), "Origin")

    def test_05_cors_preflight_options(self):
        """OPTIONS preflight must return 204 No Content with allowed methods and headers."""
        status, body, headers = asyncio.run(
            self.client.request("OPTIONS", "/api/v1/chat", origin="https://ai.peregrineacademy.in")
        )
        self.assertEqual(status, 204)
        self.assertEqual(headers.get("access-control-allow-origin"), "https://ai.peregrineacademy.in")
        self.assertIn("POST", headers.get("access-control-allow-methods", ""))
        self.assertIn("X-Request-ID", headers.get("access-control-allow-headers", ""))

    def test_06_unauthenticated_post_rejected(self):
        """POST /api/v1/chat without valid API key must return 401 UNAUTHORIZED."""
        payload = {
            "messages": [{"role": "user", "content": "مرحبا"}]
        }
        status, body, headers = asyncio.run(self.client.request("POST", "/api/v1/chat", body=payload))
        self.assertEqual(status, 401)
        self.assertEqual(body.get("error", {}).get("code"), "UNAUTHORIZED")

    def test_07_authenticated_post_success(self):
        """POST /api/v1/chat with valid Bearer token must succeed with 200 OK."""
        payload = {
            "messages": [{"role": "user", "content": "ما إعراب سماء؟"}]
        }
        headers = {"Authorization": "Bearer secret-staging-key-12345"}
        status, body, _ = asyncio.run(
            self.client.request("POST", "/api/v1/chat", body=payload, headers=headers)
        )
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsNotNone(body.get("content"))
        self.assertEqual(body.get("provider"), "mock")

    def test_08_request_body_size_limit_413(self):
        """Payload exceeding max_request_body_bytes (1 MB) must be rejected with 413 PAYLOAD_TOO_LARGE."""
        giant_body = b"A" * (1024 * 1024 + 100)  # > 1MB
        headers = {
            "Authorization": "Bearer secret-staging-key-12345",
            "Content-Type": "application/json",
        }
        status, body, _ = asyncio.run(
            self.client.request("POST", "/api/v1/chat", body=giant_body, headers=headers)
        )
        self.assertEqual(status, 413)
        self.assertEqual(body.get("error", {}).get("code"), "PAYLOAD_TOO_LARGE")

    def test_09_feedback_with_consent_persistence(self):
        """Feedback with consent=True must enter both operational and learning queues."""
        fb_payload = {
            "request_id": "req-fb-test-01",
            "rating": 2,
            "category": "grammatical_error",
            "comments": "تصحيح الإعراب في كلمة طالباً",
            "user_correction": "طالباً: خبر كان منصوب وعلامة نصبه الفتحة",
            "consent_for_training": True,
            "user_id_hash": "user_abdullah_uae",
        }
        headers = {"Authorization": "Bearer secret-staging-key-12345"}
        status, body, _ = asyncio.run(
            self.client.request("POST", "/api/v1/feedback", body=fb_payload, headers=headers)
        )
        self.assertEqual(status, 202)
        self.assertTrue(body.get("consent_recorded"))
        self.assertTrue(body.get("eligible_for_learning_pipeline"))

        # Verify learning queue has record
        metrics = self.app.feedback_store.get_queue_metrics()
        self.assertGreaterEqual(metrics.get("learning_queue_depth", 0), 1)

    def test_10_consent_withdrawal_endpoint(self):
        """POST /api/v1/feedback/consent/withdraw must purge all records for that user."""
        headers = {"Authorization": "Bearer secret-staging-key-12345"}
        withdraw_payload = {"user_id": "user_abdullah_uae"}

        status, body, _ = asyncio.run(
            self.client.request(
                "POST",
                "/api/v1/feedback/consent/withdraw",
                body=withdraw_payload,
                headers=headers,
            )
        )
        self.assertEqual(status, 200)
        self.assertEqual(body.get("status"), "consent_revoked")
        self.assertGreaterEqual(body.get("purged_records_count", 0), 1)

        # Verify learning queue is now drained of that user
        metrics = self.app.feedback_store.get_queue_metrics()
        self.assertEqual(metrics.get("learning_queue_depth", 0), 0)

    def test_11_request_id_propagation(self):
        """Supplied X-Request-ID must be propagated in response body and response headers."""
        custom_id = "peregrine-req-trace-999"
        payload = {"query": "اشرح كان وأخواتها", "level": "beginner"}
        headers = {
            "Authorization": "Bearer secret-staging-key-12345",
            "X-Request-ID": custom_id,
        }
        status, body, res_headers = asyncio.run(
            self.client.request("POST", "/api/v1/tutor/explain", body=payload, headers=headers)
        )
        self.assertEqual(status, 200)
        self.assertEqual(body.get("request_id"), custom_id)
        self.assertEqual(res_headers.get("x-request-id"), custom_id)

    def test_12_rate_limiter_exhaustion(self):
        """Exceeding requests per minute must trigger HTTP 429 Too Many Requests."""
        limited_config = APIConfig(
            host="0.0.0.0",
            port=8000,
            provider="mock",
            rate_limit_enabled=True,
            rate_limit_rpm=3,
            data_dir=Path(self.temp_dir),
        )
        limited_app = CentralAIASGIApp(limited_config)
        client = ASGIInMemoryClient(limited_app)

        # 3 allowed requests
        for _ in range(3):
            s, _, _ = asyncio.run(client.request("GET", "/health"))
            self.assertEqual(s, 200)

        # 4th request must be rate limited
        s4, b4, h4 = asyncio.run(client.request("GET", "/health"))
        self.assertEqual(s4, 429)
        self.assertEqual(b4.get("error", {}).get("code"), "RATE_LIMIT_EXCEEDED")
        self.assertIn("x-ratelimit-reset", h4)

    def test_13_domain_endpoints_tutor_speaking_exams(self):
        """All specialized Arabic domain endpoints must return valid responses."""
        headers = {"Authorization": "Bearer secret-staging-key-12345"}

        # Tutor
        tutor_payload = {"query": "ما الفرق بين الفاعل ونائب الفاعل؟", "level": "intermediate"}
        st, bt, _ = asyncio.run(self.client.request("POST", "/api/v1/tutor/explain", body=tutor_payload, headers=headers))
        self.assertEqual(st, 200)
        self.assertIsNotNone(bt.get("content"))
        self.assertIn("الإعراب", bt.get("content", ""))

        # Speaking Partner
        speaking_payload = {"user_utterance": "السلام عليكم، كيف حالك اليوم؟", "dialect": "emirati"}
        ss, bs, _ = asyncio.run(self.client.request("POST", "/api/v1/speaking/respond", body=speaking_payload, headers=headers))
        self.assertEqual(ss, 200)
        self.assertIsNotNone(bs.get("content"))

        # Exams
        exam_payload = {
            "question_text": "ما إعراب كلمة 'زيداً' في جملة: رأيتُ زيداً؟",
            "options": ["فاعل", "مفعول به", "مبتدأ", "خبر"],
            "correct_answer": "مفعول به",
        }
        se, be, _ = asyncio.run(self.client.request("POST", "/api/v1/exams/explain", body=exam_payload, headers=headers))
        self.assertEqual(se, 200)
        self.assertIsNotNone(be.get("content"))
        self.assertIn("الإجابة الصحيحة", be.get("content", ""))

    def test_14_invalid_json_handling(self):
        """Malformed JSON must return HTTP 400 INVALID_JSON."""
        headers = {"Authorization": "Bearer secret-staging-key-12345"}
        bad_json = b"{invalid_json: true, missing_quotes"
        s, b, _ = asyncio.run(self.client.request("POST", "/api/v1/chat", body=bad_json, headers=headers))
        self.assertEqual(s, 400)
        self.assertEqual(b.get("error", {}).get("code"), "INVALID_JSON")

    def test_15_provider_fallback_execution(self):
        """When primary provider fails, manager must automatically fall back."""
        fallback_config = APIConfig(
            host="0.0.0.0",
            port=8000,
            provider="mock",
            fallback_provider="mock",
            model="mock-fail",
            fallback_model="qwen3:4b",
            data_dir=Path(self.temp_dir),
            min_disk_free_gb=0.5,
        )
        app = CentralAIASGIApp(fallback_config)
        # Mock adapter simulates failure if model name contains 'fail'
        app.provider_manager.adapter.model_name = "trigger_mock_failure"
        client = ASGIInMemoryClient(app)

        payload = {"messages": [{"role": "user", "content": "تجربة الفشل والاستعادة"}]}
        s, b, _ = asyncio.run(client.request("POST", "/api/v1/chat", body=payload))
        self.assertEqual(s, 200)
        self.assertEqual(b.get("status"), "success")


if __name__ == "__main__":
    unittest.main()
