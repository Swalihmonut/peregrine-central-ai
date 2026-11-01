"""Data schemas for Central AI Runtime & API."""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
import uuid

from pydantic import BaseModel, Field


class MessageRole(str, Enum):
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


class ChatMessage(BaseModel):
    role: MessageRole
    content: str


class GenerationParameters(BaseModel):
    temperature: float = Field(0.2, ge=0.0, le=2.0)
    max_tokens: int = Field(1024, ge=1, le=8192)
    top_p: float = Field(0.95, ge=0.0, le=1.0)
    seed: Optional[int] = Field(42)


# ==========================================
# Application Request Schemas
# ==========================================

class ChatRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"req-{uuid.uuid4().hex[:12]}")
    messages: List[ChatMessage]
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)
    model: Optional[str] = None


class TutorExplainRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"tutor-{uuid.uuid4().hex[:12]}")
    query: str = Field(..., description="Arabic grammar or linguistic query to explain")
    level: str = Field("intermediate", description="beginner, intermediate, advanced")
    topic: str = Field("nahw", description="nahw, sarf, balagha, general")
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)


class SpeakingRespondRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"speak-{uuid.uuid4().hex[:12]}")
    user_utterance: str = Field(..., description="The user's spoken or typed statement")
    scenario: str = Field("daily_conversation", description="daily_conversation, travel, academic, market")
    dialect: str = Field("msa", description="msa, emirati, levantine, egyptian")
    dialogue_history: List[ChatMessage] = Field(default_factory=list)
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)


class ExamsExplainRequest(BaseModel):
    request_id: str = Field(default_factory=lambda: f"exam-{uuid.uuid4().hex[:12]}")
    question_text: str = Field(..., description="Arabic exam question")
    options: Optional[List[str]] = Field(None, description="Multiple choice options if any")
    correct_answer: Optional[str] = Field(None, description="The designated correct answer")
    student_answer: Optional[str] = Field(None, description="The answer selected by the student")
    parameters: GenerationParameters = Field(default_factory=GenerationParameters)


# ==========================================
# Feedback & Continuous Learning Schemas
# ==========================================

class FeedbackCategory(str, Enum):
    GRAMMATICAL_ERROR = "grammatical_error"
    MORPHOLOGICAL_ERROR = "morphological_error"
    HALLUCINATION = "hallucination"
    DIALECTAL_DRIFT = "dialectal_drift"
    PEDAGOGICAL_CLARITY = "pedagogical_clarity"
    HELPFUL = "helpful"
    OTHER = "other"


class ReviewStatus(str, Enum):
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class ConsentStatus(str, Enum):
    GRANTED = "granted"
    REVOKED = "revoked"
    NOT_PROVIDED = "not_provided"


class FeedbackSubmissionRequest(BaseModel):
    feedback_id: str = Field(default_factory=lambda: f"fb-{uuid.uuid4().hex[:12]}")
    request_id: str = Field(..., description="ID of the inference request being evaluated")
    rating: int = Field(..., ge=1, le=5, description="1 to 5 rating scale")
    category: FeedbackCategory = Field(FeedbackCategory.OTHER)
    user_correction: Optional[str] = Field(None, description="Customer or philologist suggested correction")
    comments: Optional[str] = Field(None, description="Optional descriptive commentary")
    consent_for_training: bool = Field(False, description="Explicit customer consent for anonymized dataset inclusion")
    user_id_hash: Optional[str] = Field(None, description="Anonymized hash of user identifier")
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)


class FeedbackSubmissionResponse(BaseModel):
    feedback_id: str
    status: str = "received"
    consent_recorded: bool
    eligible_for_learning_pipeline: bool
    message: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class CandidateDatasetRecord(BaseModel):
    candidate_id: str
    feedback_id: str
    request_id: str
    domain: str
    input_prompt_sanitized: str
    original_model_output_sanitized: str
    curated_ground_truth: str
    review_status: ReviewStatus = ReviewStatus.PENDING_REVIEW
    quality_score: Optional[float] = None
    reviewer_notes: Optional[str] = None
    pii_redacted: bool = True
    dataset_version_target: str = "v0.1.0-candidates"
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


# ==========================================
# Response and Metadata Schemas
# ==========================================

class UsageMetadata(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0


class TelemetryMetadata(BaseModel):
    latency_ms: float = 0.0
    finish_reason: Optional[str] = "stop"
    is_truncated: bool = False


class ErrorDetail(BaseModel):
    code: str
    message: str
    details: Optional[Dict[str, Any]] = None


class CentralAPIResponse(BaseModel):
    request_id: str
    status: str = Field("success", description="success or error")
    content: Optional[str] = Field(None, description="Final generated answer content (reasoning withheld)")
    model: str
    provider: str
    usage: UsageMetadata = Field(default_factory=UsageMetadata)
    telemetry: TelemetryMetadata = Field(default_factory=TelemetryMetadata)
    error: Optional[ErrorDetail] = None
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str
    active_provider: str
    active_model: str
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class ReadyResponse(BaseModel):
    ready: bool
    active_provider: str
    active_model: str
    provider_status: str
    disk_free_gb: float
    memory_free_pct: Optional[float] = None
    sequential_lock_idle: bool = True
    timestamp: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
