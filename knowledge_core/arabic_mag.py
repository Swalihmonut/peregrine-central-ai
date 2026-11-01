"""
Memory-Augmented Generation (MAG) Engine
Implements a 3-tier student memory architecture:
- Layer 1: Short-term conversation turn buffer (sliding window).
- Layer 2: User-approved long-term pedagogical memory (mastered concepts, weaknesses, preferences).
- Layer 3: Grounded domain knowledge retrieval (RAG).
Enforces strict session & user isolation, explicit user consent, memory provenance,
and context assembly under strict token budget constraints.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
import uuid

from .arabic_nlp import text_processor
from .arabic_rag import ArabicRAGEngine


@dataclass
class PedagogicalMemoryItem:
    """A discrete, structured pedagogical fact or student trait with consent tracking."""

    memory_id: str
    user_id: str
    category: str  # 'mastered_concept', 'grammar_weakness', 'pronunciation_weakness', 'dialect_preference', 'cefr_level'
    key: str  # e.g., 'concept:idafa', 'pronunciation:qaf'
    summary: str  # Concise pedagogical summary in Arabic
    confidence: float = 0.85
    consent_status: str = "approved"  # 'approved', 'pending', 'rejected'
    source_turn_id: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ConversationTurn:
    turn_id: str
    role: str  # 'user' or 'assistant'
    content: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class StudentMemoryState:
    """Isolated memory state container for an individual student."""

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.short_term_turns: List[ConversationTurn] = []
        self.long_term_memories: Dict[str, PedagogicalMemoryItem] = {}
        self.max_short_term_turns: int = 4  # Sliding window of last 4 turns

    def add_turn(self, role: str, content: str) -> ConversationTurn:
        turn = ConversationTurn(
            turn_id=f"turn_{uuid.uuid4().hex[:8]}",
            role=role,
            content=content,
        )
        self.short_term_turns.append(turn)
        if len(self.short_term_turns) > self.max_short_term_turns:
            self.short_term_turns = self.short_term_turns[-self.max_short_term_turns :]
        return turn

    def add_memory(self, item: PedagogicalMemoryItem) -> None:
        if item.user_id != self.user_id:
            raise PermissionError("Cross-user memory violation: item user_id does not match state user_id.")
        self.long_term_memories[item.memory_id] = item

    def delete_memory(self, memory_id: str) -> bool:
        if memory_id in self.long_term_memories:
            del self.long_term_memories[memory_id]
            return True
        return False

    def clear_all(self) -> int:
        count = len(self.long_term_memories)
        self.long_term_memories.clear()
        self.short_term_turns.clear()
        return count


class ArabicMAGEngine:
    """
    Memory-Augmented Generation Engine.
    Coordinates short-term turns, approved pedagogical memory, and external RAG citations.
    """

    def __init__(self, rag_engine: Optional[ArabicRAGEngine] = None):
        self.rag_engine = rag_engine or ArabicRAGEngine()
        # In-memory tenant store indexed by user_id
        self._user_states: Dict[str, StudentMemoryState] = {}

    def get_or_create_student_state(self, user_id: str) -> StudentMemoryState:
        """Retrieve student state with strict isolation."""
        if not user_id:
            raise ValueError("user_id cannot be empty")
        if user_id not in self._user_states:
            self._user_states[user_id] = StudentMemoryState(user_id=user_id)
        return self._user_states[user_id]

    def record_turn(self, user_id: str, role: str, content: str) -> ConversationTurn:
        """Record a conversation turn in the Layer 1 short-term sliding window."""
        state = self.get_or_create_student_state(user_id)
        return state.add_turn(role=role, content=content)

    def add_approved_memory(
        self,
        user_id: str,
        category: str,
        key: str,
        summary: str,
        confidence: float = 0.90,
        source_turn_id: Optional[str] = None,
    ) -> PedagogicalMemoryItem:
        """
        Record a user-approved long-term pedagogical memory item.
        NEVER stores raw customer conversations as long-term memory.
        """
        state = self.get_or_create_student_state(user_id)
        mem_id = f"mem_{uuid.uuid4().hex[:8]}"
        item = PedagogicalMemoryItem(
            memory_id=mem_id,
            user_id=user_id,
            category=category,
            key=key,
            summary=summary,
            confidence=confidence,
            consent_status="approved",
            source_turn_id=source_turn_id,
        )
        state.add_memory(item)
        return item

    def forget_memory(self, user_id: str, memory_id: str) -> bool:
        """User-initiated forgetting of a specific pedagogical memory item."""
        if user_id not in self._user_states:
            return False
        return self._user_states[user_id].delete_memory(memory_id)

    def purge_user_memory(self, user_id: str) -> int:
        """Complete data deletion and retention compliance for a student."""
        if user_id not in self._user_states:
            return 0
        count = self._user_states[user_id].clear_all()
        del self._user_states[user_id]
        return count

    def select_relevant_memories(
        self,
        user_id: str,
        query: str,
        max_items: int = 3,
    ) -> List[PedagogicalMemoryItem]:
        """
        Score and select relevant approved long-term memories for current prompt.
        Only items with consent_status == 'approved' are eligible.
        """
        if user_id not in self._user_states:
            return []

        state = self._user_states[user_id]
        norm_query = text_processor.normalize(query)
        query_stems = text_processor.extract_stems(query)

        candidates = []
        for item in state.long_term_memories.values():
            if item.consent_status != "approved":
                continue

            # Compute topic relevance score between query and memory summary/key
            item_text = f"{item.key} {item.summary}"
            norm_item = text_processor.normalize(item_text)
            item_stems = text_processor.extract_stems(item_text)

            match_score = 0.0

            # Check stem overlap
            overlap = query_stems.intersection(item_stems)
            if overlap:
                match_score += len(overlap) * 0.35

            # Word exact match
            for word in norm_query.split():
                if len(word) > 2 and word in norm_item:
                    match_score += 0.30

            # Only select memory if there is actual relevance to current query
            if match_score > 0.0:
                if "weakness" in item.category:
                    match_score += 0.15
                candidates.append((match_score, item))

        candidates.sort(key=lambda x: x[0], reverse=True)
        return [c[1] for c in candidates[:max_items]]

    def assemble_mag_prompt_context(
        self,
        user_id: str,
        query: str,
        category: Optional[str] = None,
        max_mag_tokens: int = 250,
        max_rag_tokens: int = 400,
    ) -> Dict[str, any]:
        """
        Assemble the complete 3-Tier MAG prompt context within strict token budgets:
        - Layer 1: Short-term conversation turns
        - Layer 2: Selected approved pedagogical memory cards (bounded by max_mag_tokens)
        - Layer 3: Authoritative RAG citations (bounded by max_rag_tokens)
        """
        state = self.get_or_create_student_state(user_id)

        # 1. Layer 2: Retrieve relevant pedagogical memory cards
        selected_memories = self.select_relevant_memories(user_id, query, max_items=3)
        mag_memory_lines = []
        for mem in selected_memories:
            cat_label = {
                "grammar_weakness": "نقطة ضعف نحوية",
                "pronunciation_weakness": "تنبيه نطقي",
                "mastered_concept": "مفهوم متقن",
                "dialect_preference": "اللهجة المفضلة",
                "cefr_level": "المستوى اللغوي",
            }.get(mem.category, "ملاحظة تعليمية")
            mag_memory_lines.append(f"- [{cat_label}]: {mem.summary}")

        mag_context_text = ""
        if mag_memory_lines:
            # Enforce max_mag_tokens budget (~4 chars per token)
            mag_raw = "\n".join(mag_memory_lines)
            max_chars = max_mag_tokens * 4
            if len(mag_raw) > max_chars:
                mag_raw = mag_raw[:max_chars] + "..."
            mag_context_text = (
                "=== الملف التعليمي التراكمي المعتمد للطالب (MAG) ===\n"
                f"{mag_raw}\n"
                "=== وظّف هذه الملاحظات لتخصيص الإجابة دون التصريح للطالب بأنك تقرأ سجله ==="
            )

        # 2. Layer 3: Retrieve domain knowledge from RAG
        rag_result = self.rag_engine.retrieve(
            query=query,
            category=category,
            user_id=user_id,
            top_k=2,
        )

        rag_context_text = ""
        if rag_result["has_sufficient_evidence"]:
            rag_context_text = rag_result["formatted_context"]
            max_rag_chars = max_rag_tokens * 4
            if len(rag_context_text) > max_rag_chars:
                rag_context_text = rag_context_text[:max_rag_chars] + "\n=== نهاية المصادر الموثقة ==="

        # 3. Layer 1: Format short-term history
        history_formatted = [
            {"role": turn.role, "content": turn.content} for turn in state.short_term_turns
        ]

        # 4. Synthesize complete context envelope
        assembled_sections = []
        if mag_context_text:
            assembled_sections.append(mag_context_text)
        if rag_context_text:
            assembled_sections.append(rag_context_text)

        system_instruction_context = "\n\n".join(assembled_sections)

        return {
            "user_id": user_id,
            "query": query,
            "has_grounded_evidence": rag_result["has_sufficient_evidence"],
            "evidence_confidence": rag_result["confidence_score"],
            "citations": rag_result["citations"],
            "selected_memories": [
                {"id": m.memory_id, "category": m.category, "summary": m.summary}
                for m in selected_memories
            ],
            "short_term_history": history_formatted,
            "system_instruction_context": system_instruction_context,
            "fallback_message": rag_result.get("fallback_message"),
        }
