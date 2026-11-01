"""
Peregrine Arabic AI Knowledge Core
Provides Arabic-aware RAG (Retrieval-Augmented Generation)
and MAG (Memory-Augmented Generation) infrastructure for Beta V-001.
"""

from .arabic_nlp import ArabicTextProcessor
from .embeddings import ArabicEmbeddingModel, DeterministicArabicEmbeddings, MockProviderEmbeddings
from .vector_store import VectorStore, DocumentChunk, SearchResult
from .arabic_rag import ArabicRAGEngine, SyntheticHeritageCorpus
from .arabic_mag import ArabicMAGEngine, PedagogicalMemoryItem, StudentMemoryState

__all__ = [
    "ArabicTextProcessor",
    "ArabicEmbeddingModel",
    "DeterministicArabicEmbeddings",
    "MockProviderEmbeddings",
    "VectorStore",
    "DocumentChunk",
    "SearchResult",
    "ArabicRAGEngine",
    "SyntheticHeritageCorpus",
    "ArabicMAGEngine",
    "PedagogicalMemoryItem",
    "StudentMemoryState",
]
