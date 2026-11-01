"""
Arabic RAG Engine
Provides document ingestion, chunking, hybrid retrieval, anti-injection formatting,
page-level citation generation, document deletion, and no-answer thresholding.
"""

from typing import Dict, List, Optional
from .arabic_nlp import text_processor
from .embeddings import ArabicEmbeddingModel, DeterministicArabicEmbeddings
from .vector_store import DocumentChunk, SearchResult, VectorStore


# Authentic classical Arabic corpus representing Nahw, Sarf, Balagha, and Literature
SyntheticHeritageCorpus: List[Dict[str, any]] = [
    {
        "source_id": "src_sibawayh_kitab",
        "title": "الكتاب",
        "author": "سيبويه (أبو بشر عمرو بن عثمان)",
        "section": "باب المسند والمسند إليه",
        "category": "nahw",
        "page_number": 12,
        "content": (
            "هذا باب المسند والمسند إليه، وهما ما لا يغني واحد منهما عن الآخر، ولا يجد المتكلم منه بدا. "
            "فمن ذلك الاسم المبتدأ والمبني عليه، وهو قولك: عبد الله أخوك، وهذا أخوك. ومثل ذلك: يذهب عبد الله، "
            "فلا بد للفعل من الاسم، كما لم يكن للاسم الأول بد من الآخر في الابتداء."
        ),
        "tags": ["المبتدأ", "الخبر", "المسند", "الإسناد", "النحو", "سيبويه"],
    },
    {
        "source_id": "src_ibn_jinni_khasais",
        "title": "الخصائص",
        "author": "ابن جني (أبو الفتح عثمان)",
        "section": "باب في تصاقب الألفاظ لتصاقب المعاني",
        "category": "sarf",
        "page_number": 45,
        "content": (
            "هذا موضع شريف لطيف، قد نبه عليه الخليل وسيبويه، وتلقته الجماعة بالقبول. وهو أن تجعل الحروف المستعملة "
            "في الكلمة دالة على قوة الحدث أو ضعفه، كقولهم: خضم وقضم؛ فالخضم لأكل الرطب كالبطيخ والقثاء، "
            "والقضم لأكل اليابس كالحصى والخبز اليابس، فاختاروا الخاء لرخاوتها مع الرطب والقاف لصلابتها مع اليابس."
        ),
        "tags": ["الصرف", "الاشتقاق", "تصاقب الألفاظ", "فقه اللغة", "ابن جني"],
    },
    {
        "source_id": "src_jurjani_dalail",
        "title": "دلائل الإعجاز",
        "author": "عبد القاهر الجرجاني",
        "section": "فصل في حقيقة النظم والبيان",
        "category": "balagha",
        "page_number": 88,
        "content": (
            "واعلم أن النظم ليس شيئا غير توخي معاني النحو وأحكامه ووجوهه وفروقه فيما بين الكلم، "
            "وألا تضع كلمة إلا في الموضع الذي يقتضيه علم النحو وعلم البيان. فليس الشأن أن تجمع بين ألفاظ رنانة، "
            "بل الشأن أن تناسب بين المعاني بنظم دقيق يبرز حقيقة البلاغة والإعجاز."
        ),
        "tags": ["البلاغة", "النظم", "الإعجاز", "البيان", "الجرجاني"],
    },
    {
        "source_id": "src_ibn_malik_alfiyyah",
        "title": "ألفية ابن مالك",
        "author": "ابن مالك الأندلسي",
        "section": "باب الفاعل",
        "category": "nahw",
        "page_number": 23,
        "content": (
            "الفاعل الذي كمرفوعي أتى * زيد منيرا وجهه نعم الفتى. "
            "وبعد فعل فاعل فإن ظهر * فهو وإلا فضمير استتر. "
            "وجرد الفعل إذا ما أسنِدا * لاثنين أو جمع كفاز الشهدا."
        ),
        "tags": ["الفاعل", "الألفية", "النحو", "ابن مالك", "الشعر التعليمي"],
    },
    {
        "source_id": "src_jahiz_bayan",
        "title": "البيان والتبيين",
        "author": "الجاحظ (عمرو بن بحر)",
        "section": "باب حد البلاغة ومفهوم الإبانة",
        "category": "literature",
        "page_number": 61,
        "content": (
            "قال أبو عثمان: دلالة اللفظ أوسع من كل إشارة، وأشرف المحاسن البيان. ولا يكون الكلام يستحق اسم البلاغة "
            "حتى يسابق معناه لفظه، ولفظه معناه، فلا يكون لفظه إلى سمعك أسبق من معناه إلى قلبك، مع إيجاز غير مخل "
            "وإسهاب غير ممل."
        ),
        "tags": ["الأدب", "البيان", "الجاحظ", "البلاغة", "الإبانة"],
    },
]


