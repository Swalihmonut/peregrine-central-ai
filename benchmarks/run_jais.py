#!/usr/bin/env python3
"""Runner for benchmarking Jais 3 models via OpenAI-compatible local API server (port 8080).

Author: Benchmark Infrastructure and Evaluation Reliability Engineer
Workspace: ~/peregrine-arabic-ai-lab
Version: 2.0.0
"""

from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
import sys
import time
from typing import Any, Dict, List, Optional, Tuple
import urllib.error
import urllib.request

# Support running directly as script or as imported module
sys.path.insert(0, str(Path(__file__).parent.parent))

from benchmarks.benchmark_schema import (
    BenchmarkRecord,
    BenchmarkStatus,
    CSV_FIELDNAMES,
    RUNNER_VERSION,
    create_record,
)
from benchmarks.shared_prompts import (
    CANONICAL_BENCHMARK_SYSTEM_PROMPT,
    build_chat_messages,
)


def load_benchmark(benchmark_path: Path) -> List[Dict[str, Any]]:
    """Load benchmark questions from JSON file."""
    if not benchmark_path.exists():
        raise FileNotFoundError(f"Benchmark file not found: {benchmark_path}")
    with open(benchmark_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    if isinstance(data, list):
        return data
    return data.get("questions", [])


def extract_jais_reasoning_and_answer(
    raw_text: str,
) -> Tuple[Optional[str], str, bool, Optional[str]]:
    """Extract internal reasoning trace and final answer from raw Jais response text.

    Strict Architectural Guarantees:
    1. Do not assume a single thinking delimiter.
    2. Do not remove arbitrary text simply because it resembles internal reasoning.
    3. If the response contains a recognizable reasoning/final-answer structure,
       preserve both the raw response and the extracted final answer.
    4. If the structure is ambiguous, flag it for review rather than silently rewriting it.

    Returns:
        (thinking_trace, final_answer, flagged_for_review, review_reason)
    """
    if not raw_text or not raw_text.strip():
        return None, "", False, None

    # Supported closing delimiters across known model templates
    known_closing_delimiters = [
        ("</ifm|think>", "<ifm|think>"),
        ("</think>", "<think>"),
        ("</thought>", "<thought>"),
        ("[/THINKING]", "[THINKING]"),
        ("[/REASONING]", "[REASONING]"),
    ]

    detected_closers = [c for c, _ in known_closing_delimiters if c in raw_text]

    # Check for ambiguous competing delimiters
    if len(detected_closers) > 1:
        # Ambiguous structure: multiple different delimiter standards present
        return (
            None,
            raw_text,
            True,
            f"ambiguous_multiple_closing_delimiters: {detected_closers}",
        )

    if len(detected_closers) == 1:
        closer, opener = next(item for item in known_closing_delimiters if item[0] == detected_closers[0])
        parts = raw_text.split(closer, 1)
        raw_thinking = parts[0]
        final_answer = parts[1].strip()

        # Clean matching opener if present
        if opener in raw_thinking:
            raw_thinking = raw_thinking.split(opener, 1)[1]

        thinking_trace = raw_thinking.strip() if raw_thinking.strip() else None
        return thinking_trace, final_answer, False, None

    # Check for an unclosed opening delimiter (model hit token limit during thinking)
    known_openers = ["<ifm|think>", "<think>", "<thought>", "[THINKING]", "[REASONING]"]
    detected_openers = [o for o in known_openers if o in raw_text]

    if len(detected_openers) == 1:
        opener = detected_openers[0]
        # Text begins thinking but never closed
        thinking_part = raw_text.split(opener, 1)[1].strip()
        return thinking_part, "", False, "unclosed_thinking_tag"

    if len(detected_openers) > 1:
        return None, raw_text, True, f"ambiguous_multiple_opening_delimiters: {detected_openers}"

    # RULE 8: Do not remove arbitrary text simply because it resembles internal reasoning.
    # If no structural tag exists, raw text is preserved 100% as final answer without stripping.
    return None, raw_text.strip(), False, None


def query_jais_endpoint(
    endpoint: str,
    model: str,
    prompt: str,
    question_id: str = "unknown",
    domain: Optional[str] = None,
    api_key: str = "EMPTY",
    system_prompt: Optional[str] = None,
    timeout: float = 180.0,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model_digest_or_identifier: Optional[str] = None,
    opener: Optional[Any] = None,
) -> BenchmarkRecord:
    """Execute a single query against an OpenAI-compatible endpoint serving Jais on port 8080.

    Strict Architectural Guarantees:
    1. Preserve the original unmodified response in `raw_answer`.
    2. Capture OpenAI-compatible `finish_reason`.
    3. Record prompt and completion token counts when returned by the endpoint (null if absent).
    4. Make `max_tokens` configurable through CLI.
    5. Record elapsed time and configured token limit (`max_output_tokens`).
    6. Mark `finish_reason == 'length'` as truncated.
    7. Robust reasoning extraction without arbitrary stripping.
    8. Ambiguous structures flagged for review.
    """
    url = f"{endpoint.rstrip('/')}/chat/completions"
    messages = build_chat_messages(prompt=prompt, system_prompt=system_prompt)

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": False,
    }

    start_time = time.perf_counter()
    timestamp_utc = datetime.now(timezone.utc).isoformat()

    req_data = json.dumps(payload).encode("utf-8")
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}",
    }

    req = urllib.request.Request(
        url,
        data=req_data,
        headers=headers,
        method="POST",
    )

    open_fn = opener.open if opener else urllib.request.urlopen

    try:
        with open_fn(req, timeout=timeout) as response:
            latency = time.perf_counter() - start_time
            body_bytes = response.read()
            res_body = json.loads(body_bytes.decode("utf-8"))

            choices = res_body.get("choices", [])
            raw_answer = ""
            finish_reason: Optional[str] = None

            if choices and isinstance(choices, list):
                first_choice = choices[0]
                msg = first_choice.get("message", {})
                raw_answer = msg.get("content", "") or ""
                finish_reason = first_choice.get("finish_reason")

            usage = res_body.get("usage", {})
            prompt_tokens = usage.get("prompt_tokens")
            completion_tokens = usage.get("completion_tokens")

            # Extract reasoning trace and final answer cleanly
            thinking_trace, final_answer, flagged, review_reason = extract_jais_reasoning_and_answer(raw_answer)

            raw_metadata = {
                "id": res_body.get("id"),
                "system_fingerprint": res_body.get("system_fingerprint"),
                "finish_reason": finish_reason,
            }

            return create_record(
                question_id=question_id,
                domain=domain,
                prompt=prompt,
                model=model,
                model_digest_or_identifier=model_digest_or_identifier,
                raw_answer=raw_answer,
                final_answer=final_answer,
                thinking_trace=thinking_trace,
                finish_reason=finish_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                max_output_tokens=max_tokens,
                elapsed_seconds=latency,
                flagged_for_review=flagged,
                review_reason=review_reason,
                raw_metadata=raw_metadata,
                timestamp=timestamp_utc,
            )

    except urllib.error.HTTPError as he:
        latency = time.perf_counter() - start_time
        err_body = ""
        try:
            err_body = he.read().decode("utf-8", errors="replace")[:200]
        except Exception:
            pass
        return create_record(
            question_id=question_id,
            domain=domain,
            prompt=prompt,
            model=model,
            model_digest_or_identifier=model_digest_or_identifier,
            raw_answer=err_body,
            final_answer="",
            thinking_trace=None,
            status_override=BenchmarkStatus.REQUEST_ERROR,
            error_message=f"HTTPError {he.code}: {he.reason} | {err_body}",
            finish_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            max_output_tokens=max_tokens,
            elapsed_seconds=latency,
            timestamp=timestamp_utc,
        )
    except json.JSONDecodeError as jde:
        latency = time.perf_counter() - start_time
        return create_record(
            question_id=question_id,
            domain=domain,
            prompt=prompt,
            model=model,
            model_digest_or_identifier=model_digest_or_identifier,
            raw_answer="",
            final_answer="",
            thinking_trace=None,
            status_override=BenchmarkStatus.PARSE_ERROR,
            error_message=f"JSONDecodeError: {str(jde)}",
            finish_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            max_output_tokens=max_tokens,
            elapsed_seconds=latency,
            timestamp=timestamp_utc,
        )
    except Exception as e:
        latency = time.perf_counter() - start_time
        return create_record(
            question_id=question_id,
            domain=domain,
            prompt=prompt,
            model=model,
            model_digest_or_identifier=model_digest_or_identifier,
            raw_answer="",
            final_answer="",
            thinking_trace=None,
            status_override=BenchmarkStatus.REQUEST_ERROR,
            error_message=f"{type(e).__name__}: {str(e)}",
            finish_reason=None,
            prompt_tokens=None,
            completion_tokens=None,
            max_output_tokens=max_tokens,
            elapsed_seconds=latency,
            timestamp=timestamp_utc,
        )


