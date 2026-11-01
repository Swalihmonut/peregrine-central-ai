#!/usr/bin/env python3
"""Unified QA Test Runner and Machine-Readable QA Report Generator for Beta V-001.

Executes all automated unit, integration, and staging smoke test suites.
Generates:
- `reports/BETA_V001_API_QA_RESULTS.json` (Machine-readable full QA report)
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import platform
import shutil
import sys
import tempfile
import time
import unittest
from typing import Any, Dict, List

# Ensure project root is in sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from tests.test_qa_suite import TestBetaV001CentralAPIQA
from tests.test_central_api import TestCentralAIRuntime
from tests.staging_smoke_test import run_staging_smoke_tests
from central_runtime_api.health_check import perform_health_check
from central_runtime_api.config import APIConfig
from tests.test_qa_suite import CentralAPITestHarness


class DetailedJSONTestResult(unittest.TestResult):
    """Custom TestResult capturing per-test metrics for JSON reporting."""

    def __init__(self):
        super().__init__()
        self.test_records: List[Dict[str, Any]] = []
        self._test_start: float = 0.0

    def startTest(self, test: unittest.TestCase):
        super().startTest(test)
        self._test_start = time.perf_counter()

    def addSuccess(self, test: unittest.TestCase):
        super().addSuccess(test)
        duration_ms = round((time.perf_counter() - self._test_start) * 1000, 2)
        doc = (test._testMethodDoc or "").strip()
        self.test_records.append({
            "test_id": test.id(),
            "name": test._testMethodName,
            "description": doc,
            "status": "PASS",
            "duration_ms": duration_ms,
            "error": None,
        })

    def addFailure(self, test: unittest.TestCase, err):
        super().addFailure(test, err)
        duration_ms = round((time.perf_counter() - self._test_start) * 1000, 2)
        doc = (test._testMethodDoc or "").strip()
        self.test_records.append({
            "test_id": test.id(),
            "name": test._testMethodName,
            "description": doc,
            "status": "FAIL",
            "duration_ms": duration_ms,
            "error": self._exc_info_to_string(err, test),
        })

    def addError(self, test: unittest.TestCase, err):
        super().addError(test, err)
        duration_ms = round((time.perf_counter() - self._test_start) * 1000, 2)
        doc = (test._testMethodDoc or "").strip()
        self.test_records.append({
            "test_id": test.id(),
            "name": test._testMethodName,
            "description": doc,
            "status": "ERROR",
            "duration_ms": duration_ms,
            "error": self._exc_info_to_string(err, test),
        })


def categorize_tests(test_records: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Group test records into the 13 required Beta V-001 QA categories."""
    categories: Dict[str, List[Dict[str, Any]]] = {
        "1_health_and_readiness": [],
        "2_authentication_and_authorization": [],
        "3_valid_and_invalid_requests": [],
        "4_arabic_and_english_handling": [],
        "5_conversation_history": [],
        "6_model_timeout_and_unavailable_provider": [],
        "7_empty_model_responses": [],
        "8_rate_limits_and_concurrency": [],
        "9_usage_tracking": [],
        "10_feedback_submission": [],
        "11_consent_enforcement": [],
        "12_provider_fallback": [],
        "13_cloud_environment_configuration": [],
        "integration_regression_suite": [],
    }

    for r in test_records:
        tid = r["test_id"].lower()
        name = r["name"].lower()
        if "testcentralairuntime" in tid:
            categories["integration_regression_suite"].append(r)
        elif any(f"test_{i:02d}" in name for i in (1, 2, 3)):
            categories["1_health_and_readiness"].append(r)
        elif any(f"test_{i:02d}" in name for i in (4, 5, 6, 7)):
            categories["2_authentication_and_authorization"].append(r)
        elif any(f"test_{i:02d}" in name for i in (8, 9, 10, 11, 12)):
            categories["3_valid_and_invalid_requests"].append(r)
        elif any(f"test_{i:02d}" in name for i in (13, 14, 15, 16)):
            categories["4_arabic_and_english_handling"].append(r)
        elif any(f"test_{i:02d}" in name for i in (17, 18)):
            categories["5_conversation_history"].append(r)
        elif any(f"test_{i:02d}" in name for i in (19, 20, 21)):
            categories["6_model_timeout_and_unavailable_provider"].append(r)
        elif any(f"test_{i:02d}" in name for i in (22, 23)):
            categories["7_empty_model_responses"].append(r)
        elif any(f"test_{i:02d}" in name for i in (24, 25, 26)):
            categories["8_rate_limits_and_concurrency"].append(r)
        elif "test_27" in name:
            categories["9_usage_tracking"].append(r)
        elif any(f"test_{i:02d}" in name for i in (28, 29)):
            categories["10_feedback_submission"].append(r)
        elif any(f"test_{i:02d}" in name for i in (30, 31, 32)):
            categories["11_consent_enforcement"].append(r)
        elif any(f"test_{i:02d}" in name for i in (33, 34)):
            categories["12_provider_fallback"].append(r)
        elif any(f"test_{i:02d}" in name for i in (35, 36)):
            categories["13_cloud_environment_configuration"].append(r)
        else:
            categories["3_valid_and_invalid_requests"].append(r)

    summary: Dict[str, Dict[str, Any]] = {}
    for cat_name, records in categories.items():
        total = len(records)
        passed = sum(1 for x in records if x["status"] == "PASS")
        failed = sum(1 for x in records if x["status"] in ("FAIL", "ERROR"))
        total_duration = round(sum(x["duration_ms"] for x in records), 2)
        summary[cat_name] = {
            "total_tests": total,
            "passed": passed,
            "failed": failed,
            "status": "PASS" if (failed == 0 and total > 0) else ("EMPTY" if total == 0 else "FAIL"),
            "total_duration_ms": total_duration,
            "tests": records,
        }
    return summary


