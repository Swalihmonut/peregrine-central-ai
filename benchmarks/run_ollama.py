#!/usr/bin/env python3
"""Runner for benchmarking Ollama models against the Arabic Day 1 benchmark suite.

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
import sys
import time
from typing import Any, Dict, List, Optional
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


def query_ollama(
    endpoint: str,
    model: str,
    prompt: str,
    question_id: str = "unknown",
    domain: Optional[str] = None,
    system_prompt: Optional[str] = None,
    timeout: float = 180.0,
    temperature: float = 0.2,
    max_tokens: int = 2048,
    model_digest_or_identifier: Optional[str] = None,
    opener: Optional[Any] = None,
) -> BenchmarkRecord:
    """Execute a single query against Ollama's HTTP API using streaming.

    Strict Architectural Guarantees:
    1. Separate streaming `message.thinking` from `message.content`.
    2. Never substitute thinking content into final_answer when final content is empty.
    3. If thinking exists but final content is empty, mark status: 'reasoning_only_truncated'.
    4. Capture Ollama `done_reason`, `prompt_eval_count`, and `eval_count`.
    5. Record elapsed time and configured output-token limit (`max_output_tokens`).
    6. Record whether the response ended normally or hit token limit (`is_truncated`).
    7. Preserve raw response chunks and engine metadata for forensic inspection.
    """
    url = f"{endpoint.rstrip('/')}/api/chat"
    messages = build_chat_messages(prompt=prompt, system_prompt=system_prompt)

    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_predict": max_tokens,
        },
    }

    start_time = time.perf_counter()
    timestamp_utc = datetime.now(timezone.utc).isoformat()
    req_data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=req_data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    open_fn = opener.open if opener else urllib.request.urlopen

    content_chunks: List[str] = []
    thinking_chunks: List[str] = []
    raw_lines: List[str] = []
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    done_reason: Optional[str] = None
    raw_metadata: Dict[str, Any] = {}
    is_parse_error = False
    parse_error_msg = None

    try:
        with open_fn(req, timeout=timeout) as response:
            for raw_line in response:
                if isinstance(raw_line, bytes):
                    line_str = raw_line.decode("utf-8", errors="replace").strip()
                else:
                    line_str = str(raw_line).strip()

                if not line_str:
                    continue
                raw_lines.append(line_str)

                try:
                    chunk = json.loads(line_str)
                except json.JSONDecodeError as jde:
                    is_parse_error = True
                    parse_error_msg = f"JSONDecodeError: {jde} on chunk: {line_str[:120]}"
                    continue

                msg = chunk.get("message", {})
                if msg.get("content"):
                    content_chunks.append(msg["content"])
                if msg.get("thinking"):
                    thinking_chunks.append(msg["thinking"])

                if chunk.get("done"):
                    done_reason = chunk.get("done_reason")
                    prompt_tokens = chunk.get("prompt_eval_count")
                    completion_tokens = chunk.get("eval_count")
                    # Preserve all performance timing telemetry from done chunk
                    for k in [
                        "total_duration",
                        "load_duration",
                        "prompt_eval_duration",
                        "eval_duration",
                        "done_reason",
                    ]:
                        if k in chunk:
                            raw_metadata[k] = chunk[k]

        latency = time.perf_counter() - start_time

        if is_parse_error and not content_chunks and not thinking_chunks:
            return create_record(
                question_id=question_id,
                domain=domain,
                prompt=prompt,
                model=model,
                model_digest_or_identifier=model_digest_or_identifier,
                raw_answer="\n".join(raw_lines),
                final_answer="",
                thinking_trace=None,
                status_override=BenchmarkStatus.PARSE_ERROR,
                error_message=parse_error_msg or "Failed to parse streaming JSON",
                finish_reason=done_reason,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                max_output_tokens=max_tokens,
                elapsed_seconds=latency,
                raw_metadata=raw_metadata,
                timestamp=timestamp_utc,
            )

        full_content = "".join(content_chunks).strip()
        full_thinking = "".join(thinking_chunks).strip()
        raw_full = "".join(raw_lines)

        # STRICT PROHIBITION: Never substitute thinking content into final_answer
        return create_record(
            question_id=question_id,
            domain=domain,
            prompt=prompt,
            model=model,
            model_digest_or_identifier=model_digest_or_identifier,
            raw_answer=raw_full,
            final_answer=full_content,
            thinking_trace=full_thinking if full_thinking else None,
            finish_reason=done_reason,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            max_output_tokens=max_tokens,
            elapsed_seconds=latency,
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
    output_prefix: str = "pilot_ollama",
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
                f"'{jsonl_path.name}'. Specify a different --output-prefix (e.g. 'pilot_ollama') "
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
        description="Run Arabic Day 1 benchmark with Ollama (qwen3:4b) [v2.0.0 Auditable Runner]"
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
        default=os.environ.get("OLLAMA_MODEL", "qwen3:4b"),
        help="Ollama model tag to evaluate (default: qwen3:4b)",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434"),
        help="Ollama server endpoint (default: http://127.0.0.1:11434)",
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
        default="pilot_ollama",
        help="Filename prefix for results (default: pilot_ollama, saving pilot_ollama.jsonl/csv)",
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
        help="Configurable output token limit (num_predict: 1024 or 2048 recommended; default: 2048)",
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
    print(f"Arabic Benchmark Runner - Ollama Suite [v{RUNNER_VERSION}]")
    print(f"Model: {args.model}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Benchmark: {args.benchmark}")
    print(f"Max Output Tokens (num_predict): {args.max_tokens}")
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
        record = query_ollama(
            endpoint=args.endpoint,
            model=args.model,
            prompt=prompt,
            question_id=q_id,
            domain=domain,
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
        elif record.status == BenchmarkStatus.REASONING_ONLY_TRUNCATED.value:
            print(f"  ⚠ Reasoning-Only Truncated | Latency: {record.elapsed_seconds}s | Tokens: {record.completion_tokens}")
            think_preview = (record.thinking_trace[:80] + "...") if record.thinking_trace else ""
            print(f"    Thinking Trace: {think_preview}")
        elif record.status == BenchmarkStatus.TRUNCATED.value:
            print(f"  ⚠ Content Truncated | Latency: {record.elapsed_seconds}s | Tokens: {record.completion_tokens}")
            ans_preview = (record.final_answer[:80] + "...") if len(record.final_answer) > 80 else record.final_answer
            print(f"    Preview: {ans_preview}")
        else:
            print(f"  ✗ {record.status} | Latency: {record.elapsed_seconds}s | Reason: {record.error_message}")

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
