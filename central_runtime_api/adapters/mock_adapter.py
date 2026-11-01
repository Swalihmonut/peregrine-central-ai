"""Mock Provider Adapter for offline development and deterministic testing."""

from __future__ import annotations

import time
from typing import Any, Dict, List

from central_runtime_api.adapters.base import BaseProviderAdapter
from central_runtime_api.schemas import (
    CentralAPIResponse,
    ChatMessage,
    ErrorDetail,
    GenerationParameters,
    TelemetryMetadata,
    UsageMetadata,
)


class MockProviderAdapter(BaseProviderAdapter):
    """Deterministic mock adapter simulating realistic responses without model loading or GPU use."""

    @property
    def provider_name(self) -> str:
        return "mock"

    def is_ready(self) -> bool:
        return True

    def check_health(self) -> Dict[str, Any]:
        return {
            "status": "healthy",
            "provider": self.provider_name,
            "simulated_model": self.model_name,
            "mode": "in-memory-mock",
        }

    def generate(
        self,
        messages: List[ChatMessage],
        parameters: GenerationParameters,
        request_id: str,
    ) -> CentralAPIResponse:
        start_time = time.perf_counter()

        system_text = ""
        last_user_message = ""
        for m in messages:
            if m.role.value == "system":
                system_text += m.content + " "
            elif m.role.value == "user":
                last_user_message = m.content

        # Simulate synthetic failure condition if triggered
        if "__FORCE_ERROR__" in last_user_message and "fallback" not in self.model_name.lower():
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="error"),
                error=ErrorDetail(
                    code="SIMULATED_PROVIDER_FAILURE",
                    message="Forced synthetic failure triggered by test query.",
                ),
            )

        # Simulate model timeout if triggered
        if "__FORCE_TIMEOUT__" in last_user_message:
            latency_ms = (time.perf_counter() - start_time) * 1000 + 5000.0
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="timeout"),
                error=ErrorDetail(
                    code="MODEL_TIMEOUT",
                    message="Inference request timed out after configured duration.",
                ),
            )

        # Simulate provider unavailable if triggered
        if "__FORCE_UNAVAILABLE__" in last_user_message:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="unavailable"),
                error=ErrorDetail(
                    code="PROVIDER_UNAVAILABLE",
                    message="Upstream provider is temporarily unreachable or unavailable.",
                ),
            )

        # Simulate empty response if triggered
        if "__FORCE_EMPTY__" in last_user_message:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="success",
                content="",
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(latency_ms=round(latency_ms, 2), finish_reason="stop"),
                usage=UsageMetadata(prompt_tokens=10, completion_tokens=0, total_tokens=10),
            )

        # Simulate empty content / reasoning only error if triggered
        if "__FORCE_REASONING_ONLY__" in last_user_message:
            latency_ms = (time.perf_counter() - start_time) * 1000
            return CentralAPIResponse(
                request_id=request_id,
                status="error",
                content=None,
                model=self.model_name,
                provider=self.provider_name,
                telemetry=TelemetryMetadata(
                    latency_ms=round(latency_ms, 2),
                    finish_reason="length",
                    is_truncated=True,
                ),
                error=ErrorDetail(
                    code="MODEL_REASONING_ONLY",
                    message="Model concluded without generating final answer content. Thinking trace withheld.",
                ),
            )

        # Generate contextual mock response based on prompt keywords
        response_text = self._synthesize_response(last_user_message, system_text)

        # Estimate mock tokens
        prompt_tokens = sum(len(m.content.split()) * 2 for m in messages)
        completion_tokens = len(response_text.split()) * 2
        total_tokens = prompt_tokens + completion_tokens

        latency_ms = (time.perf_counter() - start_time) * 1000 + 12.5  # Realistic mock latency ~12-15ms

        return CentralAPIResponse(
            request_id=request_id,
            status="success",
            content=response_text,
            model=self.model_name,
            provider=self.provider_name,
            usage=UsageMetadata(
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                total_tokens=total_tokens,
            ),
            telemetry=TelemetryMetadata(
                latency_ms=round(latency_ms, 2),
                finish_reason="stop",
                is_truncated=False,
            ),
            error=None,
        )

    def _synthesize_response(self, text: str, system_text: str = "") -> str:
        text_lower = text.lower()
        sys_lower = system_text.lower()

        # 1. AI Speaking Partner domain
        if "شريك المحادثة" in system_text or "speaking" in sys_lower or "speaking" in text_lower:
            return (
                "أهلاً بك يا صديقي! يسعدني جداً أن أتحدث معك باللغة العربية الفصحى اليوم. "
                "كيف كان يومك؟ وما هو الموضوع الذي تحب أن نتبادل أطراف الحديث حوله الآن؟"
            )

        # 2. Exams App domain
        if "مساعد الامتحانات" in system_text or "exam" in sys_lower or "exam" in text_lower:
            return (
                "تحليل السؤال الإمتحاني وتوضيح الإجابة الصحيحة:\n"
                "- الإجابة الصحيحة هي الخيار المطابق للقواعد المقررة.\n"
                "- التعليل العلمي: العامل النحوي المؤثر يتطلب حالة الرفع بالواو لأنه جمع مذكر سالم.\n"
                "- سبب استبعاد الخيارات الأخرى: الخيارات البديلة وقعت في خطأ عدم مطابقة علامة الإعراب لموقع الكلمة."
            )

        # 3. Arabic Tutor domain
        if "المعلم الذكي" in system_text or "إن" in text or "أعرب" in text or "إعراب" in text:
            if "استغفر" in text or "صرف" in text:
                return (
                    "التحليل الصرفي للفعل «اسْتَغْفَرَ»:\n"
                    "1. الجذر الثلاثي: (غ - ف - ر).\n"
                    "2. الوزن الصرفي: اسْتَفْعَلَ.\n"
                    "3. حروف الزيادة: ثلاثة أحرف (الهمزة، السين، التاء).\n"
                    "4. دلالة الزيادة: تفيد معنى «الطلب»، أي: طلب المغفرة والصفح."
                )
            elif "تشبيه" in text or "استعارة" in text:
                return (
                    "الفرق بين التشبيه والاستعارة والكناية:\n"
                    "1. التشبيه: عقد مماثلة بين طرفين بوجود أداة التشبيه ووجه الشبه (مثال: زيد كالأسد في الشجاعة).\n"
                    "2. الاستعارة: تشبيه بليغ حُذف أحد طرفيه (مثال: رأيتُ أسداً يخطب على المنبر).\n"
                    "3. الكناية: لفظ أُطلق وأُريد به لازم معناه مع جواز إرادة المعنى الأصلي (مثال: فلان كثير الرماد، كناية عن الكرم)."
                )
            else:
                return (
                    "الإعراب المفصل:\n"
                    "- «إنَّ»: حرف توكيد ونصب مبني على الفتح لا محل له من الإعراب.\n"
                    "- «العلمَ»: اسم إنّ منصوب وعلامة نصبه الفتحة الظاهرة على آخره.\n"
                    "- «نورٌ»: خبر إنّ مرفوع وعلامة رفعه الضمة الظاهرة على آخره.\n"
                    "القاعدة النحوية: تدخل (إنّ) وأخواتها على الجملة الاسمية فتنصب المبتدأ ويسمى اسمها، وترفع الخبر ويسمى خبرها."
                )

        # Default bilingual conversation
        return (
            "مرحباً بك في الخدمة المركزية للذكاء الاصطناعي العربي. "
            "أنا جاهز لمساعدتك في تعلم اللغة العربية، دراسة النحو والصرف، أو ممارسة المحادثة.\n\n"
            "Welcome to the Central Arabic AI Service. I am ready to assist you with Arabic pedagogy, grammar, or dialogue."
        )
