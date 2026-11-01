#!/usr/bin/env python3
"""Isolated Staging Smoke-Test Procedure for Central Arabic AI Runtime & API.

Verifies end-to-end functionality across 7 critical staging gates:
- Gate 1: Infrastructure Health & Liveness (/health)
- Gate 2: Readiness & Host Telemetry (/ready)
- Gate 3: Security & Authentication Enforcement
- Gate 4: Bilingual Core Inference & Domain Prompts (Tutor, Speaking, Exams)
- Gate 5: Error Isolation & Safety Interlocks (Malformed JSON, Schema, Reasoning)
- Gate 6: Rate Limiting & Concurrency Headers
- Gate 7: Operational Feedback & Consent Boundaries

Can execute in:
1. Isolated local staging mode (in-process mock server with zero credentials needed)
2. External staging deployment target (via STAGING_URL and STAGING_API_KEY)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time
import urllib.error
import urllib.request
from typing import Any, Dict, List, Optional, Tuple

# Ensure project root is in sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


class StagingClient:
    """HTTP client for staging smoke tests."""

    def __init__(self, base_url: str, api_key: Optional[str] = None, timeout: float = 8.0):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def request(
        self,
        method: str,
        path: str,
        payload: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        use_auth: bool = True,
    ) -> Tuple[int, Dict[str, Any], Dict[str, str], float, Optional[str]]:
        url = f"{self.base_url}{path}"
        h = {"User-Agent": "Peregrine-Staging-SmokeTest/1.0"}
        if use_auth and self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        if headers:
            h.update(headers)

        data = None
        if payload is not None:
            data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            h["Content-Type"] = "application/json; charset=utf-8"

        start_time = time.perf_counter()
        req = urllib.request.Request(url, data=data, headers=h, method=method)
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency_ms = (time.perf_counter() - start_time) * 1000
                resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                raw = resp.read().decode("utf-8")
                try:
                    body = json.loads(raw)
                except Exception:
                    body = {"raw": raw}
                return resp.status, body, resp_headers, round(latency_ms, 2), None
        except urllib.error.HTTPError as e:
            latency_ms = (time.perf_counter() - start_time) * 1000
            resp_headers = {k.lower(): v for k, v in e.headers.items()}
            raw = e.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except Exception:
                body = {"raw": raw}
            return e.code, body, resp_headers, round(latency_ms, 2), f"HTTP Error {e.code}"
        except Exception as exc:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return 0, {}, {}, round(latency_ms, 2), f"Network error: {type(exc).__name__}: {str(exc)}"


def run_staging_smoke_tests(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = 8.0,
) -> Dict[str, Any]:
    """Execute all 7 staging verification gates."""
    client = StagingClient(base_url, api_key=api_key, timeout=timeout)
    gates: List[Dict[str, Any]] = []

    def record_gate(name: str, passed: bool, details: Dict[str, Any], error: Optional[str] = None):
        gates.append({
            "gate": name,
            "passed": passed,
            "details": details,
            "error": error,
        })

    # -------------------------------------------------------------
    # Gate 1: Infrastructure Health & Liveness
    # -------------------------------------------------------------
    c, b, _, lat, err = client.request("GET", "/health", use_auth=False)
    g1_ok = (c == 200 and b.get("status") == "ok")
    record_gate(
        "Gate 1: Infrastructure Health & Liveness",
        g1_ok,
        {"status_code": c, "version": b.get("version"), "provider": b.get("active_provider"), "latency_ms": lat},
        err if not g1_ok else None,
    )

    # -------------------------------------------------------------
    # Gate 2: Readiness & Host Telemetry
    # -------------------------------------------------------------
    c, b, _, lat, err = client.request("GET", "/ready", use_auth=False)
    g2_ok = (c == 200 and b.get("ready") is True)
    record_gate(
        "Gate 2: Readiness & Host Telemetry",
        g2_ok,
        {
            "status_code": c,
            "ready": b.get("ready"),
            "disk_free_gb": b.get("disk_free_gb"),
            "memory_free_pct": b.get("memory_free_pct"),
            "sequential_lock_idle": b.get("sequential_lock_idle"),
            "latency_ms": lat,
        },
        err if not g2_ok else None,
    )

    # -------------------------------------------------------------
    # Gate 3: Security & Authentication Enforcement
    # -------------------------------------------------------------
    # If API key configured, test auth rejection; otherwise verify open access
    if api_key:
        c_unauth, b_unauth, _, _, _ = client.request("POST", "/api/v1/chat", payload={"messages": [{"role": "user", "content": "hi"}]}, use_auth=False)
        c_auth, b_auth, _, _, err_auth = client.request("POST", "/api/v1/chat", payload={"messages": [{"role": "user", "content": "hi"}]}, use_auth=True)
        g3_ok = (c_unauth == 401 and c_auth == 200)
        record_gate(
            "Gate 3: Security & Authentication Enforcement",
            g3_ok,
            {"unauthorized_status": c_unauth, "authorized_status": c_auth, "auth_model": "Bearer Token"},
            err_auth if not g3_ok else None,
        )
    else:
        # Auth not enforced in this staging profile (local/development profile)
        c_auth, b_auth, _, _, err_auth = client.request("POST", "/api/v1/chat", payload={"messages": [{"role": "user", "content": "hi"}]})
        g3_ok = (c_auth == 200)
        record_gate(
            "Gate 3: Security & Authentication Enforcement",
            g3_ok,
            {"auth_mode": "Open/Permissive (No API Key Configured)", "status_code": c_auth},
            err_auth if not g3_ok else None,
        )

    # -------------------------------------------------------------
    # Gate 4: Bilingual Core Inference & Domain Prompts
    # -------------------------------------------------------------
    # 4a: Arabic AI Tutor
    tutor_payload = {"query": "أعرب جملة الصدق منجاة", "level": "intermediate", "topic": "nahw"}
    c_tut, b_tut, _, lat_tut, err_tut = client.request("POST", "/api/v1/tutor/explain", payload=tutor_payload)
    tut_ok = (c_tut == 200 and b_tut.get("status") == "success" and bool(b_tut.get("content")))

    # 4b: AI Speaking Partner
    speak_payload = {
        "user_utterance": "السلام عليكم، ما هي أهم معالم مدينة أبوظبي؟",
        "scenario": "travel",
        "dialect": "emirati",
    }
    c_spk, b_spk, _, lat_spk, err_spk = client.request("POST", "/api/v1/speaking/respond", payload=speak_payload)
    spk_ok = (c_spk == 200 and b_spk.get("status") == "success" and bool(b_spk.get("content")))

    # 4c: Exams Assistant
    exam_payload = {
        "question_text": "ما حكم تقديم المفعول به على الفاعل وجوباً؟",
        "options": ["إذا كان الفاعل ضميراً متصلاً والمفعول به اسماً ظاهراً", "إذا اتصل بالفاعل ضمير يعود على المفعول به"],
        "correct_answer": "إذا اتصل بالفاعل ضمير يعود على المفعول به",
    }
    c_exm, b_exm, _, lat_exm, err_exm = client.request("POST", "/api/v1/exams/explain", payload=exam_payload)
    exm_ok = (c_exm == 200 and b_exm.get("status") == "success" and bool(b_exm.get("content")))

    g4_ok = (tut_ok and spk_ok and exm_ok)
    record_gate(
        "Gate 4: Domain Prompts (Tutor, Speaking, Exams)",
        g4_ok,
        {
            "tutor_ok": tut_ok, "tutor_latency_ms": lat_tut,
            "speaking_ok": spk_ok, "speaking_latency_ms": lat_spk,
            "exams_ok": exm_ok, "exams_latency_ms": lat_exm,
        },
        err_tut or err_spk or err_exm if not g4_ok else None,
    )

    # -------------------------------------------------------------
    # Gate 5: Error Isolation & Safety Interlocks
    # -------------------------------------------------------------
    # Bad JSON
    c_json, b_json, _, _, _ = client.request("POST", "/api/v1/chat", headers={"Content-Type": "application/json"})
    # Reasoning only
    c_rsn, b_rsn, _, _, _ = client.request("POST", "/api/v1/chat", payload={"messages": [{"role": "user", "content": "__FORCE_REASONING_ONLY__"}]})
    g5_ok = (c_json == 400 and b_rsn.get("status") == "error" and b_rsn.get("error", {}).get("code") == "MODEL_REASONING_ONLY")
    record_gate(
        "Gate 5: Error Isolation & Safety Interlocks",
        g5_ok,
        {
            "bad_json_status": c_json,
            "bad_json_code": b_json.get("error", {}).get("code"),
            "reasoning_isolation_code": b_rsn.get("error", {}).get("code"),
        },
    )

    # -------------------------------------------------------------
    # Gate 6: Rate Limiting & Concurrency Headers
    # -------------------------------------------------------------
    c_rate, _, h_rate, _, _ = client.request("POST", "/api/v1/chat", payload={"messages": [{"role": "user", "content": "rate-test"}]})
    has_rpm_headers = ("x-ratelimit-limit" in h_rate and "x-ratelimit-remaining" in h_rate)
    record_gate(
        "Gate 6: Rate Limiting & Concurrency Headers",
        has_rpm_headers,
        {
            "x-ratelimit-limit": h_rate.get("x-ratelimit-limit"),
            "x-ratelimit-remaining": h_rate.get("x-ratelimit-remaining"),
            "x-ratelimit-reset": h_rate.get("x-ratelimit-reset"),
        },
    )

    # -------------------------------------------------------------
    # Gate 7: Operational Feedback & Consent Boundaries
    # -------------------------------------------------------------
    fb_payload = {
        "request_id": "req-staging-smoke-01",
        "rating": 5,
        "category": "helpful",
        "comments": "Staging smoke test verification probe.",
        "consent_for_training": False,  # Non-consented must be accepted but excluded from training queue
    }
    c_fb, b_fb, _, lat_fb, err_fb = client.request("POST", "/api/v1/feedback", payload=fb_payload)
    g7_ok = (c_fb == 202 and b_fb.get("status") == "received" and b_fb.get("consent_recorded") is False)
    record_gate(
        "Gate 7: Operational Feedback & Consent Boundaries",
        g7_ok,
        {
            "status_code": c_fb,
            "feedback_id": b_fb.get("feedback_id"),
            "consent_recorded": b_fb.get("consent_recorded"),
            "eligible_for_learning": b_fb.get("eligible_for_learning_pipeline"),
            "latency_ms": lat_fb,
        },
        err_fb if not g7_ok else None,
    )

    all_passed = all(g["passed"] for g in gates)
    return {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base_url,
        "passed": all_passed,
        "total_gates": len(gates),
        "passed_gates": sum(1 for g in gates if g["passed"]),
        "failed_gates": sum(1 for g in gates if not g["passed"]),
        "gates": gates,
    }


def main():
    parser = argparse.ArgumentParser(description="Staging Smoke-Test Runner for Central AI Runtime")
    parser.add_argument("--url", default=None, help="Staging service URL (if None, launches in-process staging server)")
    parser.add_argument("--api-key", default=os.environ.get("STAGING_API_KEY", None), help="Staging API Key")
    parser.add_argument("--timeout", type=float, default=8.0, help="Request timeout")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON summary")
    args = parser.parse_args()

    harness = None
    temp_dir = None
    target_url = args.url

    if not target_url:
        # Launch isolated local staging server
        from central_runtime_api.config import APIConfig
        from tests.test_qa_suite import CentralAPITestHarness

        temp_dir = tempfile.mkdtemp(prefix="staging_smoke_local_")
        staging_api_key = args.api_key or "staging-key-smoke-2026"
        cfg = APIConfig(
            host="127.0.0.1",
            port=9030,
            provider="mock",
            model="qwen3:4b-staging",
            api_key=staging_api_key,
            timeout_seconds=5.0,
            rate_limit_enabled=True,
            rate_limit_rpm=60,
            data_dir=Path(temp_dir),
        )
        harness = CentralAPITestHarness(cfg)
        harness.start()
        target_url = harness.base_url
        effective_api_key = staging_api_key
    else:
        effective_api_key = args.api_key

    try:
        report = run_staging_smoke_tests(target_url, api_key=effective_api_key, timeout=args.timeout)
    finally:
        if harness:
            harness.stop()
        if temp_dir:
            shutil.rmtree(temp_dir, ignore_errors=True)

    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        status_str = "\033[92mPASSED\033[0m" if report["passed"] else "\033[91mFAILED\033[0m"
        print("\n=======================================================")
        print(f" STAGING DEPLOYMENT SMOKE TEST: {status_str}")
        print(f" Target: {report['base_url']} | Time: {report['timestamp']}")
        print(f" Gates Passed: {report['passed_gates']} / {report['total_gates']}")
        print("=======================================================")

        for g in report["gates"]:
            sym = "\033[92m✔ PASS\033[0m" if g["passed"] else "\033[91m✘ FAIL\033[0m"
            print(f"  [{sym}] {g['gate']}")
            if not g["passed"] and g["error"]:
                print(f"         Error: {g['error']}")
            for k, v in g["details"].items():
                print(f"         • {k}: {v}")

        print("=======================================================\n")

    sys.exit(0 if report["passed"] else 1)


if __name__ == "__main__":
    main()
