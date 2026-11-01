"""
Vector Store & Hybrid Search Index
Supports PostgreSQL+pgvector schema contracts and in-memory execution with
strict multi-tenant isolation, metadata filtering, and Arabic hybrid scoring.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional
from .arabic_nlp import text_processor
from .embeddings import ArabicEmbeddingModel, DeterministicArabicEmbeddings


@dataclass
class DocumentChunk:
    id: str
    source_id: str
    title: str
    author: str
    section: str
    content: str
    category: str
    tags: List[str] = field(default_factory=list)
    page_number: Optional[int] = 1
    user_id: Optional[str] = None  # None indicates shared public corpus
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    embedding: List[float] = field(default_factory=list)


@dataclass
class SearchResult:
    chunk: DocumentChunk
    similarity: float
    exact_match_bonus: float
    total_score: float
    citation: Dict[str, any]


class VectorStore:
    """
    High-performance vector index and document repository.
    Enforces tenant boundaries, cascading deletion, and hybrid Arabic retrieval.
    """

    def __init__(self, embedding_model: Optional[ArabicEmbeddingModel] = None):
        self.embedding_model = embedding_model or DeterministicArabicEmbeddings()
        self.chunks: Dict[str, DocumentChunk] = {}

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """Embed and index document chunks."""
        count = 0
        for chunk in chunks:
            if not chunk.embedding:
                embed_text = f"{chunk.title} {chunk.section} {chunk.content} {' '.join(chunk.tags)}"
                chunk.embedding = self.embedding_model.embed_text(embed_text)
            self.chunks[chunk.id] = chunk
            count += 1
        return count

    def delete_by_source_id(self, source_id: str, user_id: Optional[str] = None) -> int:
        """
        Delete all chunks associated with a source document.
        If user_id is provided, guarantees a user can only delete their own documents.
        """
        to_delete = []
        for c_id, chunk in self.chunks.items():
            if chunk.source_id == source_id:
                if user_id is not None and chunk.user_id != user_id:
                    # User unauthorized to delete this document
                    continue
                to_delete.append(c_id)

        for c_id in to_delete:
            del self.chunks[c_id]

        return len(to_delete)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        user_id: Optional[str] = None,
        top_k: int = 3,
        min_similarity: float = 0.15,
    ) -> List[SearchResult]:
        """
        Hybrid semantic + morphological retrieval with tenant isolation.
        - Semantic similarity via cosine metric
        - Arabic exact keyword & stem match bonus
        - Multi-tenant filter: permits shared public corpus (user_id is None) AND user's private chunks
        """
        if not query or not query.strip():
            return []

        query_vec = self.embedding_model.embed_text(query)
        norm_query = text_processor.normalize(query)
        query_words = set(norm_query.split())
        query_stems = text_processor.extract_stems(query)

        scored: List[SearchResult] = []

        for chunk in self.chunks.values():
            # 1. Tenant boundary enforcement: User A cannot see User B's documents
            if chunk.user_id is not None:
                if user_id is None or chunk.user_id != user_id:
                    continue

            # 2. Category metadata filter
            if category and chunk.category.lower() != category.lower():
                continue

            # 3. Vector cosine similarity
            cos_sim = ArabicEmbeddingModel.cosine_similarity(query_vec, chunk.embedding)

            # 4. Morphological and exact keyword match bonus
            chunk_norm = text_processor.normalize(f"{chunk.title} {chunk.section} {chunk.content}")
            chunk_stems = text_processor.extract_stems(chunk.content)

            bonus = 0.0

            # Exact word match bonus (+0.10 per word up to 0.30)
            for w in query_words:
                if len(w) > 2 and w in chunk_norm:
                    bonus += 0.10

            # Stem overlap bonus (+0.05 per shared stem up to 0.15)
            shared_stems = query_stems.intersection(chunk_stems)
            if shared_stems:
                bonus += min(0.15, len(shared_stems) * 0.05)

            bonus = min(0.40, round(bonus, 4))
            total_score = round(cos_sim + bonus, 4)

            if total_score >= min_similarity:
                excerpt = chunk.content[:160] + ("..." if len(chunk.content) > 160 else "")
                result = SearchResult(
                    chunk=chunk,
                    similarity=cos_sim,
                    exact_match_bonus=bonus,
                    total_score=total_score,
                    citation={
                        "source_id": chunk.source_id,
                        "title": chunk.title,
                        "author": chunk.author,
                        "section": chunk.section,
                        "page_number": chunk.page_number,
                        "excerpt": excerpt,
                        "relevance_score": total_score,
                    },
                )
                scored.append(result)

        # Sort descending by total composite score
        scored.sort(key=lambda r: r.total_score, reverse=True)
        return scored[:top_k]

    def count(self) -> int:
        return len(self.chunks)
