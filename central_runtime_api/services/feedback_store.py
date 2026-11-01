"""Feedback storage and continuous learning queue manager."""

from __future__ import annotations

import json
from pathlib import Path
import threading
from typing import Any, Dict, List, Optional
import uuid

from central_runtime_api.middleware.privacy import anonymize_user_id, sanitize_pii
from central_runtime_api.schemas import (
    CandidateDatasetRecord,
    FeedbackSubmissionRequest,
    FeedbackSubmissionResponse,
    ReviewStatus,
)


class FeedbackStore:
    """Manages feedback persistence, consent enforcement, and candidate dataset queuing."""

    def __init__(self, data_dir: Path):
        self.data_dir = Path(data_dir)
        self.feedback_dir = self.data_dir / "feedback"
        self.candidates_dir = self.data_dir / "candidates"
        try:
            self.feedback_dir.mkdir(parents=True, exist_ok=True)
            self.candidates_dir.mkdir(parents=True, exist_ok=True)
        except Exception:
            pass

        self._lock = threading.Lock()
        self.operational_log = self.feedback_dir / "operational_feedback.jsonl"
        self.learning_queue = self.feedback_dir / "learning_queue.jsonl"

    def record_feedback(self, req: FeedbackSubmissionRequest) -> FeedbackSubmissionResponse:
        """Record customer feedback, enforcing strict consent filtering."""
        with self._lock:
            # 1. Anonymize user ID
            hashed_user = anonymize_user_id(req.user_id_hash) if req.user_id_hash else "anon_user"

            # 2. Sanitize comments and user correction for PII
            clean_comments, _ = sanitize_pii(req.comments or "")
            clean_correction, _ = sanitize_pii(req.user_correction or "")

            record = req.model_dump()
            record["user_id_hash"] = hashed_user
            record["comments"] = clean_comments
            record["user_correction"] = clean_correction

            # 3. Always write to operational log for QA tracking
            with open(self.operational_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

            # 4. Consent Gate: Only write to learning queue if explicit consent is True
            eligible = bool(req.consent_for_training and (req.user_correction or req.rating <= 2))
            if req.consent_for_training:
                with open(self.learning_queue, "a", encoding="utf-8") as f:
                    f.write(json.dumps(record, ensure_ascii=False) + "\n")

            msg = (
                "Feedback recorded for quality monitoring and learning queue."
                if req.consent_for_training
                else "Feedback recorded for operational monitoring only (Consent not granted for model training)."
            )

            return FeedbackSubmissionResponse(
                feedback_id=req.feedback_id,
                status="received",
                consent_recorded=req.consent_for_training,
                eligible_for_learning_pipeline=eligible,
                message=msg,
            )

    def generate_candidate_dataset(
        self,
        target_version: str = "v0.1.0-candidates",
    ) -> tuple[int, Path]:
        """Batch process learning queue into candidate dataset records (for philologist review)."""
        with self._lock:
            candidates_file = self.candidates_dir / f"{target_version}.jsonl"
            processed_count = 0

            if not self.learning_queue.exists():
                return 0, candidates_file

            candidates: List[Dict[str, Any]] = []
            with open(self.learning_queue, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    fb = json.loads(line)
                    if not fb.get("consent_for_training"):
                        continue

                    candidate = CandidateDatasetRecord(
                        candidate_id=f"cand-{uuid.uuid4().hex[:12]}",
                        feedback_id=fb.get("feedback_id", "unknown"),
                        request_id=fb.get("request_id", "unknown"),
                        domain=fb.get("category", "other"),
                        input_prompt_sanitized=fb.get("metadata", {}).get("prompt", "Prompt withheld or omitted"),
                        original_model_output_sanitized=fb.get("metadata", {}).get("original_output", ""),
                        curated_ground_truth=fb.get("user_correction") or "",
                        review_status=ReviewStatus.PENDING_REVIEW,
                        dataset_version_target=target_version,
                    )
                    candidates.append(candidate.model_dump())
                    processed_count += 1

            with open(candidates_file, "a", encoding="utf-8") as f:
                for c in candidates:
                    f.write(json.dumps(c, ensure_ascii=False) + "\n")

            return processed_count, candidates_file

    def withdraw_consent(self, raw_user_id: str) -> Dict[str, Any]:
        """Withdraw consent for a user: purge all their records from the learning queue."""
        hashed_user = anonymize_user_id(raw_user_id) if raw_user_id else "anon_user"
        purged_count = 0

        with self._lock:
            # 1. Record withdrawal event in operational log for legal audit trail
            withdrawal_event = {
                "event": "consent_withdrawal",
                "user_id_hash": hashed_user,
                "timestamp": str(uuid.uuid4()),
                "status": "revoked",
            }
            with open(self.operational_log, "a", encoding="utf-8") as f:
                f.write(json.dumps(withdrawal_event, ensure_ascii=False) + "\n")

            # 2. Filter learning queue
            if self.learning_queue.exists():
                retained_lines: List[str] = []
                with open(self.learning_queue, "r", encoding="utf-8") as f:
                    for line in f:
                        line_str = line.strip()
                        if not line_str:
                            continue
                        try:
                            record = json.loads(line_str)
                            if record.get("user_id_hash") == hashed_user:
                                purged_count += 1
                                continue
                            retained_lines.append(line_str)
                        except Exception:
                            retained_lines.append(line_str)

                with open(self.learning_queue, "w", encoding="utf-8") as f:
                    for r_line in retained_lines:
                        f.write(r_line + "\n")

        return {
            "status": "consent_revoked",
            "user_id_hash": hashed_user,
            "purged_records_count": purged_count,
            "message": f"Successfully revoked consent. Purged {purged_count} records from active learning queue.",
        }

    def get_queue_metrics(self) -> Dict[str, Any]:
        """Return operational telemetry on feedback queue depth and storage."""
        with self._lock:
            op_count = 0
            if self.operational_log.exists():
                with open(self.operational_log, "r", encoding="utf-8") as f:
                    op_count = sum(1 for line in f if line.strip())

            learn_count = 0
            if self.learning_queue.exists():
                with open(self.learning_queue, "r", encoding="utf-8") as f:
                    learn_count = sum(1 for line in f if line.strip())

            candidate_files = list(self.candidates_dir.glob("*.jsonl"))

            return {
                "operational_feedback_count": op_count,
                "learning_queue_depth": learn_count,
                "candidate_datasets_count": len(candidate_files),
                "storage_path": str(self.data_dir),
            }

