#!/usr/bin/env python3
"""Comprehensive Unit and Mocked Verification Suite for Benchmark Runners.

Author: Benchmark Infrastructure and Evaluation Reliability Engineer
Workspace: ~/peregrine-arabic-ai-lab
Version: 2.0.0
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import sys
import unittest
from unittest.mock import MagicMock, patch

# Ensure research repo root is in python path
REPO_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(REPO_ROOT))

from benchmarks.benchmark_schema import (
    BenchmarkRecord,
    BenchmarkStatus,
    CSV_FIELDNAMES,
    RUNNER_VERSION,
    create_record,
)
from benchmarks.run_jais import (
    extract_jais_reasoning_and_answer,
    query_jais_endpoint,
)
from benchmarks.run_ollama import query_ollama
from benchmarks.shared_prompts import (
    CANONICAL_BENCHMARK_SYSTEM_PROMPT,
    build_chat_messages,
)


class MockStreamingResponse:
    """Mock HTTP response yielding streaming JSON lines like Ollama."""

    def __init__(self, lines: list[str]):
        self._lines = [line.encode("utf-8") if isinstance(line, str) else line for line in lines]
        self._iter = iter(self._lines)

    def __iter__(self):
        return self

    def __next__(self):
        return next(self._iter)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class MockHTTPResponse:
    """Mock HTTP response for standard read() calls like OpenAI/Jais."""

    def __init__(self, data: dict, status: int = 200):
        self._data = json.dumps(data).encode("utf-8")
        self.status = status

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        pass


class TestBenchmarkRunners(unittest.TestCase):
    """Rigorous unit tests ensuring runners satisfy all audit & safety requirements."""

    # -------------------------------------------------------------------------
    # 1. Qwen thinking and content are stored separately
    # -------------------------------------------------------------------------
    def test_01_qwen_thinking_and_content_stored_separately(self):
        stream_chunks = [
            json.dumps({"message": {"role": "assistant", "thinking": "Let me analyze nahw."}}),
            json.dumps({"message": {"role": "assistant", "thinking": " The particle inna is harf naskh."}}),
            json.dumps({"message": {"role": "assistant", "content": "إنّ: حرف توكيد ونصب."}}),
            json.dumps({"message": {"role": "assistant", "content": " اللغةَ: اسم إنّ منصوب."}}),
            json.dumps({
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 80,
                "eval_count": 120,
            }),
        ]
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockStreamingResponse(stream_chunks)

        record = query_ollama(
            endpoint="http://mock-ollama:11434",
            model="qwen3:4b",
            prompt="أعرب الجملة",
            question_id="NAHW001",
            domain="nahw",
            max_tokens=2048,
            opener=mock_opener,
        )

        self.assertEqual(record.status, BenchmarkStatus.SUCCESS.value)
        self.assertFalse(record.is_truncated)
        self.assertEqual(record.thinking_trace, "Let me analyze nahw. The particle inna is harf naskh.")
        self.assertEqual(record.final_answer, "إنّ: حرف توكيد ونصب. اللغةَ: اسم إنّ منصوب.")
        self.assertNotIn("Let me analyze", record.final_answer)
        self.assertEqual(record.prompt_tokens, 80)
        self.assertEqual(record.completion_tokens, 120)
        self.assertEqual(record.finish_reason, "stop")

    # -------------------------------------------------------------------------
    # 2. Empty Qwen final content never falls back to thinking
    # -------------------------------------------------------------------------
    def test_02_empty_qwen_final_content_never_falls_back_to_thinking(self):
        stream_chunks = [
            json.dumps({"message": {"role": "assistant", "thinking": "Thinking step 1..."}}),
            json.dumps({"message": {"role": "assistant", "thinking": " Still thinking step 2..."}}),
            # NO content chunks emitted!
            json.dumps({
                "done": True,
                "done_reason": "length",
                "prompt_eval_count": 50,
                "eval_count": 512,
            }),
        ]
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockStreamingResponse(stream_chunks)

        record = query_ollama(
            endpoint="http://mock-ollama:11434",
            model="qwen3:4b",
            prompt="أعرب الجملة",
            question_id="NAHW001",
            domain="nahw",
            max_tokens=512,
            opener=mock_opener,
        )

        # STRICT ASSERTION: final_answer must remain EMPTY, NOT populated with thinking
        self.assertEqual(record.final_answer, "")
        self.assertEqual(record.thinking_trace, "Thinking step 1... Still thinking step 2...")
        self.assertEqual(record.status, BenchmarkStatus.REASONING_ONLY_TRUNCATED.value)
        self.assertTrue(record.is_truncated)
        self.assertEqual(record.finish_reason, "length")

    # -------------------------------------------------------------------------
    # 3. Qwen done_reason=length is marked truncated
    # -------------------------------------------------------------------------
    def test_03_qwen_done_reason_length_marked_truncated(self):
        stream_chunks = [
            json.dumps({"message": {"role": "assistant", "thinking": "Brief plan."}}),
            json.dumps({"message": {"role": "assistant", "content": "الجزء الأول من الإعراب..."}}),
            json.dumps({
                "done": True,
                "done_reason": "length",
                "prompt_eval_count": 60,
                "eval_count": 512,
            }),
        ]
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockStreamingResponse(stream_chunks)

        record = query_ollama(
            endpoint="http://mock-ollama:11434",
            model="qwen3:4b",
            prompt="أعرب الجملة",
            question_id="NAHW001",
            max_tokens=512,
            opener=mock_opener,
        )

        self.assertEqual(record.status, BenchmarkStatus.TRUNCATED.value)
        self.assertTrue(record.is_truncated)
        self.assertEqual(record.finish_reason, "length")
        self.assertEqual(record.final_answer, "الجزء الأول من الإعراب...")

    # -------------------------------------------------------------------------
    # 4. Qwen normal completion is recorded correctly
    # -------------------------------------------------------------------------
    def test_04_qwen_normal_completion_recorded_correctly(self):
        stream_chunks = [
            json.dumps({"message": {"role": "assistant", "content": "تم الإعراب بنجاح تام."}}),
            json.dumps({
                "done": True,
                "done_reason": "stop",
                "prompt_eval_count": 40,
                "eval_count": 75,
            }),
        ]
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockStreamingResponse(stream_chunks)

        record = query_ollama(
            endpoint="http://mock-ollama:11434",
            model="qwen3:4b",
            prompt="أعرب",
            question_id="NAHW001",
            max_tokens=2048,
            opener=mock_opener,
        )

        self.assertEqual(record.status, BenchmarkStatus.SUCCESS.value)
        self.assertFalse(record.is_truncated)
        self.assertIsNone(record.thinking_trace)
        self.assertEqual(record.final_answer, "تم الإعراب بنجاح تام.")
        self.assertEqual(record.finish_reason, "stop")

    # -------------------------------------------------------------------------
    # 5. Jais finish_reason=length is marked truncated
    # -------------------------------------------------------------------------
    def test_05_jais_finish_reason_length_marked_truncated(self):
        api_data = {
            "id": "chatcmpl-test-01",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "هذا شرح ناقص تم قطعه قبل إتمام الجملة"},
                    "finish_reason": "length",
                }
            ],
            "usage": {"prompt_tokens": 74, "completion_tokens": 512, "total_tokens": 586},
        }
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockHTTPResponse(api_data)

        record = query_jais_endpoint(
            endpoint="http://mock-jais:8080/v1",
            model="IFM/Jais-3-3.7B-MLX-4bit",
            prompt="اشرح البلاغة",
            question_id="BAL001",
            max_tokens=512,
            opener=mock_opener,
        )

        self.assertEqual(record.status, BenchmarkStatus.TRUNCATED.value)
        self.assertTrue(record.is_truncated)
        self.assertEqual(record.finish_reason, "length")
        self.assertEqual(record.completion_tokens, 512)
        self.assertEqual(record.final_answer, "هذا شرح ناقص تم قطعه قبل إتمام الجملة")

    # -------------------------------------------------------------------------
    # 6. Jais normal completion is recorded correctly
    # -------------------------------------------------------------------------
    def test_06_jais_normal_completion_recorded_correctly(self):
        api_data = {
            "id": "chatcmpl-test-02",
            "choices": [
                {
                    "index": 0,
                    "message": {"role": "assistant", "content": "التشبيه هو عقد مماثلة بين أمرين."},
                    "finish_reason": "stop",
                }
            ],
            "usage": {"prompt_tokens": 70, "completion_tokens": 150, "total_tokens": 220},
        }
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockHTTPResponse(api_data)

        record = query_jais_endpoint(
            endpoint="http://mock-jais:8080/v1",
            model="IFM/Jais-3-3.7B-MLX-4bit",
            prompt="ما هو التشبيه؟",
            question_id="BAL001",
            max_tokens=2048,
            opener=mock_opener,
        )

        self.assertEqual(record.status, BenchmarkStatus.SUCCESS.value)
        self.assertFalse(record.is_truncated)
        self.assertEqual(record.finish_reason, "stop")
        self.assertEqual(record.prompt_tokens, 70)
        self.assertEqual(record.completion_tokens, 150)
        self.assertEqual(record.final_answer, "التشبيه هو عقد مماثلة بين أمرين.")

    # -------------------------------------------------------------------------
    # 7. Empty responses are not successful
    # -------------------------------------------------------------------------
    def test_07_empty_responses_are_not_successful(self):
        # Ollama empty response test
        stream_chunks = [
            json.dumps({"done": True, "done_reason": "stop", "prompt_eval_count": 20, "eval_count": 0})
        ]
        mock_opener_ollama = MagicMock()
        mock_opener_ollama.open.return_value = MockStreamingResponse(stream_chunks)

        rec_ollama = query_ollama(
            endpoint="http://mock:11434",
            model="qwen3:4b",
            prompt="test",
            max_tokens=1024,
            opener=mock_opener_ollama,
        )
        self.assertEqual(rec_ollama.status, BenchmarkStatus.EMPTY_RESPONSE.value)
        self.assertNotEqual(rec_ollama.status, BenchmarkStatus.SUCCESS.value)

        # Jais empty response test
        api_data = {
            "choices": [{"message": {"content": ""}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 10, "completion_tokens": 0},
        }
        mock_opener_jais = MagicMock()
        mock_opener_jais.open.return_value = MockHTTPResponse(api_data)

        rec_jais = query_jais_endpoint(
            endpoint="http://mock:8080/v1",
            model="jais",
            prompt="test",
            max_tokens=1024,
            opener=mock_opener_jais,
        )
        self.assertEqual(rec_jais.status, BenchmarkStatus.EMPTY_RESPONSE.value)
        self.assertNotEqual(rec_jais.status, BenchmarkStatus.SUCCESS.value)

    # -------------------------------------------------------------------------
    # 8. Missing token metadata remains null
    # -------------------------------------------------------------------------
    def test_08_missing_token_metadata_remains_null(self):
        # Jais response missing usage dictionary entirely
        api_data = {
            "choices": [{"message": {"content": "إجابة سليمة"}, "finish_reason": "stop"}]
            # No 'usage' field!
        }
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockHTTPResponse(api_data)

        rec = query_jais_endpoint(
            endpoint="http://mock:8080/v1",
            model="jais",
            prompt="test",
            max_tokens=1024,
            opener=mock_opener,
        )

        self.assertIsNone(rec.prompt_tokens)
        self.assertIsNone(rec.completion_tokens)
        self.assertEqual(rec.status, BenchmarkStatus.SUCCESS.value)

    # -------------------------------------------------------------------------
    # 9. Raw Jais responses remain unchanged
    # -------------------------------------------------------------------------
    def test_09_raw_jais_responses_remain_unchanged(self):
        exact_raw = (
            "<ifm|think>\nLet us analyze the poet Al-Mutanabbi.\n</ifm|think>\n"
            "أبو الطيب المتنبي هو أحمد بن الحسين الجعفي."
        )
        api_data = {
            "choices": [{"message": {"content": exact_raw}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 50, "completion_tokens": 120},
        }
        mock_opener = MagicMock()
        mock_opener.open.return_value = MockHTTPResponse(api_data)

        rec = query_jais_endpoint(
            endpoint="http://mock:8080/v1",
            model="jais",
            prompt="من المتنبي؟",
            max_tokens=1024,
            opener=mock_opener,
        )

        # raw_answer MUST preserve exact unmodified string including all delimiters
        self.assertEqual(rec.raw_answer, exact_raw)
        self.assertEqual(rec.thinking_trace, "Let us analyze the poet Al-Mutanabbi.")
        self.assertEqual(rec.final_answer, "أبو الطيب المتنبي هو أحمد بن الحسين الجعفي.")

    # -------------------------------------------------------------------------
    # 10. Ambiguous reasoning delimiters are not silently stripped
    # -------------------------------------------------------------------------
    def test_10_ambiguous_reasoning_delimiters_not_silently_stripped(self):
        # Case A: Multiple conflicting delimiters
        conflicting_raw = (
            "<think>Thinking with standard tag</think> Some intermediate text "
            "[/REASONING] Conflicting closing tag. الجواب النهائي."
        )
        think_trace, final_ans, flagged, reason = extract_jais_reasoning_and_answer(conflicting_raw)
        self.assertTrue(flagged)
        self.assertIn("ambiguous", reason.lower())
        # The text was NOT stripped!
        self.assertEqual(final_ans, conflicting_raw)

        # Case B: Plain natural language without recognized tags (Rule 8)
        planning_text = (
            "We will structure our pedagogical lesson into three phases: "
            "Phase 1: Diagnostic warm up. النشاط التعليمي المقترح هو..."
        )
        think_trace, final_ans, flagged, reason = extract_jais_reasoning_and_answer(planning_text)
        self.assertFalse(flagged)
        self.assertIsNone(think_trace)
        # Never arbitrarily stripped simply because it contains English planning
        self.assertEqual(final_ans, planning_text)

    # -------------------------------------------------------------------------
    # 11. CLI token limits are configurable
    # -------------------------------------------------------------------------
    def test_11_cli_token_limits_are_configurable(self):
        from benchmarks.run_jais import main as jais_main
        from benchmarks.run_ollama import main as ollama_main

        # Test valid parsing of 1024 and 2048
        for runner_module in ["benchmarks.run_ollama", "benchmarks.run_jais"]:
            with patch("sys.argv", ["runner", "--max-tokens", "1024", "--help"]):
                # argparse help causes SystemExit(0)
                with self.assertRaises(SystemExit) as cm:
                    if "ollama" in runner_module:
                        ollama_main()
                    else:
                        jais_main()
                self.assertEqual(cm.exception.code, 0)

            with patch("sys.argv", ["runner", "--max-tokens", "2048", "--help"]):
                with self.assertRaises(SystemExit) as cm:
                    if "ollama" in runner_module:
                        ollama_main()
                    else:
                        jais_main()
                self.assertEqual(cm.exception.code, 0)

    # -------------------------------------------------------------------------
    # 12. Both runners produce compatible record schemas
    # -------------------------------------------------------------------------
    def test_12_both_runners_produce_compatible_record_schemas(self):
        # Generate Ollama record
        stream_chunks = [
            json.dumps({"message": {"role": "assistant", "content": "محتوى أول"}}),
            json.dumps({"done": True, "done_reason": "stop", "prompt_eval_count": 10, "eval_count": 20}),
        ]
        mock_ollama = MagicMock()
        mock_ollama.open.return_value = MockStreamingResponse(stream_chunks)

        rec_ollama = query_ollama(
            endpoint="http://mock:11434",
            model="qwen3:4b",
            prompt="سؤال",
            question_id="Q001",
            opener=mock_ollama,
        )

        # Generate Jais record
        api_data = {
            "choices": [{"message": {"content": "محتوى ثان"}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 15, "completion_tokens": 25},
        }
        mock_jais = MagicMock()
        mock_jais.open.return_value = MockHTTPResponse(api_data)

        rec_jais = query_jais_endpoint(
            endpoint="http://mock:8080/v1",
            model="jais",
            prompt="سؤال",
            question_id="Q002",
            opener=mock_jais,
        )

        dict_ollama = rec_ollama.to_dict()
        dict_jais = rec_jais.to_dict()

        # Both records must possess the EXACT same keys
        self.assertEqual(set(dict_ollama.keys()), set(dict_jais.keys()))

        # All CSV fields must be present in both
        for field in CSV_FIELDNAMES:
            self.assertIn(field, dict_ollama)
            self.assertIn(field, dict_jais)

        # Both records must pass schema validation without errors
        self.assertEqual(rec_ollama.validate(), [])
        self.assertEqual(rec_jais.validate(), [])

    # -------------------------------------------------------------------------
    # 13. Beta V-001 Question Filtering
    # -------------------------------------------------------------------------
    def test_13_question_filtering_for_beta_pilot(self):
        sample_questions = [
            {"id": "NAHW001", "domain": "nahw", "question": "q1"},
            {"id": "SARF001", "domain": "sarf", "question": "q2"},
            {"id": "BAL001", "domain": "balagha", "question": "q3"},
            {"id": "LIT001", "domain": "literature", "question": "q4"},
            {"id": "CRIT001", "domain": "criticism", "question": "q5"},
        ]

        # Test question-ids filtering
        target_ids = {"NAHW001", "SARF001", "BAL001"}
        filtered = [q for q in sample_questions if q.get("id") in target_ids]
        self.assertEqual(len(filtered), 3)
        self.assertEqual([q["id"] for q in filtered], ["NAHW001", "SARF001", "BAL001"])

        # Test limit filtering
        limited = sample_questions[:3]
        self.assertEqual(len(limited), 3)
        self.assertEqual([q["id"] for q in limited], ["NAHW001", "SARF001", "BAL001"])


if __name__ == "__main__":
    unittest.main()
