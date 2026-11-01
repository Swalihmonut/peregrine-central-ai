#!/usr/bin/env python3
"""Unified Benchmark Record Schema and Validation Engine for Arabic AI Evaluation.

Author: Benchmark Infrastructure and Evaluation Reliability Engineer
Workspace: ~/peregrine-arabic-ai-lab
Version: 2.0.0
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Union


RUNNER_VERSION = "2.0.0"


class BenchmarkStatus(str, Enum):
    """Normalized evaluation status codes.

    Distinguishes natural completions from truncated responses, empty outputs,
    and runtime errors. A response is NEVER marked successful merely because
    the API returned HTTP 200 without raising an exception.
    """

    SUCCESS = "success"
    TRUNCATED = "truncated"
    REASONING_ONLY_TRUNCATED = "reasoning_only_truncated"
    EMPTY_RESPONSE = "empty_response"
    REQUEST_ERROR = "request_error"
    PARSE_ERROR = "parse_error"


@dataclass
class BenchmarkRecord:
    """Normalized, auditable record emitted by all Peregrine benchmark runners.

    Required Fields:
        question_id: Benchmark question identifier (e.g., 'NAHW001').
        model: Logical model name/tag passed to the runner (e.g., 'qwen3:4b').
        model_digest_or_identifier: Specific checkpoint SHA256 or HF repo ID (or None if unavailable).
        raw_answer: Exact, unmodified string returned by the provider prior to any extraction.
        final_answer: Extracted substantive Arabic answer presented for scholarly grading.
        thinking_trace: Extracted internal chain-of-thought tokens/scratchpad (or None).
        status: BenchmarkStatus enum string value.
        error_message: String describing error if status is an error, otherwise None.
        finish_reason: Direct engine termination flag ('stop', 'length', etc.) or None if missing.
        is_truncated: Boolean flag indicating if token limit halted generation.
        prompt_tokens: Integer prompt token count reported by provider (or None).
        completion_tokens: Integer completion token count reported by provider (or None).
        max_output_tokens: Configured token generation budget (e.g., 1024, 2048).
        elapsed_seconds: Round-trip wall-clock latency in seconds.
        timestamp: ISO 8601 UTC timestamp of execution start.
        runner_version: Software version of the benchmark runner infrastructure.

    Extensible Metadata Fields:
        domain: Field of Arabic scholarship (nahw, sarf, balagha, etc.).
        prompt: User question prompt text.
        flagged_for_review: Boolean indicating ambiguity in thinking/answer extraction.
        review_reason: Explanation if flagged for review, otherwise None.
        raw_metadata: Raw provider metadata dict (e.g. durations, fingerprint, usage).
    """

    question_id: str
    model: str
    model_digest_or_identifier: Optional[str]
    raw_answer: str
    final_answer: str
    thinking_trace: Optional[str]
    status: str
    error_message: Optional[str]
    finish_reason: Optional[str]
    is_truncated: bool
    prompt_tokens: Optional[int]
    completion_tokens: Optional[int]
    max_output_tokens: int
    elapsed_seconds: float
    timestamp: str
    runner_version: str = RUNNER_VERSION

    # Extensible fields
    domain: Optional[str] = None
    prompt: Optional[str] = None
    flagged_for_review: bool = False
    review_reason: Optional[str] = None
    raw_metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert record to a JSON-serializable dictionary preserving null values."""
        res = asdict(self)
        # Ensure status is string
        if isinstance(res["status"], Enum):
            res["status"] = res["status"].value
        return res

    def validate(self) -> List[str]:
        """Verify strict schema compliance. Returns a list of validation errors."""
        errors = []
        # Required non-null string fields
        for f in ["question_id", "model", "status", "timestamp", "runner_version"]:
            val = getattr(self, f, None)
            if val is None or not isinstance(val, str) or not val.strip():
                errors.append(f"Field '{f}' must be a non-empty string, got {val!r}")

        # Raw answer and final answer must be strings (can be empty string, but not None)
        if not isinstance(self.raw_answer, str):
            errors.append(f"Field 'raw_answer' must be a string, got {type(self.raw_answer)}")
        if not isinstance(self.final_answer, str):
            errors.append(f"Field 'final_answer' must be a string, got {type(self.final_answer)}")

        # Thinking trace must be str or None
        if self.thinking_trace is not None and not isinstance(self.thinking_trace, str):
            errors.append(f"Field 'thinking_trace' must be str or None, got {type(self.thinking_trace)}")

        # Status validation
        valid_statuses = {s.value for s in BenchmarkStatus}
        if self.status not in valid_statuses:
            errors.append(f"Invalid status '{self.status}'. Must be one of {valid_statuses}")

        # is_truncated must be boolean
        if not isinstance(self.is_truncated, bool):
            errors.append(f"Field 'is_truncated' must be bool, got {type(self.is_truncated)}")

        # max_output_tokens must be positive int
        if not isinstance(self.max_output_tokens, int) or self.max_output_tokens <= 0:
            errors.append(f"Field 'max_output_tokens' must be a positive int, got {self.max_output_tokens}")

        # elapsed_seconds must be non-negative float/int
        if not isinstance(self.elapsed_seconds, (float, int)) or self.elapsed_seconds < 0:
            errors.append(f"Field 'elapsed_seconds' must be >= 0, got {self.elapsed_seconds}")

        # Semantic status invariants
        if self.status == BenchmarkStatus.SUCCESS.value:
            if self.is_truncated:
                errors.append("Invariant violated: status 'success' cannot have is_truncated=True")
            if not self.final_answer.strip():
                errors.append("Invariant violated: status 'success' cannot have empty final_answer")

        if self.status == BenchmarkStatus.REASONING_ONLY_TRUNCATED.value:
            if not self.thinking_trace or not self.thinking_trace.strip():
                errors.append("Invariant violated: status 'reasoning_only_truncated' requires non-empty thinking_trace")
            if self.final_answer.strip():
                errors.append("Invariant violated: status 'reasoning_only_truncated' cannot have non-empty final_answer")
            if not self.is_truncated:
                errors.append("Invariant violated: status 'reasoning_only_truncated' must have is_truncated=True")

        return errors