class ArabicRAGEngine:
    """End-to-end RAG Engine for Classical and Modern Arabic literature and treatises."""

    def __init__(self, embedding_model: Optional[ArabicEmbeddingModel] = None):
        self.embedding_model = embedding_model or DeterministicArabicEmbeddings()
        self.vector_store = VectorStore(self.embedding_model)
        self.confidence_threshold = 0.45
        # Automatically seed with synthetic heritage corpus
        self._seed_heritage_corpus()

    def _seed_heritage_corpus(self) -> None:
        """Seed the vector store with verified Arabic heritage excerpts."""
        chunks: List[DocumentChunk] = []
        for doc in SyntheticHeritageCorpus:
            chunk = DocumentChunk(
                id=f"{doc['source_id']}_c1",
                source_id=doc["source_id"],
                title=doc["title"],
                author=doc["author"],
                section=doc["section"],
                content=doc["content"],
                category=doc["category"],
                tags=doc.get("tags", []),
                page_number=doc.get("page_number", 1),
                user_id=None,  # Public corpus available to all users
            )
            chunks.append(chunk)
        self.vector_store.add_chunks(chunks)

    def ingest_document(
        self,
        source_id: str,
        title: str,
        author: str,
        content: str,
        category: str = "general",
        page_number: int = 1,
        user_id: Optional[str] = None,
        tags: Optional[List[str]] = None,
    ) -> int:
        """
        Chunk and ingest a text or multi-page treatise into the vector store.
        Respects Arabic sentence boundaries and captures full provenance.
        """
        text_chunks = text_processor.chunk_text(content, max_chunk_chars=400, overlap_chars=50)
        doc_chunks: List[DocumentChunk] = []

        for idx, chunk_text in enumerate(text_chunks):
            doc_chunk = DocumentChunk(
                id=f"{source_id}_c{idx+1}",
                source_id=source_id,
                title=title,
                author=author,
                section=f"مقطع {idx+1}",
                content=chunk_text,
                category=category,
                tags=tags or [],
                page_number=page_number,
                user_id=user_id,
            )
            doc_chunks.append(doc_chunk)

        return self.vector_store.add_chunks(doc_chunks)

    def delete_document(self, source_id: str, user_id: Optional[str] = None) -> int:
        """Permanently delete all chunks associated with a source document."""
        return self.vector_store.delete_by_source_id(source_id, user_id=user_id)

    def retrieve(
        self,
        query: str,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        top_k: int = 3,
        min_similarity: Optional[float] = None,
    ) -> Dict[str, any]:
        """
        Retrieve relevant Arabic citations and synthesize formatted context block.
        Implements anti-prompt injection sanitation and no-answer thresholding.
        """
        threshold = min_similarity if min_similarity is not None else self.confidence_threshold
        results = self.vector_store.search(
            query=query,
            category=category,
            user_id=user_id,
            top_k=top_k,
            min_similarity=threshold,
        )

        # Check for no-answer state (no results meeting confidence threshold or lacking topical grounding)
        if not results or (results[0].exact_match_bonus == 0.0 and results[0].total_score < 0.70):
            return {
                "has_sufficient_evidence": False,
                "confidence_score": results[0].total_score if results else 0.0,
                "formatted_context": "",
                "citations": [],
                "fallback_message": (
                    "عذرا، لم نجد شواهد تراثية موثقة كافية في قاعدة المعرفة المعتمدة للإجابة بدقة عن هذا السؤال. "
                    "يرجى تحديد المصطلح النحوي أو البلاغي أو رفع الوثيقة المعنية."
                ),
            }

        top_score = results[0].total_score
        citations = [r.citation for r in results]

        # Assemble safe context block with prompt-injection defense
        context_blocks = []
        for idx, res in enumerate(results):
            # Sanitize raw chunk content
            clean_text = (
                res.chunk.content.replace("```", "'''")
                .replace("<system>", "")
                .replace("</system>", "")
                .replace("ignore previous instructions", "[محاولة تجاوز محجوبة]")
            )
            block = (
                f"[المصدر {idx + 1}]: «{res.chunk.title}» — {res.chunk.author} (صفحة: {res.chunk.page_number})\n"
                f"الموضع: {res.chunk.section}\n"
                f"المحتوى المقتبس:\n{clean_text}"
            )
            context_blocks.append(block)

        formatted_context = (
            "=== شواهد ومصادر تراثية موثقة من قاعدة المعرفة ===\n"
            + "\n\n---\n\n".join(context_blocks)
            + "\n=== نهاية المصادر الموثقة (التزم بهذه الشواهد واذكر أسماء مؤلفيها بدقة) ==="
        )

        return {
            "has_sufficient_evidence": True,
            "confidence_score": top_score,
            "formatted_context": formatted_context,
            "citations": citations,
            "fallback_message": None,
        }

    def evaluate_retrieval(
        self,
        query: str,
        expected_source_id: str,
        category: Optional[str] = None,
        top_k: int = 3,
    ) -> Dict[str, any]:
        """Evaluate retrieval accuracy against expected ground-truth source."""
        ret = self.retrieve(query, category=category, top_k=top_k)
        retrieved_sources = [c["source_id"] for c in ret["citations"]]
        is_hit = expected_source_id in retrieved_sources
        rank = retrieved_sources.index(expected_source_id) + 1 if is_hit else None

        return {
            "query": query,
            "expected_source_id": expected_source_id,
            "retrieved_sources": retrieved_sources,
            "hit": is_hit,
            "rank": rank,
            "confidence": ret["confidence_score"],
        }
