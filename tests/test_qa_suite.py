"""Comprehensive Automated QA Test Suite for Central Arabic AI Runtime & Cloud Architecture.

Covers all 13 Beta V-001 QA Mission requirements:
1. Health and readiness endpoints
2. Authentication and authorization
3. Valid and invalid requests
4. Arabic and English request handling
5. Conversation history
6. Model timeout and unavailable provider
7. Empty model responses
8. Rate limits and concurrency
9. Usage tracking
10. Feedback submission
11. Consent enforcement & PII anonymization
12. Provider fallback
13. Cloud environment configuration
"""

from __future__ import annotations

import concurrent.futures
import json
import os
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

from central_runtime_api.config import APIConfig, get_default_config
from central_runtime_api.middleware.privacy import anonymize_user_id, sanitize_pii
from central_runtime_api.middleware.rate_limiter import RateLimiter
from central_runtime_api.schemas import (
    ChatMessage,
    ChatRequest,
    ExamsExplainRequest,
    FeedbackCategory,
    FeedbackSubmissionRequest,
    GenerationParameters,
    MessageRole,
    SpeakingRespondRequest,
    TutorExplainRequest,
)
from central_runtime_api.server import create_server
from central_runtime_api.services.feedback_store import FeedbackStore
from central_runtime_api.services.provider_manager import ProviderManager
from central_runtime_api.workers.feedback_worker import ContinuousLearningWorker