def main():
    parser = argparse.ArgumentParser(description="Beta V-001 QA Test Runner")
    parser.add_argument("--output", default="reports/BETA_V001_API_QA_RESULTS.json", help="Path to output JSON report")
    args = parser.parse_args()

    suite_start = time.perf_counter()
    print("\n=======================================================")
    print(" Executing Beta V-001 Central API & Cloud QA Suite")
    print("=======================================================")

    # 1. Run Unit & Automated QA Suites
    suite = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite.addTests(loader.loadTestsFromTestCase(TestBetaV001CentralAPIQA))
    suite.addTests(loader.loadTestsFromTestCase(TestCentralAIRuntime))

    runner = DetailedJSONTestResult()
    suite.run(runner)
    duration_total = round((time.perf_counter() - suite_start), 3)

    # 2. Run Isolated Staging Smoke Test
    print(" [✓] Unit & Automated QA Suites complete. Running Isolated Staging Smoke Test...")
    temp_dir = tempfile.mkdtemp(prefix="staging_qa_run_")
    staging_cfg = APIConfig(
        host="127.0.0.1",
        port=9035,
        provider="mock",
        model="qwen3:4b-staging",
        api_key="qa-staging-verify-token",
        timeout_seconds=5.0,
        rate_limit_enabled=True,
        rate_limit_rpm=60,
        data_dir=Path(temp_dir),
    )
    staging_harness = CentralAPITestHarness(staging_cfg)
    staging_harness.start()

    try:
        staging_report = run_staging_smoke_tests(
            base_url=staging_harness.base_url,
            api_key="qa-staging-verify-token",
        )
        health_check_report = perform_health_check(
            base_url=staging_harness.base_url,
            api_key="qa-staging-verify-token",
            deep_probe=True,
        )
    finally:
        staging_harness.stop()
        shutil.rmtree(temp_dir, ignore_errors=True)

    # 3. Categorize & Compile QA Report
    categorized = categorize_tests(runner.test_records)
    total_tests = runner.testsRun
    total_passed = len(runner.test_records) - len(runner.failures) - len(runner.errors)
    total_failed = len(runner.failures) + len(runner.errors)

    report_payload = {
        "metadata": {
            "version": "1.0.0 (Beta V-001)",
            "mission": "Central API, Hosting & Infrastructure QA",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "platform": platform.platform(),
            "python_version": platform.python_version(),
            "total_execution_time_seconds": duration_total,
        },
        "executive_summary": {
            "total_tests": total_tests,
            "passed": total_passed,
            "failed": total_failed,
            "success_rate_percent": round((total_passed / total_tests) * 100, 2) if total_tests > 0 else 0,
            "all_suites_passed": (total_failed == 0 and staging_report["passed"]),
            "cloud_readiness_status": (
                "AUTOMATED_STAGING_VERIFIED_CLOUD_DEPLOYMENT_PENDING"
                if (total_failed == 0 and staging_report["passed"])
                else "FAILED"
            ),
            "cloud_readiness_mandate_notice": (
                "In strict accordance with the mission protocol, cloud readiness cannot be claimed "
                "until the actual remote cloud-hosted instance has been provisioned and tested."
            ),
        },
        "staging_smoke_test_summary": staging_report,
        "health_check_probe_summary": health_check_report,
        "category_breakdown": categorized,
    }

    # Write report file
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report_payload, indent=2, ensure_ascii=False), encoding="utf-8")

    # Console Summary
    print("\n=======================================================")
    print(" QA MISSION RESULTS SUMMARY")
    print(f" Total Tests Executed : {total_tests}")
    print(f" Passed               : {total_passed}")
    print(f" Failed               : {total_failed}")
    print(f" Staging Smoke Gates  : {staging_report['passed_gates']} / {staging_report['total_gates']} Passed")
    print(f" Health Probe Status  : {health_check_report['status']}")
    print(f" Machine-Readable JSON: {out_path}")
    print("=======================================================\n")

    for cat_name, cat in categorized.items():
        sym = "✔ PASS" if cat["status"] == "PASS" else ("- EMPTY" if cat["status"] == "EMPTY" else "✘ FAIL")
        print(f"  [{sym}] {cat_name:<42} : {cat['passed']}/{cat['total_tests']} tests ({cat['total_duration_ms']} ms)")

    print("\n=======================================================")
    print(f" Cloud Readiness Status: {report_payload['executive_summary']['cloud_readiness_status']}")
    print(f" Note: {report_payload['executive_summary']['cloud_readiness_mandate_notice']}")
    print("=======================================================\n")

    sys.exit(0 if (total_failed == 0 and staging_report["passed"]) else 1)


if __name__ == "__main__":
    main()
