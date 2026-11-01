#!/usr/bin/env python3
"""Automated Health and Readiness Check Script for Central AI Runtime & API.

Verifies service liveness, readiness probes, host resource headroom,
and synthetic inference latency. Supports both human-readable terminal
output and machine-readable JSON reports.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from typing import Any, Dict, Optional, Tuple


def probe_url(
    url: str,
    method: str = "GET",
    payload: Optional[Dict[str, Any]] = None,
    headers: Optional[Dict[str, str]] = None,
    timeout: float = 5.0,
) -> Tuple[int, Dict[str, Any], float, Optional[str]]:
    """Execute HTTP probe and return (status_code, body, latency_ms, error_msg)."""
    h = {"User-Agent": "CentralAI-HealthChecker/0.1.0"}
    if headers:
        h.update(headers)

    data = None
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        h["Content-Type"] = "application/json; charset=utf-8"

    req = urllib.request.Request(url, data=data, headers=h, method=method)
    start_time = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            latency_ms = (time.perf_counter() - start_time) * 1000
            raw = resp.read().decode("utf-8")
            try:
                body = json.loads(raw)
            except Exception:
                body = {"raw": raw}
            return resp.status, body, round(latency_ms, 2), None
    except urllib.error.HTTPError as e:
        latency_ms = (time.perf_counter() - start_time) * 1000
        raw = e.read().decode("utf-8")
        try:
            body = json.loads(raw)
        except Exception:
            body = {"raw": raw}
        return e.code, body, round(latency_ms, 2), f"HTTP Error {e.code}: {e.reason}"
    except Exception as exc:
        latency_ms = (time.perf_counter() - start_time) * 1000
        return 0, {}, round(latency_ms, 2), f"Network/Connection failure: {type(exc).__name__}: {str(exc)}"


def perform_health_check(
    base_url: str,
    api_key: Optional[str] = None,
    timeout: float = 5.0,
    deep_probe: bool = True,
) -> Dict[str, Any]:
    """Execute standard health check matrix."""
    base = base_url.rstrip("/")
    result: Dict[str, Any] = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "base_url": base,
        "healthy": False,
        "status": "UNHEALTHY",
        "probes": {},
    }

    # 1. Health Probe (/health)
    h_code, h_body, h_latency, h_err = probe_url(f"{base}/health", timeout=timeout)
    result["probes"]["health"] = {
        "status_code": h_code,
        "latency_ms": h_latency,
        "passed": (h_code == 200 and h_body.get("status") == "ok"),
        "error": h_err,
        "data": h_body,
    }

    # 2. Readiness Probe (/ready)
    r_code, r_body, r_latency, r_err = probe_url(f"{base}/ready", timeout=timeout)
    result["probes"]["ready"] = {
        "status_code": r_code,
        "latency_ms": r_latency,
        "passed": (r_code == 200 and r_body.get("ready") is True),
        "error": r_err,
        "data": r_body,
    }

    # 3. Optional Deep Synthetic Inference Probe (/api/v1/chat)
    if deep_probe:
        headers = {}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        chat_payload = {
            "messages": [{"role": "user", "content": "ping"}],
            "parameters": {"max_tokens": 16, "temperature": 0.1},
        }
        c_code, c_body, c_latency, c_err = probe_url(
            f"{base}/api/v1/chat",
            method="POST",
            payload=chat_payload,
            headers=headers,
            timeout=timeout,
        )
        result["probes"]["inference_ping"] = {
            "status_code": c_code,
            "latency_ms": c_latency,
            "passed": (c_code == 200 and c_body.get("status") == "success"),
            "error": c_err,
            "data": {
                "model": c_body.get("model"),
                "provider": c_body.get("provider"),
                "finish_reason": c_body.get("telemetry", {}).get("finish_reason"),
            },
        }

    # Evaluate overall status
    health_ok = result["probes"]["health"]["passed"]
    ready_ok = result["probes"]["ready"]["passed"]
    deep_ok = result["probes"].get("inference_ping", {}).get("passed", True)

    if health_ok and ready_ok and deep_ok:
        result["healthy"] = True
        result["status"] = "HEALTHY"
    elif health_ok:
        result["healthy"] = False
        result["status"] = "DEGRADED"
    else:
        result["healthy"] = False
        result["status"] = "UNHEALTHY"

    return result


def main():
    parser = argparse.ArgumentParser(description="Central AI Runtime Automated Health Checker")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="Base URL of Central AI service")
    parser.add_argument("--api-key", default=None, help="Optional API key for authenticated endpoints")
    parser.add_argument("--timeout", type=float, default=5.0, help="HTTP timeout in seconds")
    parser.add_argument("--no-deep", action="store_true", help="Skip deep inference ping probe")
    parser.add_argument("--json", action="store_true", help="Output machine-readable JSON format")
    args = parser.parse_args()

    results = perform_health_check(
        base_url=args.url,
        api_key=args.api_key,
        timeout=args.timeout,
        deep_probe=not args.no_deep,
    )

    if args.json:
        print(json.dumps(results, indent=2, ensure_ascii=False))
    else:
        status = results["status"]
        color_code = "\033[92m" if status == "HEALTHY" else ("\033[93m" if status == "DEGRADED" else "\033[91m")
        reset_code = "\033[0m"

        print(f"\n=======================================================")
        print(f" Central AI Runtime Service Health Check: {color_code}{status}{reset_code}")
        print(f" Target: {results['base_url']} | Time: {results['timestamp']}")
        print(f"=======================================================")

        for probe_name, p in results["probes"].items():
            probe_symbol = "✔" if p["passed"] else "✘"
            symbol_color = "\033[92m" if p["passed"] else "\033[91m"
            print(f"  {symbol_color}[{probe_symbol}]{reset_code} {probe_name.upper():<16} : HTTP {p['status_code']} ({p['latency_ms']} ms)")
            if not p["passed"] and p["error"]:
                print(f"      Reason: {p['error']}")

        ready_data = results["probes"].get("ready", {}).get("data", {})
        if ready_data:
            print("\n  Diagnostic Telemetry:")
            print(f"    - Active Provider   : {ready_data.get('active_provider')}")
            print(f"    - Active Model      : {ready_data.get('active_model')}")
            print(f"    - Disk Space Free   : {ready_data.get('disk_free_gb')} GB")
            print(f"    - Memory Free Pct   : {ready_data.get('memory_free_pct')}%")
            print(f"    - Sequential Lock   : {'IDLE' if ready_data.get('sequential_lock_idle') else 'BUSY'}")

        print(f"=======================================================\n")

    sys.exit(0 if results["healthy"] else 1)


if __name__ == "__main__":
    main()
