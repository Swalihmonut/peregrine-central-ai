#!/usr/bin/env python3
"""
PyArud Isolated Prosody Service (Beta V-001)
Peregrine Arabic AI Unified Platform — Specialist Service Layer

Provides lightweight, zero-external-dependency HTTP REST service for
Classical Arabic Prosody and Metre Analysis (*'Ilm al-'Arud wa al-Qafiyah*).

Runtime: CPython 3.12 (Dedicated .venv-prosody environment)
License: MIT
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import signal
import sys
import time
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

# Arabic diacritics Unicode range (Harakat & Tanween)
HARAKAT_REGEX = re.compile(r"[\u064B-\u0652\u0670]")
ARABIC_LETTERS_REGEX = re.compile(r"[\u0621-\u064A\u0671]")

logging.basicConfig(
    level=logging.INFO,
    format='{"time":"%(asctime)s", "level":"%(levelname)s", "message":"%(message)s"}',
)
logger = logging.getLogger("pyarud_service")


class PyArudEngine:
    """Singleton wrapper around PyArud ArudhProcessor with cached initialization."""

    def __init__(self) -> None:
        start_time = time.perf_counter()
        from pyarud.processor import ArudhProcessor

        self.processor = ArudhProcessor()
        # Warm up internal regexes with a canary scansion
        _ = self.processor.analyze_verse("فَعُولُنْ مَفَاعِيلُنْ")
        self.init_duration_ms = (time.perf_counter() - start_time) * 1000
        logger.info(f"PyArudEngine initialized in {self.init_duration_ms:.2f} ms")

    @staticmethod
    def calculate_vowel_density(text: str) -> float:
        """
        Calculates diagnostic vowel density: count(Harakat) / count(Arabic Letters).
        Non-destructive advisory metric; does not reject scansion.
        """
        letters = len(ARABIC_LETTERS_REGEX.findall(text))
        if letters == 0:
            return 0.0
        harakat = len(HARAKAT_REGEX.findall(text))
        return round(harakat / letters, 3)

    def analyze(
        self,
        sadr: str,
        ajuz: str = "",
        min_confidence: float = 0.85,
    ) -> dict[str, Any]:
        """
        Analyzes a single Arabic verse with dual-gate prose filtering.
        """
        start_time = time.perf_counter()
        combined_text = f"{sadr} {ajuz}".strip()
        vowel_density = self.calculate_vowel_density(combined_text)

        # Execute deterministic scansion
        raw_analysis = self.processor.analyze_verse(sadr_text=sadr, ajuz_text=ajuz)

        # Gate 1: Check score against threshold
        score = float(raw_analysis.score or 0.0)
        passes_score_gate = score >= min_confidence

        # Gate 2: Check foot structural integrity
        broken_feet = 0
        sadr_feet_data = []
        if raw_analysis.sadr:
            for f in raw_analysis.sadr.feet:
                is_ok = f.status == "ok"
                if not is_ok:
                    broken_feet += 1
                sadr_feet_data.append(
                    {
                        "foot_index": f.foot_index,
                        "base_tafeela": f.base_tafeela,
                        "actual_tafeela": f.actual_tafeela or f.base_tafeela,
                        "pattern": f.actual_segment,
                        "zihaf_name_ar": f.zihaf_name_ar,
                        "zihaf_name_en": f.zihaf_name_en,
                        "status": f.status,
                    }
                )

        ajuz_feet_data = []
        if raw_analysis.ajuz:
            for f in raw_analysis.ajuz.feet:
                is_ok = f.status == "ok"
                if not is_ok:
                    broken_feet += 1
                ajuz_feet_data.append(
                    {
                        "foot_index": f.foot_index,
                        "base_tafeela": f.base_tafeela,
                        "actual_tafeela": f.actual_tafeela or f.base_tafeela,
                        "pattern": f.actual_segment,
                        "zihaf_name_ar": f.zihaf_name_ar,
                        "zihaf_name_en": f.zihaf_name_en,
                        "status": f.status,
                    }
                )

        passes_foot_gate = broken_feet == 0
        is_poetic = raw_analysis.is_valid and passes_score_gate and passes_foot_gate

        # Qafiyah extraction
        qafiyah_data = None
        if raw_analysis.qafiyah and raw_analysis.qafiyah.rawi:
            q = raw_analysis.qafiyah
            qafiyah_data = {
                "rawi": q.rawi,
                "rawi_haraka": q.rawi_haraka,
                "wasl": q.wasl,
                "khuruj": q.khuruj,
                "ridf": q.ridf,
                "tasees": q.tasees,
                "dakhil": q.dakhil,
                "qafiyah_span": q.qafiyah_text,
                "qafiyah_pattern": q.qafiyah_pattern,
                "qafiyah_type_ar": q.qafiyah_type_ar,
                "qafiyah_type_en": q.qafiyah_type_en,
            }

        elapsed_ms = (time.perf_counter() - start_time) * 1000

        # Construct response payload
        return {
            "status": "success",
            "execution_time_ms": round(elapsed_ms, 3),
            "provenance": {
                "engine": "pyarud",
                "engine_version": "1.0.0",
                "ruleset": "Farahidian (Al-Khalil ibn Ahmad)",
                "runtime": f"CPython {sys.version.split()[0]}",
            },
            "data": {
                "is_poetic": is_poetic,
                "meter_key": raw_analysis.meter_key if is_poetic else None,
                "meter_name_ar": raw_analysis.meter_name_ar if is_poetic else "غير موزون / نثر",
                "meter_name_en": raw_analysis.meter_name_en if is_poetic else "Unmetered / Prose",
                "bahr_type": raw_analysis.bahr_type if is_poetic else None,
                "similarity_score": round(score, 3),
                "is_valid_structure": raw_analysis.is_valid,
                "vowel_density": vowel_density,
                "density_warning": vowel_density < 0.35,
                "broken_feet_count": broken_feet,
                "rejection_reason": (
                    None
                    if is_poetic
                    else ("PROSE_OR_FRACTURED_METER" if broken_feet > 0 else "LOW_SIMILARITY_SCORE")
                ),
                "sadr": {
                    "original_text": sadr,
                    "arudi_text": raw_analysis.sadr.arudi_text if raw_analysis.sadr else "",
                    "binary_pattern": raw_analysis.sadr.pattern if raw_analysis.sadr else "",
                    "feet": sadr_feet_data,
                },
                "ajuz": (
                    {
                        "original_text": ajuz,
                        "arudi_text": raw_analysis.ajuz.arudi_text if raw_analysis.ajuz else "",
                        "binary_pattern": raw_analysis.ajuz.pattern if raw_analysis.ajuz else "",
                        "feet": ajuz_feet_data,
                    }
                    if ajuz
                    else None
                ),
                "qafiyah": qafiyah_data,
            },
        }


# Global engine instance
ENGINE: PyArudEngine | None = None


class ProsodyRequestHandler(BaseHTTPRequestHandler):
    """HTTP Request Handler serving health checks and prosody scansion."""

    def _set_headers(self, status_code: int = 200) -> None:
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type, Authorization, X-Request-ID")
        self.end_headers()

    def do_OPTIONS(self) -> None:
        self._set_headers(HTTPStatus.NO_CONTENT)

    def do_GET(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        if path in ("", "/health", "/healthz"):
            self._set_headers(HTTPStatus.OK)
            resp = {
                "status": "ok",
                "service": "peregrine-prosody-sidecar",
                "version": "1.0.0",
                "engine": "pyarud",
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        if path == "/ready":
            is_ready = ENGINE is not None
            self._set_headers(HTTPStatus.OK if is_ready else HTTPStatus.SERVICE_UNAVAILABLE)
            resp = {
                "ready": is_ready,
                "engine": "pyarud",
                "version": "1.0.0",
                "canary_passed": is_ready,
            }
            self.wfile.write(json.dumps(resp).encode("utf-8"))
            return

        self._set_headers(HTTPStatus.NOT_FOUND)
        err = {"status": "error", "error": {"code": "NOT_FOUND", "message_en": "Endpoint not found"}}
        self.wfile.write(json.dumps(err).encode("utf-8"))

    def do_POST(self) -> None:
        path = self.path.split("?")[0].rstrip("/")
        if path not in ("/api/v1/prosody/analyze", "/analyze"):
            self._set_headers(HTTPStatus.NOT_FOUND)
            err = {"status": "error", "error": {"code": "NOT_FOUND", "message_en": "Endpoint not found"}}
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Check engine readiness
        if ENGINE is None:
            self._set_headers(HTTPStatus.SERVICE_UNAVAILABLE)
            err = {
                "status": "error",
                "error": {
                    "code": "SERVICE_INITIALIZING",
                    "message_en": "Prosody engine is initializing",
                    "message_ar": "المحرك العروضي قيد التهيئة",
                },
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        # Read and validate body
        content_length = int(self.headers.get("Content-Length", 0))
        if content_length == 0:
            self._set_headers(HTTPStatus.BAD_REQUEST)
            err = {
                "status": "error",
                "error": {
                    "code": "EMPTY_PAYLOAD",
                    "message_en": "Request body cannot be empty",
                    "message_ar": "نص الطلب لا يمكن أن يكون فارغاً",
                },
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        try:
            body = self.rfile.read(content_length).decode("utf-8")
            data = json.loads(body)
        except Exception as e:
            self._set_headers(HTTPStatus.BAD_REQUEST)
            err = {
                "status": "error",
                "error": {
                    "code": "INVALID_JSON",
                    "message_en": f"Invalid JSON payload: {str(e)}",
                    "message_ar": "صيغة JSON غير صالحة",
                },
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        sadr = data.get("sadr", "").strip()
        ajuz = data.get("ajuz", "").strip()
        min_conf = float(data.get("min_confidence", 0.85))

        if not sadr:
            self._set_headers(HTTPStatus.BAD_REQUEST)
            err = {
                "status": "error",
                "error": {
                    "code": "MISSING_SADR",
                    "message_en": "Field 'sadr' (first hemistich) is required",
                    "message_ar": "حقل 'sadr' (الصدر) مطلوب",
                },
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))
            return

        try:
            result = ENGINE.analyze(sadr=sadr, ajuz=ajuz, min_confidence=min_conf)
            self._set_headers(HTTPStatus.OK)
            self.wfile.write(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        except Exception as e:
            logger.error(f"Scansion error: {e}", exc_info=True)
            self._set_headers(HTTPStatus.INTERNAL_SERVER_ERROR)
            err = {
                "status": "error",
                "error": {
                    "code": "SCANSION_EXCEPTION",
                    "message_en": str(e),
                    "message_ar": "حدث خطأ غير متوقع أثناء المعالجة العروضية",
                },
            }
            self.wfile.write(json.dumps(err).encode("utf-8"))

    def log_message(self, format: str, *args: Any) -> None:
        """Structured access logger."""
        logger.info(f"{self.address_string()} - {format % args}")


def run_service(host: str = "127.0.0.1", port: int = 8089) -> None:
    """Starts the Threading HTTP Server."""
    global ENGINE
    print(f"Initializing PyArud Prosody Sidecar on http://{host}:{port} ...")
    ENGINE = PyArudEngine()

    server = ThreadingHTTPServer((host, port), ProsodyRequestHandler)

    def shutdown_handler(signum: int, frame: Any) -> None:
        print(f"\nReceived signal {signum}. Shutting down PyArud sidecar gracefully...")
        server.shutdown()
        server.server_close()
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown_handler)
    signal.signal(signal.SIGTERM, shutdown_handler)

    print(f"PyArud Prosody Sidecar ready and listening on http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="PyArud Prosody HTTP Sidecar")
    parser.add_argument("--host", default="127.0.0.1", help="Host interface to bind")
    parser.add_argument("--port", type=int, default=8089, help="TCP Port to listen on")
    args = parser.parse_args()

    run_service(host=args.host, port=args.port)
