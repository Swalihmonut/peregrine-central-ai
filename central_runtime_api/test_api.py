"""Comprehensive unit and functional test suite for Central AI Runtime & API."""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from typing import Any, Dict

from central_runtime_api.config import APIConfig
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
from central_runtime_api.workers.feedback_worker import ContinuousLearningWorker


class TestCentralAIRuntime(unittest.TestCase):
    """Test suite running against a live in-process server using MockProviderAdapter."""

    server_thread: threading.Thread
    server: Any
    base_url: str
    port: int = 8999
    temp_dir: str

    @classmethod
    def setUpClass(cls):
        """Start in-process HTTP server on port 8999 using mock provider and isolated temp data dir."""
        cls.temp_dir = tempfile.mkdtemp(prefix="central_ai_test_data_")
        config = APIConfig(
            host="127.0.0.1",
            port=cls.port,
            provider="mock",
            model="mock-qwen3",
            timeout_seconds=5.0,
            rate_limit_enabled=True,
            rate_limit_rpm=100,
            data_dir=Path(cls.temp_dir),
        )
        cls.server = create_server(config)
        cls.base_url = f"http://127.0.0.1:{cls.port}"
        cls.server_thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.server_thread.start()
        time.sleep(0.5)

    @classmethod
    def tearDownClass(cls):
        """Shutdown in-process server and clean temp dir."""
        cls.server.shutdown()
        cls.server.server_close()
        cls.server_thread.join(timeout=2.0)
        shutil.rmtree(cls.temp_dir, ignore_errors=True)

    def _post(self, path: str, payload: Dict[str, Any], headers: Dict[str, str] = None) -> tuple[int, Dict[str, Any], Dict[str, str]]:
        url = f"{self.base_url}{path}"
        data = json.dumps(payload).encode("utf-8")
        h = {"Content-Type": "application/json"}
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, data=data, headers=h, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                resp_headers = dict(resp.headers.items())
                return resp.status, json.loads(resp.read().decode("utf-8")), resp_headers
        except urllib.error.HTTPError as e:
            resp_headers = dict(e.headers.items())
            return e.code, json.loads(e.read().decode("utf-8")), resp_headers

    def _get(self, path: str) -> tuple[int, Dict[str, Any]]:
        url = f"{self.base_url}{path}"
        req = urllib.request.Request(url, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=5.0) as resp:
                return resp.status, json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            return e.code, json.loads(e.read().decode("utf-8"))

    # ========================================================
    # 1. Health and Readiness Tests
    # ========================================================

    def test_01_health_endpoint(self):
        """Test GET /health returns standard health payload."""
        code, body = self._get("/health")
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "ok")
        self.assertEqual(body.get("active_provider"), "mock")
        self.assertEqual(body.get("active_model"), "mock-qwen3")
        self.assertIn("version", body)
        self.assertIn("timestamp", body)

    def test_02_ready_endpoint(self):
        """Test GET /ready returns readiness and disk telemetry."""
        code, body = self._get("/ready")
        self.assertEqual(code, 200)
        self.assertTrue(body.get("ready"))
        self.assertGreater(body.get("disk_free_gb", 0), 5.0)
        self.assertTrue(body.get("sequential_lock_idle"))

    # ========================================================
    # 2. Domain Application Endpoints Tests
    # ========================================================

    def test_03_chat_endpoint(self):
        """Test POST /api/v1/chat returns standard CentralAPIResponse."""
        payload = {
            "messages": [
                {"role": "user", "content": "مرحبا بك في المختبر"}
            ],
            "parameters": {"temperature": 0.2, "max_tokens": 512}
        }
        code, body, _ = self._post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        self.assertIsNotNone(body.get("content"))
        self.assertEqual(body.get("provider"), "mock")
        self.assertIn("latency_ms", body.get("telemetry", {}))
        self.assertGreater(body.get("usage", {}).get("total_tokens", 0), 0)

    def test_04_tutor_explain_endpoint(self):
        """Test POST /api/v1/tutor/explain returns structured grammar explanation."""
        payload = {
            "query": "أعرب جملة إن العلم نور",
            "level": "intermediate",
            "topic": "nahw"
        }
        code, body, _ = self._post("/api/v1/tutor/explain", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        content = body.get("content", "")
        self.assertIn("إنَّ", content)
        self.assertIn("اسم إنّ", content)
        self.assertIn("خبر إنّ", content)

    def test_05_speaking_respond_endpoint(self):
        """Test POST /api/v1/speaking/respond returns conversational turn."""
        payload = {
            "user_utterance": "السلام عليكم، كيف حالك اليوم؟",
            "scenario": "daily_conversation",
            "dialect": "msa",
            "dialogue_history": []
        }
        code, body, _ = self._post("/api/v1/speaking/respond", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        content = body.get("content", "")
        self.assertTrue(len(content) > 10)
        self.assertIn("أهلاً", content)

    def test_06_exams_explain_endpoint(self):
        """Test POST /api/v1/exams/explain analyzes question and options."""
        payload = {
            "question_text": "ما علامة إعراب الفاعل في جملة حضر المعلمون؟",
            "options": ["الضمة", "الواو", "الألف", "الفتحة"],
            "correct_answer": "الواو",
            "student_answer": "الضمة"
        }
        code, body, _ = self._post("/api/v1/exams/explain", payload)
        self.assertEqual(code, 200)
        self.assertEqual(body.get("status"), "success")
        content = body.get("content", "")
        self.assertIn("الإجابة الصحيحة", content)

    # ========================================================
    # 3. Error Handling and Safety Rule Tests
    # ========================================================

    def test_07_thinking_isolation_safety_rule(self):
        """Beta Safety Rule: If model only emits reasoning, content must be None and error returned."""
        payload = {
            "messages": [
                {"role": "user", "content": "Test __FORCE_REASONING_ONLY__ query"}
            ]
        }
        code, body, _ = self._post("/api/v1/chat", payload)
        self.assertEqual(body.get("status"), "error")
        self.assertIsNone(body.get("content"))
        self.assertEqual(body.get("error", {}).get("code"), "MODEL_REASONING_ONLY")
        self.assertIn("withheld", body.get("error", {}).get("message").lower())

    def test_08_invalid_json_handling(self):
        """Test POST with malformed JSON returns 400 INVALID_JSON."""
        url = f"{self.base_url}/api/v1/chat"
        req = urllib.request.Request(
            url,
            data=b"THIS IS NOT VALID JSON {",
            headers={"Content-Type": "application/json"},
            method="POST"
        )
        with self.assertRaises(urllib.error.HTTPError) as ctx:
            urllib.request.urlopen(req)
        err = ctx.exception
        self.assertEqual(err.code, 400)
        res_json = json.loads(err.read().decode("utf-8"))
        self.assertEqual(res_json.get("error", {}).get("code"), "INVALID_JSON")

    def test_09_schema_validation_error(self):
        """Test POST with missing required field returns 422 SCHEMA_VALIDATION_ERROR."""
        payload = {"invalid_key": "no messages provided"}
        code, body, _ = self._post("/api/v1/chat", payload)
        self.assertEqual(code, 422)
        self.assertEqual(body.get("error", {}).get("code"), "SCHEMA_VALIDATION_ERROR")

    def test_10_endpoint_not_found(self):
        """Test non-existent path returns 404 ENDPOINT_NOT_FOUND."""
        code, body = self._get("/api/v1/non_existent_route")
        self.assertEqual(code, 404)
        self.assertEqual(body.get("error", {}).get("code"), "ENDPOINT_NOT_FOUND")

    def test_11_request_id_propagation(self):
        """Test that custom X-Request-ID header is propagated into response."""
        custom_id = "test-req-custom-9988"
        payload = {
            "messages": [{"role": "user", "content": "Hello"}]
        }
        code, body, _ = self._post("/api/v1/chat", payload, headers={"X-Request-ID": custom_id})
        self.assertEqual(code, 200)
        self.assertEqual(body.get("request_id"), custom_id)

    # ========================================================
    # 4. Continuous Learning & Feedback Ingestion Tests
    # ========================================================

    def test_12_feedback_with_consent(self):
        """Test POST /api/v1/feedback when consent is granted."""
        payload = {
            "request_id": "req-tutor-991",
            "rating": 2,
            "category": "grammatical_error",
            "user_correction": "الصواب هو نصب اسم إن بالفتحة وليس بالضمة.",
            "comments": "يرجى مراعاة علامات الإعراب الأصلية.",
            "consent_for_training": True,
            "user_id_hash": "raw_user_12345",
            "metadata": {"prompt": "أعرب إن العلم نور", "original_output": "العلمُ نور"}
        }
        code, body, _ = self._post("/api/v1/feedback", payload)
        self.assertEqual(code, 202)
        self.assertEqual(body.get("status"), "received")
        self.assertTrue(body.get("consent_recorded"))
        self.assertTrue(body.get("eligible_for_learning_pipeline"))

    def test_13_feedback_without_consent(self):
        """Test POST /api/v1/feedback when consent is denied (must exclude from training)."""
        payload = {
            "request_id": "req-tutor-992",
            "rating": 1,
            "category": "hallucination",
            "user_correction": "Incorrect output",
            "comments": "Do not train on my data",
            "consent_for_training": False,
            "user_id_hash": "user_private"
        }
        code, body, _ = self._post("/api/v1/feedback", payload)
        self.assertEqual(code, 202)
        self.assertFalse(body.get("consent_recorded"))
        self.assertFalse(body.get("eligible_for_learning_pipeline"))
        self.assertIn("Consent not granted", body.get("message"))

    def test_14_pii_sanitization(self):
        """Test sensitive data filtering (emails, phones, national IDs) in privacy middleware."""
        raw_text = (
            "تواصل معي على البريد info@example.com أو على الهاتف +971501234567 "
            "ورقم الهوية 784-1990-1234567-1 لمراجعة الإعراب."
        )
        cleaned, counts = sanitize_pii(raw_text)
        self.assertNotIn("info@example.com", cleaned)
        self.assertNotIn("+971501234567", cleaned)
        self.assertNotIn("784-1990-1234567-1", cleaned)
        self.assertIn("[REDACTED_EMAIL]", cleaned)
        self.assertIn("[REDACTED_PHONE]", cleaned)
        self.assertIn("[REDACTED_EMIRATES_ID]", cleaned)
        self.assertEqual(counts.get("email"), 1)
        self.assertEqual(counts.get("phone"), 1)

    def test_15_continuous_learning_worker_cycle(self):
        """Test background worker aggregates eligible feedback into candidate dataset."""
        worker = ContinuousLearningWorker(Path(self.temp_dir))
        count = worker.process_cycle("v0.1.0-test-candidates")
        self.assertGreaterEqual(count, 1)

        candidate_file = Path(self.temp_dir) / "candidates" / "v0.1.0-test-candidates.jsonl"
        self.assertTrue(candidate_file.exists())

        # Verify candidate record schema
        with open(candidate_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            self.assertGreaterEqual(len(lines), 1)
            record = json.loads(lines[0])
            self.assertEqual(record.get("review_status"), "pending_review")
            self.assertTrue(record.get("pii_redacted"))
            self.assertEqual(record.get("dataset_version_target"), "v0.1.0-test-candidates")

    def test_16_rate_limiter_headers(self):
        """Test that rate limiting headers are returned on valid requests."""
        payload = {"messages": [{"role": "user", "content": "ping"}]}
        code, body, headers = self._post("/api/v1/chat", payload)
        self.assertEqual(code, 200)
        # Check case-insensitively or standard header casing
        header_keys_lower = [k.lower() for k in headers.keys()]
        self.assertIn("x-ratelimit-limit", header_keys_lower)
        self.assertIn("x-ratelimit-remaining", header_keys_lower)

    def test_17_rate_limiter_rejection(self):
        """Test that exceeding RPM returns HTTP 429 Too Many Requests."""
        strict_limiter = RateLimiter(requests_per_minute=2, enabled=True)
        allowed1, _, _, _ = strict_limiter.acquire("test_client")
        allowed2, _, _, _ = strict_limiter.acquire("test_client")
        allowed3, remaining, reset, reason = strict_limiter.acquire("test_client")

        self.assertTrue(allowed1)
        self.assertTrue(allowed2)
        self.assertFalse(allowed3)
        self.assertEqual(reason, "RATE_LIMIT_EXCEEDED")
        self.assertGreater(reset, 0.0)


if __name__ == "__main__":
    unittest.main()