class CentralAPITestHarness:
    """Helper to launch and teardown isolated in-process test servers."""

    def __init__(self, config: APIConfig):
        self.config = config
        self.server = create_server(config)
        self.base_url = f"http://{config.host}:{config.port}"
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)

    def start(self):
        self.thread.start()
        time.sleep(0.15)

    def stop(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2.0)

    def post(
        self,
        path: str,
        payload: Any,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0,
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        url = f"{self.base_url}{path}"
        if isinstance(payload, (dict, list)):
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        elif isinstance(payload, bytes):
            data = payload
        elif isinstance(payload, str):
            data = payload.encode("utf-8")
        else:
            data = b""

        h = {"Content-Type": "application/json; charset=utf-8"}
        if headers:
            h.update(headers)

        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                body = json.loads(resp.read().decode("utf-8"))
                return resp.status, body, resp_headers
        except urllib.error.HTTPError as e:
            resp_headers = {k.lower(): v for k, v in e.headers.items()}
            raw = e.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except Exception:
                body = {"raw": raw}
            return e.code, body, resp_headers

    def get(
        self,
        path: str,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 5.0,
    ) -> Tuple[int, Dict[str, Any], Dict[str, str]]:
        url = f"{self.base_url}{path}"
        h = headers or {}
        req = urllib.request.Request(url, headers=h, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                body = json.loads(resp.read().decode("utf-8"))
                return resp.status, body, resp_headers
        except urllib.error.HTTPError as e:
            resp_headers = {k.lower(): v for k, v in e.headers.items()}
            raw = e.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except Exception:
                body = {"raw": raw}
            return e.code, body, resp_headers


class TestBetaV001CentralAPIQA(unittest.TestCase):
    """Full automated QA test suite for Central AI Runtime & Cloud Architecture."""

    temp_dir: str
    harness: CentralAPITestHarness
    auth_harness: Optional[CentralAPITestHarness] = None
    TEST_API_KEY = "test-secret-key-beta-qa-2026"

    @classmethod
    def setUpClass(cls):
        cls.temp_dir = tempfile.mkdtemp(prefix="beta_v001_qa_test_")
        
        # Primary standard test server on port 9010 (No mandatory auth)
        config = APIConfig(
            host="127.0.0.1",
            port=9010,
            provider="mock",
            model="qwen3:4b-mock",
            timeout_seconds=5.0,
            rate_limit_enabled=True,
            rate_limit_rpm=60,
            max_concurrency=10,
            data_dir=Path(cls.temp_dir) / "standard_data",
        )
        cls.harness = CentralAPITestHarness(config)
        cls.harness.start()

        # Dedicated authenticated test server on port 9011 (API Key required)
        auth_config = APIConfig(
            host="127.0.0.1",
            port=9011,
            provider="mock",
            model="qwen3:4b-mock",
            api_key=cls.TEST_API_KEY,
            timeout_seconds=5.0,
            rate_limit_enabled=True,
            rate_limit_rpm=30,
            data_dir=Path(cls.temp_dir) / "auth_data",
        )
        cls.auth_harness = CentralAPITestHarness(auth_config)
        cls.auth_harness.start()

    @classmethod
    def tearDownClass(cls):
        cls.harness.stop()
        if cls.auth_harness:
            cls.auth_harness.stop()
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    # =========================================================================
    # 1. Health and Readiness Endpoints
    # =========================================================================

    def test_01_health_endpoint_contract(self):
        """GET /health must return status ok, version, active provider and model."""
        code, body, _ = self.harness.get("/health")
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("version"), "0.1.0-beta")
        self.assertEqual(body.get("active_provider"), "mock")
        self.assertEqual(body.get("active_model"), "qwen3:4b-mock")
        self.assertIn("timestamp", body)

    def test_02_readiness_endpoint_contract(self):
        """GET /ready must report readiness, disk storage, and lock availability."""
        code, body, _ = self.harness.get("/ready")
        self.assertEqual(code, 200)
        self.assertTrue(body.get("ready"))
        self.assertEqual(body.get("provider_status"), "ready")
        self.assertGreater(body.get("disk_free_gb", 0), 1.0)
        self.assertTrue(body.get("sequential_lock_idle"))

    def test_03_readiness_failure_on_disk_breach(self):
        """GET /ready must return 503 if disk space is below safety threshold."""
        temp_data = Path(self.temp_dir) / "disk_test"
        strict_config = APIConfig(
            host="127.0.0.1",
            port=9012,
            provider="mock",
            enforce_disk_limit=True,
            min_disk_free_gb=9999999.0,  # Unattainable threshold to force safety abort
            data_dir=temp_data,
        )
        h = CentralAPITestHarness(strict_config)
        h.start()
        try:
            code, body, _ = h.get("/ready")
            self.assertEqual(code, 503)
            self.assertFalse(body.get("ready"))
            self.assertEqual(body.get("provider_status"), "not_ready_or_provider_stopped")
        finally:
            h.stop()

    # =========================================================================
    # 2. Authentication and Authorization
    # =========================================================================

    def test_04_auth_enforcement_missing_token(self):
        """Protected endpoints must return 401 UNAUTHORIZED when no token is supplied."""
        payload = {"messages": [{"role": "user", "content": "مرحبا"}]}
        code, body, _ = self.auth_harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 401)
        self.assertEqual(body.get("status"), "error")
        self.assertEqual(body.get("error", {}).get("code"), "UNAUTHORIZED")

    def test_05_auth_enforcement_invalid_token(self):
        """Protected endpoints must return 401 UNAUTHORIZED when token is incorrect."""
        payload = {"messages": [{"role": "user", "content": "مرحبا"}]}
        headers = {"Authorization": "Bearer wrong-invalid-token"}
        code, body, _ = self.auth_harness.post("/api/v1/chat", payload, headers=headers)
        self.assertEqual(code, 401)
        self.assertEqual(body.get("error", {}).get("code"), "UNAUTHORIZED")

    def test_06_auth_enforcement_valid_token(self):
        """Protected endpoints must return 200 OK when correct Bearer token is provided."""
        payload = {"messages": [{"role": "user", "content": "مرحبا"}]}
        headers = {"Authorization": f"Bearer {self.TEST_API_KEY}"}
        code, body, _ = self.auth_harness.post("/api/v1/chat", payload, headers=headers)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")

    def test_07_public_probes_unaffected_by_auth(self):
        """GET /health and GET /ready must remain open for container orchestrator probes."""
        code_h, body_h, _ = self.auth_harness.get("/health")
        self.assertEqual(code_h, 200)
        self.assertEqual(body_h.get("status"), "ok")

        code_r, body_r, _ = self.auth_harness.get("/ready")
        self.assertEqual(code_r, 200)
        self.assertTrue(body_r.get("ready"))

    # =========================================================================
    # 3. Valid and Invalid Requests
    # =========================================================================

    def test_08_valid_request_chat_endpoint(self):
        """Valid chat payload must return 200 and standard response structure."""
        payload = {
            "messages": [
                {"role": "user", "content": "ما هو الفرق بين الجملة الاسمية والفعلية؟"}
            ],
            "parameters": {"temperature": 0.3, "max_tokens": 512, "top_p": 0.9}
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsNotNone(body.get("content"))
        self.assertTrue(len(body["content"]) > 10)

    def test_09_invalid_json_payload(self):
        """Malformed JSON must return 400 INVALID_JSON."""
        code, body, _ = self.harness.post("/api/v1/chat", b"{invalid-json: none")
        self.assertEqual(code, 400)
        self.assertEqual(body.get("error", {}).get("code"), "INVALID_JSON")

    def test_10_empty_request_body(self):
        """Empty POST body must return 400 EMPTY_REQUEST_BODY."""
        code, body, _ = self.harness.post("/api/v1/chat", b"")
        self.assertEqual(code, 400)
        self.assertEqual(body.get("error", {}).get("code"), "EMPTY_REQUEST_BODY")

    def test_11_schema_validation_out_of_range_parameter(self):
        """Out-of-range parameters (e.g. temperature > 2.0) must return 422 SCHEMA_VALIDATION_ERROR."""
        payload = {
            "messages": [{"role": "user", "content": "test"}],
            "parameters": {"temperature": 4.5}  # max is 2.0
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 422)
        self.assertEqual(body.get("error", {}).get("code"), "SCHEMA_VALIDATION_ERROR")

    def test_12_non_existent_endpoint(self):
        """Non-existent endpoints must return 404 ENDPOINT_NOT_FOUND."""
        code, body, _ = self.harness.get("/api/v1/invalid_path_probe")
        self.assertEqual(code, 404)
        self.assertEqual(body.get("error", {}).get("code"), "ENDPOINT_NOT_FOUND")

    # =========================================================================
    # 4. Arabic and English Request Handling
    # =========================================================================

    def test_13_arabic_msa_with_tashkeel_handling(self):
        """Arabic text with full diacritics (tashkeel) must be processed without corruption."""
        tashkeel_query = "أَعْرِبْ قَوْلَهُ تَعَالَى: {إِنَّ مَعَ الْعُسْرِ يُسْرًا}"
        payload = {"query": tashkeel_query, "level": "advanced", "topic": "nahw"}
        code, body, _ = self.harness.post("/api/v1/tutor/explain", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        content = body.get("content", "")
        self.assertTrue(len(content) > 20)
        self.assertIn("إنّ", content)

    def test_14_arabic_dialect_handling(self):
        """Speaking Partner must handle Arabic dialects (e.g. Emirati) appropriately."""
        payload = {
            "user_utterance": "شحالك يا خوي؟ شو مسوي اليوم في دبي؟",
            "scenario": "daily_conversation",
            "dialect": "emirati",
        }
        code, body, _ = self.harness.post("/api/v1/speaking/respond", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIn("أهلاً", body.get("content", ""))

    def test_15_english_request_handling(self):
        """System must handle pure English linguistic queries cleanly."""
        payload = {
            "messages": [
                {"role": "user", "content": "Explain the difference between Nahw and Sarf in Arabic."}
            ]
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsNotNone(body.get("content"))

    def test_16_code_switching_bilingual_query(self):
        """System must handle code-switching between Arabic and English."""
        payload = {
            "query": "What is the detailed I'rab of the sentence: إن العلمَ نورٌ ?",
            "level": "intermediate",
            "topic": "nahw"
        }
        code, body, _ = self.harness.post("/api/v1/tutor/explain", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIn("اسم إنّ", body.get("content", ""))

    # =========================================================================
    # 5. Conversation History
    # =========================================================================

    def test_17_multi_turn_chat_history(self):
        """Multi-turn messages array must preserve sequential dialogue history."""
        messages = [
            {"role": "user", "content": "ما هي كان وأخواتها؟"},
            {"role": "assistant", "content": "كان وأخواتها أفعال ناسخة تدخل على المبتدأ والخبر فترفع المبتدأ وتنصب الخبر."},
            {"role": "user", "content": "أعطني مثالاً عليها مع الإعراب."},
        ]
        payload = {"messages": messages}
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertGreater(body.get("usage", {}).get("prompt_tokens", 0), 20)

    def test_18_speaking_dialogue_history(self):
        """Speaking partner must accept dialogue_history turns alongside current utterance."""
        history = [
            {"role": "user", "content": "السلام عليكم ورحمة الله."},
            {"role": "assistant", "content": "وعليكم السلام ورحمة الله وبركاته! كيف أستطيع مساعدتك اليوم؟"}
        ]
        payload = {
            "user_utterance": "أريد حجز غرفة في الفندق لثلاث ليالٍ.",
            "scenario": "travel",
            "dialect": "msa",
            "dialogue_history": history
        }
        code, body, _ = self.harness.post("/api/v1/speaking/respond", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")

    # =========================================================================
    # 6. Model Timeout and Unavailable Provider
    # =========================================================================

    def test_19_model_timeout_handling(self):
        """Simulated model timeout must return 500 status and MODEL_TIMEOUT error envelope."""
        payload = {
            "messages": [{"role": "user", "content": "Trigger __FORCE_TIMEOUT__"}]
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 500)
        self.assertEqual(body.get("status"), "error")
        self.assertEqual(body.get("error", {}).get("code"), "MODEL_TIMEOUT")

    def test_20_unavailable_provider_handling(self):
        """Simulated unavailable provider must return 500 status and PROVIDER_UNAVAILABLE code."""
        payload = {
            "messages": [{"role": "user", "content": "Trigger __FORCE_UNAVAILABLE__"}]
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 500)
        self.assertEqual(body.get("status"), "error")
        self.assertEqual(body.get("error", {}).get("code"), "PROVIDER_UNAVAILABLE")

    def test_21_hosted_adapter_unconfigured_error(self):
        """Hosted adapter without endpoint or API key must report configuration error."""
        config = APIConfig(provider="hosted", hosted_endpoint="", hosted_api_key="")
        pm = ProviderManager(config)
        resp = pm.execute_inference(
            messages=[ChatMessage(role=MessageRole.USER, content="Hello")],
            parameters=GenerationParameters(),
            request_id="req-test-hosted",
        )
        self.assertEqual(resp.status, "error")
        self.assertEqual(resp.error.code, "HOSTED_ENDPOINT_NOT_CONFIGURED")

    # =========================================================================
    # 7. Empty Model Responses
    # =========================================================================

    def test_22_empty_model_response_interception(self):
        """Provider returning empty content string must be caught as EMPTY_MODEL_RESPONSE error."""
        payload = {
            "messages": [{"role": "user", "content": "Trigger __FORCE_EMPTY__"}]
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 500)
        self.assertEqual(body.get("status"), "error")
        self.assertEqual(body.get("error", {}).get("code"), "EMPTY_MODEL_RESPONSE")
        self.assertIsNone(body.get("content"))

    def test_23_reasoning_only_empty_content_isolation(self):
        """Model producing only chain-of-thought without answer must return MODEL_REASONING_ONLY."""
        payload = {
            "messages": [{"role": "user", "content": "Trigger __FORCE_REASONING_ONLY__"}]
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 500)
        self.assertEqual(body.get("status"), "error")
        self.assertEqual(body.get("error", {}).get("code"), "MODEL_REASONING_ONLY")

    # =========================================================================
    # 8. Rate Limits and Concurrency
    # =========================================================================

    def test_24_rate_limit_headers_presence(self):
        """Responses must include standard X-RateLimit headers."""
        payload = {"messages": [{"role": "user", "content": "ping"}]}
        code, _, headers = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        self.assertIn("x-ratelimit-limit", headers)
        self.assertIn("x-ratelimit-remaining", headers)
        self.assertIn("x-ratelimit-reset", headers)

    def test_25_rate_limit_exhaustion_429(self):
        """Exceeding requests per minute must trigger 429 Too Many Requests."""
        rate_config = APIConfig(
            host="127.0.0.1",
            port=9013,
            provider="mock",
            rate_limit_enabled=True,
            rate_limit_rpm=3,
            data_dir=Path(self.temp_dir) / "rate_data",
        )
        rh = CentralAPITestHarness(rate_config)
        rh.start()
        try:
            payload = {"messages": [{"role": "user", "content": "test"}]}
            c1, _, _ = rh.post("/api/v1/chat", payload)
            c2, _, _ = rh.post("/api/v1/chat", payload)
            c3, _, _ = rh.post("/api/v1/chat", payload)
            c4, b4, h4 = rh.post("/api/v1/chat", payload)

            self.assertEqual(c1, 200)
            self.assertEqual(c2, 200)
            self.assertEqual(c3, 200)
            self.assertEqual(c4, 429)
            self.assertEqual(b4.get("error", {}).get("code"), "RATE_LIMIT_EXCEEDED")
            self.assertEqual(h4.get("x-ratelimit-remaining"), "0")
        finally:
            rh.stop()

    def test_26_multi_threaded_concurrency_safety(self):
        """Concurrent requests must execute safely without race conditions or memory corruption."""
        payload = {"messages": [{"role": "user", "content": "concurrent ping"}]}
        
        def send_req():
            c, b, _ = self.harness.post("/api/v1/chat", payload)
            return c, b.get("status")

        with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(send_req) for _ in range(10)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        for status_code, status in results:
            self.assertEqual(status_code, 200)
            self.assertEqual(status, "success")

    # =========================================================================
    # 9. Usage Tracking
    # =========================================================================

    def test_27_token_usage_and_telemetry_metrics(self):
        """Successful responses must report prompt, completion, total tokens and latency."""
        payload = {
            "messages": [
                {"role": "user", "content": "اشرح معنى كلمة الفصاحة في البلاغة العربية بالتفصيل"}
            ]
        }
        code, body, _ = self.harness.post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        usage = body.get("usage", {})
        self.assertGreater(usage.get("prompt_tokens", 0), 0)
        self.assertGreater(usage.get("completion_tokens", 0), 0)
        self.assertEqual(usage.get("total_tokens"), usage["prompt_tokens"] + usage["completion_tokens"])

        telemetry = body.get("telemetry", {})
        self.assertGreater(telemetry.get("latency_ms", 0), 0.0)
        self.assertEqual(telemetry.get("finish_reason"), "stop")

    # =========================================================================
    # 10. Feedback Submission
    # =========================================================================

    def test_28_feedback_submission_valid(self):
        """POST /api/v1/feedback must accept valid evaluations and return 202 ACCEPTED."""
        payload = {
            "request_id": "req-qa-test-101",
            "rating": 5,
            "category": "helpful",
            "comments": "شرح ممتاز وواضح جداً",
            "consent_for_training": True,
            "user_id_hash": "user_qa_101",
            "metadata": {"domain": "tutor"}
        }
        code, body, _ = self.harness.post("/api/v1/feedback", payload)
        self.assertEqual(code, 202)
        self.assertEqual(body.get("status"), "received")
        self.assertTrue(body.get("consent_recorded"))
        self.assertIn("feedback_id", body)

    def test_29_feedback_submission_invalid_rating(self):
        """Feedback with rating out of range (>5) must return 422 SCHEMA_VALIDATION_ERROR."""
        payload = {
            "request_id": "req-qa-test-102",
            "rating": 10,  # Invalid: max is 5
            "category": "helpful"
        }
        code, body, _ = self.harness.post("/api/v1/feedback", payload)
        self.assertEqual(code, 422)
        self.assertEqual(body.get("error", {}).get("code"), "SCHEMA_VALIDATION_ERROR")

    # =========================================================================
    # 11. Consent Enforcement & Privacy Middleware
    # =========================================================================

    def test_30_consent_gate_operational_vs_learning_queue(self):
        """Non-consented feedback must NEVER be stored in the continuous learning queue."""
        fb_dir = Path(self.temp_dir) / "consent_store"
        store = FeedbackStore(fb_dir)

        # 1. Non-consented feedback
        req_no_consent = FeedbackSubmissionRequest(
            request_id="req-private-01",
            rating=1,
            category=FeedbackCategory.HALLUCINATION,
            user_correction="Private correction",
            consent_for_training=False,
            user_id_hash="user_private_99",
        )
        res_no = store.record_feedback(req_no_consent)
        self.assertFalse(res_no.consent_recorded)
        self.assertFalse(res_no.eligible_for_learning_pipeline)

        # 2. Consented feedback
        req_consent = FeedbackSubmissionRequest(
            request_id="req-public-02",
            rating=2,
            category=FeedbackCategory.GRAMMATICAL_ERROR,
            user_correction="Public correction",
            consent_for_training=True,
            user_id_hash="user_consenting_88",
        )
        res_yes = store.record_feedback(req_consent)
        self.assertTrue(res_yes.consent_recorded)
        self.assertTrue(res_yes.eligible_for_learning_pipeline)

        # Check learning queue file directly
        with open(store.learning_queue, "r", encoding="utf-8") as f:
            lines = [json.loads(line) for line in f if line.strip()]
        
        self.assertEqual(len(lines), 1)
        self.assertEqual(lines[0]["request_id"], "req-public-02")
        self.assertTrue(lines[0]["consent_for_training"])

        # Check operational log (contains both)
        with open(store.operational_log, "r", encoding="utf-8") as f:
            op_lines = [json.loads(line) for line in f if line.strip()]
        self.assertEqual(len(op_lines), 2)

    def test_31_pii_sanitization_patterns(self):
        """Privacy middleware must redact international emails, GCC phones, and national IDs."""
        text = (
            "Contact user at student@kuwait-university.edu.kw or phone +966501234567. "
            "National ID: 1029384756, UAE ID: 784-2001-1234567-2."
        )
        cleaned, counts = sanitize_pii(text)
        self.assertNotIn("student@kuwait-university.edu.kw", cleaned)
        self.assertNotIn("+966501234567", cleaned)
        self.assertNotIn("1029384756", cleaned)
        self.assertNotIn("784-2001-1234567-2", cleaned)
        self.assertIn("[REDACTED_EMAIL]", cleaned)
        self.assertIn("[REDACTED_PHONE]", cleaned)
        self.assertIn("[REDACTED_SAUDI_ID]", cleaned)
        self.assertIn("[REDACTED_EMIRATES_ID]", cleaned)

    def test_32_user_id_anonymization_determinism(self):
        """User identifiers must be hashed deterministically using SHA-256."""
        h1 = anonymize_user_id("user-uuid-12345")
        h2 = anonymize_user_id("user-uuid-12345")
        h3 = anonymize_user_id("user-uuid-67890")
        self.assertEqual(h1, h2)
        self.assertNotEqual(h1, h3)
        self.assertTrue(h1.startswith("usr_"))

    # =========================================================================
    # 12. Provider Fallback
    # =========================================================================

    def test_33_provider_fallback_on_primary_failure(self):
        """When primary provider fails, manager must seamlessly fall back to secondary provider."""
        fallback_dir = Path(self.temp_dir) / "fallback_test"
        fb_config = APIConfig(
            host="127.0.0.1",
            port=9014,
            provider="mock",
            fallback_provider="mock",
            model="primary-mock",
            fallback_model="fallback-mock",
            data_dir=fallback_dir,
        )
        pm = ProviderManager(fb_config)
        self.assertIsNotNone(pm.fallback_adapter)

        # Primary forced failure query
        messages = [ChatMessage(role=MessageRole.USER, content="Test __FORCE_ERROR__ query")]
        resp = pm.execute_inference(messages, GenerationParameters(), "req-fallback-test")
        
        # Fallback adapter handles the fallback query (fallback mock doesn't re-trigger error)
        # Note: In our implementation, fallback adapter generates response
        self.assertEqual(resp.status, "success")
        self.assertIsNotNone(resp.content)

    def test_34_provider_no_fallback_when_unconfigured(self):
        """When fallback provider is not configured, primary error must be returned."""
        no_fb_config = APIConfig(provider="mock", fallback_provider=None)
        pm = ProviderManager(no_fb_config)
        self.assertIsNone(pm.fallback_adapter)

        messages = [ChatMessage(role=MessageRole.USER, content="Test __FORCE_ERROR__ query")]
        resp = pm.execute_inference(messages, GenerationParameters(), "req-no-fb-test")
        self.assertEqual(resp.status, "error")
        self.assertEqual(resp.error.code, "SIMULATED_PROVIDER_FAILURE")

    # =========================================================================
    # 13. Cloud Environment Configuration
    # =========================================================================

    def test_35_cloud_environment_variable_loading(self):
        """APIConfig must correctly load and typecast cloud environment variables."""
        env_patch = {
            "CENTRAL_AI_PROVIDER": "hosted",
            "CENTRAL_AI_MODEL": "gpt-4o-mini",
            "CENTRAL_AI_HOST": "0.0.0.0",
            "CENTRAL_AI_PORT": "8080",
            "CENTRAL_AI_TIMEOUT": "45.0",
            "CENTRAL_AI_RATE_LIMIT_RPM": "120",
            "CENTRAL_AI_MAX_CONCURRENCY": "25",
            "HOSTED_ENDPOINT": "https://api.example.com/v1",
            "HOSTED_API_KEY": "sk-cloud-test-key-12345",
        }
        for k, v in env_patch.items():
            os.environ[k] = v

        try:
            cfg = get_default_config()
            self.assertEqual(cfg.provider, "hosted")
            self.assertEqual(cfg.model, "gpt-4o-mini")
            self.assertEqual(cfg.host, "0.0.0.0")
            self.assertEqual(cfg.port, 8080)
            self.assertEqual(cfg.timeout_seconds, 45.0)
            self.assertEqual(cfg.rate_limit_rpm, 120)
            self.assertEqual(cfg.max_concurrency, 25)
            self.assertEqual(cfg.hosted_endpoint, "https://api.example.com/v1")
            self.assertEqual(cfg.hosted_api_key, "sk-cloud-test-key-12345")
        finally:
            for k in env_patch.keys():
                os.environ.pop(k, None)

    def test_36_dockerfile_and_container_configuration(self):
        """Verify Dockerfile exists, uses python 3.11, exposes standard port, and configures HEALTHCHECK."""
        dockerfile_path = Path("central_runtime_api/Dockerfile")
        self.assertTrue(dockerfile_path.exists())
        content = dockerfile_path.read_text(encoding="utf-8")
        self.assertIn("python:3.11", content)
        self.assertIn("EXPOSE 8000", content)
        self.assertIn("HEALTHCHECK", content)
        self.assertIn("/health", content)


if __name__ == "__main__":
    unittest.main()