def create_record(
    question_id: str,
    model: str,
    raw_answer: str,
    final_answer: str,
    max_output_tokens: int,
    elapsed_seconds: float,
    thinking_trace: Optional[str] = None,
    finish_reason: Optional[str] = None,
    prompt_tokens: Optional[int] = None,
    completion_tokens: Optional[int] = None,
    model_digest_or_identifier: Optional[str] = None,
    status_override: Optional[Union[BenchmarkStatus, str]] = None,
    error_message: Optional[str] = None,
    domain: Optional[str] = None,
    prompt: Optional[str] = None,
    flagged_for_review: bool = False,
    review_reason: Optional[str] = None,
    raw_metadata: Optional[Dict[str, Any]] = None,
    timestamp: Optional[str] = None,
) -> BenchmarkRecord:
    """Factory function that constructs, evaluates status, and validates a BenchmarkRecord."""
    ts = timestamp or datetime.now(timezone.utc).isoformat()
    clean_final = final_answer.strip()
    clean_thinking = thinking_trace.strip() if thinking_trace else ""
    metadata = raw_metadata or {}

    # Determine is_truncated
    norm_finish = str(finish_reason).lower() if finish_reason else None
    is_truncated = False
    if norm_finish in ("length", "max_tokens"):
        is_truncated = True
    elif completion_tokens is not None and completion_tokens >= max_output_tokens:
        is_truncated = True

    # Determine status
    if status_override:
        status_val = status_override.value if isinstance(status_override, BenchmarkStatus) else str(status_override)
    elif error_message:
        status_val = BenchmarkStatus.REQUEST_ERROR.value
    elif not clean_final and not clean_thinking and not raw_answer.strip():
        status_val = BenchmarkStatus.EMPTY_RESPONSE.value
    elif is_truncated:
        if not clean_final and clean_thinking:
            status_val = BenchmarkStatus.REASONING_ONLY_TRUNCATED.value
        elif clean_final:
            status_val = BenchmarkStatus.TRUNCATED.value
        else:
            status_val = BenchmarkStatus.EMPTY_RESPONSE.value
    else:
        # Not truncated
        if clean_final:
            status_val = BenchmarkStatus.SUCCESS.value
        elif clean_thinking and not clean_final:
            status_val = BenchmarkStatus.REASONING_ONLY_TRUNCATED.value
        else:
            status_val = BenchmarkStatus.EMPTY_RESPONSE.value

    rec = BenchmarkRecord(
        question_id=question_id,
        model=model,
        model_digest_or_identifier=model_digest_or_identifier,
        raw_answer=raw_answer,
        final_answer=clean_final,
        thinking_trace=clean_thinking if clean_thinking else None,
        status=status_val,
        error_message=error_message,
        finish_reason=finish_reason,
        is_truncated=is_truncated,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        max_output_tokens=max_output_tokens,
        elapsed_seconds=round(elapsed_seconds, 4),
        timestamp=ts,
        runner_version=RUNNER_VERSION,
        domain=domain,
        prompt=prompt,
        flagged_for_review=flagged_for_review,
        review_reason=review_reason,
        raw_metadata=metadata,
    )

    val_errors = rec.validate()
    if val_errors:
        raise ValueError(f"BenchmarkRecord validation failed: {'; '.join(val_errors)}")
    return rec


# CSV Fieldnames specification
CSV_FIELDNAMES = [
    "question_id",
    "domain",
    "model",
    "model_digest_or_identifier",
    "status",
    "is_truncated",
    "finish_reason",
    "prompt_tokens",
    "completion_tokens",
    "max_output_tokens",
    "elapsed_seconds",
    "timestamp",
    "runner_version",
    "flagged_for_review",
    "review_reason",
    "error_message",
    "prompt",
    "final_answer",
    "thinking_trace",
    "raw_answer",
]