def save_results(
    records: List[BenchmarkRecord],
    output_dir: Path,
    output_prefix: str = "pilot_jais",
    allow_overwrite: bool = False,
) -> tuple[Path, Path]:
    """Save normalized benchmark records to JSONL and CSV with strict overwrite guards."""
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    csv_path = output_dir / f"{output_prefix}.csv"

    # DATA PROTECTION SAFETY GUARD:
    # Protect baseline original files from being overwritten
    protected_baselines = {"day1_ollama.jsonl", "day1_ollama.csv", "day1_jais.jsonl", "day1_jais.csv"}
    if jsonl_path.name in protected_baselines or csv_path.name in protected_baselines:
        if not allow_overwrite:
            raise FileExistsError(
                f"SAFETY GUARD: Refusing to overwrite protected baseline benchmark output "
                f"'{jsonl_path.name}'. Specify a different --output-prefix (e.g. 'pilot_jais') "
                f"or pass --allow-overwrite explicitly if intended."
            )

    # Write JSONL
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec.to_dict(), ensure_ascii=False) + "\n")

    # Write CSV
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES, extrasaction="ignore")
        writer.writeheader()
        for rec in records:
            writer.writerow(rec.to_dict())

    return jsonl_path, csv_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Arabic Day 1 benchmark with Jais 3 on port 8080 [v2.0.0 Auditable Runner]"
    )
    parser.add_argument(
        "--benchmark",
        type=Path,
        default=Path(__file__).parent / "arabic_day1.json",
        help="Path to benchmark JSON file (default: benchmarks/arabic_day1.json)",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get("JAIS_MODEL", "IFM/Jais-3-3.7B-MLX-4bit"),
        help="Model identifier on server (default: IFM/Jais-3-3.7B-MLX-4bit)",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.environ.get("JAIS_ENDPOINT", "http://localhost:8080/v1"),
        help="OpenAI-compatible server endpoint (default: http://localhost:8080/v1)",
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=os.environ.get("OPENAI_API_KEY", "EMPTY"),
        help="API Key for endpoint (default: EMPTY)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "results",
        help="Directory to save benchmark results (default: results/)",
    )
    parser.add_argument(
        "--output-prefix",
        type=str,
        default="pilot_jais",
        help="Filename prefix for results (default: pilot_jais, saving pilot_jais.jsonl/csv)",
    )
    parser.add_argument(
        "--allow-overwrite",
        action="store_true",
        help="Explicitly permit overwriting existing output files if they exist",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Request timeout in seconds (default: 180.0)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Sampling temperature (default: 0.2)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=2048,
        choices=[512, 1024, 2048, 4096],
        help="Configurable output token limit (max_tokens: 1024 or 2048 recommended; default: 2048)",
    )
    parser.add_argument(
        "--question-ids",
        type=str,
        default=None,
        help="Comma-separated question IDs to execute (e.g. 'NAHW001,SARF001,BAL001')",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit execution to the first N questions",
    )
    parser.add_argument(
        "--system-prompt",
        type=str,
        default=None,
        help="Optional custom system prompt (defaults to canonical shared benchmark prompt)",
    )

    args = parser.parse_args()

    print("============================================================")
    print(f"Arabic Benchmark Runner - Jais Suite [v{RUNNER_VERSION}]")
    print(f"Model: {args.model}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Max Output Tokens (max_tokens): {args.max_tokens}")
    print(f"Output Prefix: {args.output_prefix}")
    print("============================================================")

    try:
        questions = load_benchmark(args.benchmark)
        if args.question_ids:
            target_ids = {qid.strip() for qid in args.question_ids.split(",") if qid.strip()}
            questions = [q for q in questions if q.get("id") in target_ids]
        if args.limit is not None and args.limit > 0:
            questions = questions[:args.limit]
    except Exception as e:
        print(f"[CRITICAL] Failed to load benchmark: {e}", file=sys.stderr)
        return 1

    records: List[BenchmarkRecord] = []

    for i, q in enumerate(questions, start=1):
        q_id = q.get("id", f"q{i}")
        domain = q.get("domain", "unknown")
        prompt = q.get("question") or q.get("prompt", "")

        print(f"\n[{i}/{len(questions)}] Processing: {q_id} ({domain})...")
        record = query_jais_endpoint(
            endpoint=args.endpoint,
            model=args.model,
            prompt=prompt,
            question_id=q_id,
            domain=domain,
            api_key=args.api_key,
            system_prompt=args.system_prompt,
            timeout=args.timeout,
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
        records.append(record)

        if record.status == BenchmarkStatus.SUCCESS.value:
            print(f"  ✓ Success | Latency: {record.elapsed_seconds}s | Tokens: {record.completion_tokens}")
            ans_preview = (record.final_answer[:80] + "...") if len(record.final_answer) > 80 else record.final_answer
            print(f"    Preview: {ans_preview}")
        elif record.status == BenchmarkStatus.TRUNCATED.value:
            print(f"  ⚠ Truncated (length limit) | Latency: {record.elapsed_seconds}s | Tokens: {record.completion_tokens}")
            ans_preview = (record.final_answer[:80] + "...") if len(record.final_answer) > 80 else record.final_answer
            print(f"    Preview: {ans_preview}")
        elif record.status == BenchmarkStatus.REASONING_ONLY_TRUNCATED.value:
            print(f"  ⚠ Reasoning-Only Truncated | Latency: {record.elapsed_seconds}s | Tokens: {record.completion_tokens}")
        else:
            print(f"  ✗ {record.status} | Latency: {record.elapsed_seconds}s | Reason: {record.error_message}")

        if record.flagged_for_review:
            print(f"    [FLAGGED FOR REVIEW]: {record.review_reason}")

    if records:
        jsonl_path, csv_path = save_results(
            records=records,
            output_dir=args.output_dir,
            output_prefix=args.output_prefix,
            allow_overwrite=args.allow_overwrite,
        )
        print("\n============================================================")
        print("Benchmark run completed. Results saved to:")
        print(f"  JSONL: {jsonl_path}")
        print(f"  CSV:   {csv_path}")
        print("============================================================")

    all_success = all(r.status == BenchmarkStatus.SUCCESS.value for r in records)
    return 0 if all_success else 2


if __name__ == "__main__":
    sys.exit(main())
