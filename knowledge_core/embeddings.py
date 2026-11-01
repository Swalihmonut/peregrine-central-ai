"""
Arabic Embeddings & Vector Representations
Provides deterministic subword n-gram embeddings for offline/sandboxed execution
and mock adapters for live cloud models (Google text-embedding-004 / Jais).
"""

from abc import ABC, abstractmethod
import math
from typing import List, Optional
from .arabic_nlp import text_processor


class ArabicEmbeddingModel(ABC):
    """Abstract base class for Arabic text embeddings."""

    @abstractmethod
    def embed_text(self, text: str) -> List[float]:
        """Generate a dense float vector for input text."""
        pass

    @abstractmethod
    def get_dimension(self) -> int:
        """Return the vector dimensionality."""
        pass

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two unit-normalized or arbitrary float vectors."""
        if not vec_a or not vec_b or len(vec_a) != len(vec_b):
            return 0.0

        dot = 0.0
        norm_a = 0.0
        norm_b = 0.0

        for a, b in zip(vec_a, vec_b):
            dot += a * b
            norm_a += a * a
            norm_b += b * b

        denom = math.sqrt(norm_a) * math.sqrt(norm_b)
        if denom <= 0.0:
            return 0.0

        return round(dot / denom, 5)


class DeterministicArabicEmbeddings(ArabicEmbeddingModel):
    """
    Fast, deterministic 128-dimensional vector generator for Arabic text.
    Combines word tokens, subword character trigrams, and morphological stems
    into a unit-normalized vector. Enables semantic and morphological proximity
    without requiring external GPU/API models.
    """

    def __init__(self, dimension: int = 128):
        self.dimension = dimension

    def get_dimension(self) -> int:
        return self.dimension

    def embed_text(self, text: str) -> List[float]:
        vector = [0.0] * self.dimension
        if not text or not text.strip():
            return vector

        normalized = text_processor.normalize(text)
        words = normalized.split()
        stems = text_processor.extract_stems(text)

        # 1. Hash full words (weight 1.0)
        for word in words:
            h = 5381
            for char in word:
                h = ((h << 5) + h) ^ ord(char)
            idx = abs(h) % self.dimension
            vector[idx] += 1.0

            # 2. Hash character trigrams for morphological root proximity (weight 0.5)
            if len(word) >= 3:
                for i in range(len(word) - 2):
                    tri = word[i : i + 3]
                    tri_hash = 0
                    for c in tri:
                        tri_hash = (tri_hash << 5) - tri_hash + ord(c)
                    t_idx = abs(tri_hash) % self.dimension
                    vector[t_idx] += 0.5

        # 3. Hash morphological stems (weight 0.75) to strengthen lemma matches
        for stem in stems:
            stem_hash = 7919
            for char in stem:
                stem_hash = ((stem_hash << 5) + stem_hash) ^ ord(char)
            s_idx = abs(stem_hash) % self.dimension
            vector[s_idx] += 0.75

        # 4. L2 unit-norm normalization
        norm = math.sqrt(sum(v * v for v in vector))
        if norm > 0.0:
            vector = [round(v / norm, 6) for v in vector]

        return vector


class MockProviderEmbeddings(ArabicEmbeddingModel):
    """
    Mock embedding adapter simulating 768-dim (Gemini) or 1536-dim (OpenAI) outputs.
    Status: LIVE EXECUTION NOT VERIFIED (SANDBOXED PROXY).
    """

    def __init__(self, provider: str = "google-text-embedding-004", dimension: int = 768):
        self.provider = provider
        self.dimension = dimension
        self.status = "LIVE EXECUTION NOT VERIFIED — DETERMINISTIC REPRODUCIBLE PROXY"
        self._fallback = DeterministicArabicEmbeddings(dimension=128)

    def get_dimension(self) -> int:
        return self.dimension

    def embed_text(self, text: str) -> List[float]:
        # Expand 128-dim core into higher dimension via deterministic tiled projection
        base = self._fallback.embed_text(text)
        repeats = (self.dimension // len(base)) + 1
        expanded = (base * repeats)[: self.dimension]
        norm = math.sqrt(sum(v * v for v in expanded))
        if norm > 0.0:
            return [round(v / norm, 6) for v in expanded]
        return expanded
