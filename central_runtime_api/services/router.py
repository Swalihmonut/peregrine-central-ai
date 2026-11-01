"""Domain service routing for Arabic Tutor, Speaking Partner, Exams, Chat, and Feedback."""

from __future__ import annotations

from typing import List

from central_runtime_api.schemas import (
    CentralAPIResponse,
    ChatMessage,
    ChatRequest,
    ExamsExplainRequest,
    FeedbackSubmissionRequest,
    FeedbackSubmissionResponse,
    MessageRole,
    SpeakingRespondRequest,
    TutorExplainRequest,
)
from central_runtime_api.services.feedback_store import FeedbackStore
from central_runtime_api.services.provider_manager import ProviderManager


class CentralAPIRouter:
    """Orchestrates application domain prompts, feedback ingestion, and delegates to ProviderManager."""

    def __init__(self, provider_manager: ProviderManager, feedback_store: FeedbackStore):
        self.manager = provider_manager
        self.feedback_store = feedback_store

    def handle_chat(self, req: ChatRequest) -> CentralAPIResponse:
        """General conversational endpoint."""
        return self.manager.execute_inference(
            messages=req.messages,
            parameters=req.parameters,
            request_id=req.request_id,
        )

    def handle_tutor_explain(self, req: TutorExplainRequest) -> CentralAPIResponse:
        """Arabic AI Tutor endpoint: explains grammar, syntax, morphology with pedagogical clarity."""
        system_prompt = (
            "أنت «المعلم الذكي للغة العربية» (Arabic AI Tutor). "
            "مهمتك شرح المسائل اللغوية والنحوية والصرفية بدقة علمية وأسلوب تربوي واضح ومبسط. "
            f"مستوى الطالب المستهدف: {req.level}. مجال السؤال: {req.topic}.\n"
            "إرشادات الإجابة:\n"
            "1. اذكر القاعدة الأساسية بوضوح وإيجاز.\n"
            "2. قم بإعراب أو تحليل الشواهد المستهدفة بدقة تامة بالحركات.\n"
            "3. قدم أمثلة توضيحية إضافية تعزز الفهم.\n"
            "4. تجنب المصطلحات المعقدة دون شرحها، وتجنب اللحن تماماً."
        )

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=f"اشرح لي المسألة التالية بالتفصيل: {req.query}"),
        ]

        return self.manager.execute_inference(
            messages=messages,
            parameters=req.parameters,
            request_id=req.request_id,
        )

    def handle_speaking_respond(self, req: SpeakingRespondRequest) -> CentralAPIResponse:
        """AI Speaking Partner endpoint: natural conversational turn-taking with pronunciation/vocabulary tips."""
        dialect_desc = "اللغة العربية الفصحى المعاصرة" if req.dialect == "msa" else f"اللهجة {req.dialect}"
        system_prompt = (
            "أنت «شريك المحادثة الذكي» (AI Speaking Partner) لمتعلمي اللغة العربية. "
            f"المشهد التواصلي: {req.scenario}. لغة التخاطب: {dialect_desc}.\n"
            "إرشادات المحادثة:\n"
            "1. استجب لعبارة المتعلم بأسلوب طبيعي وتفاعلي وودود.\n"
            "2. اطرح سؤالاً مفتوحاً أو تعليقاً يحفز على استمرار الحوار.\n"
            "3. إذا كان هناك خطأ لغوي جسيم في عبارة المتعلم، نبهه عليه بلطف واقترح الصياغة الأصح.\n"
            "4. حافظ على تناسق الرد مع تاريخ المحادثة السابقة."
        )

        messages: List[ChatMessage] = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
        ]
        messages.extend(req.dialogue_history)
        messages.append(ChatMessage(role=MessageRole.USER, content=req.user_utterance))

        return self.manager.execute_inference(
            messages=messages,
            parameters=req.parameters,
            request_id=req.request_id,
        )

    def handle_exams_explain(self, req: ExamsExplainRequest) -> CentralAPIResponse:
        """Exams App endpoint: question analysis, correct answer rationale, and distracter analysis."""
        system_prompt = (
            "أنت «مساعد الامتحانات والاختبارات اللغوية» (Arabic Exams AI Assistant). "
            "مهمتك تحليل الأسئلة الامتحانية بدقة أكاديمية عالية.\n"
            "إرشادات التحليل:\n"
            "1. حدد الحكم النحوي أو الصرفي أو البلاغي الصحيح مع التعليل القاطع.\n"
            "2. بيّن بالتفصيل لماذا الإجابة الصحيحة هي الصواب وفق قواعد اللغة.\n"
            "3. إذا وُجدت خيارات متعددة، فند الخيارات الخاطئة (المشتتات) موضحاً موضع الخلل في كل خيار.\n"
            "4. قدم نصيحة مهارية للطالب لتجنب الوقوع في مثل هذا الخطأ في الامتحانات."
        )

        user_content = f"السؤال الامتحاني: {req.question_text}\n"
        if req.options:
            user_content += f"الخيارات المتاحة:\n" + "\n".join(f"- {opt}" for opt in req.options) + "\n"
        if req.correct_answer:
            user_content += f"الإجابة المعتمدة: {req.correct_answer}\n"
        if req.student_answer:
            user_content += f"إجابة الطالب المختارة: {req.student_answer}\n"
        user_content += "المطلوب: قدم تحليلاً شاملاً وتبريراً علمياً للإجابة الصحيحة وتفنيد المشتتات."

        messages = [
            ChatMessage(role=MessageRole.SYSTEM, content=system_prompt),
            ChatMessage(role=MessageRole.USER, content=user_content),
        ]

        return self.manager.execute_inference(
            messages=messages,
            parameters=req.parameters,
            request_id=req.request_id,
        )

    def handle_feedback(self, req: FeedbackSubmissionRequest) -> FeedbackSubmissionResponse:
        """Ingest user or philologist feedback, enforcing consent boundaries."""
        return self.feedback_store.record_feedback(req)

    def handle_withdraw_consent(self, user_id: str) -> dict:
        """Process consent withdrawal request."""
        return self.feedback_store.withdraw_consent(user_id)

