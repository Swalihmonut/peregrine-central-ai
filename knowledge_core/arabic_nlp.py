"""
Arabic Text Processor & Morphological Analyzer
Provides Arabic-aware normalization, light stemming, sentence segmentation,
and tokenization for search and retrieval.
"""

import re
from typing import List, Set
import pyarabic.araby as araby
from tashaphyne.stemming import ArabicLightStemmer


class ArabicTextProcessor:
    """Specialized NLP processor for Modern Standard and Classical Arabic text."""

    def __init__(self):
        self.stemmer = ArabicLightStemmer()

    def normalize(self, text: str, keep_diacritics: bool = False) -> str:
        """
        Normalize Arabic text for search indexing and exact/morphological comparison.
        - Strips tatweel (kashida: ـ)
        - Strips tashkeel (diacritics) if keep_diacritics is False
        - Normalizes alef variants (أ، إ، آ -> ا)
        - Normalizes teh marbuta (ة -> ه)
        - Normalizes alef maqsura (ى -> ي)
        - Normalizes multiple spaces
        """
        if not text:
            return ""

        result = text.strip()
        result = araby.strip_tatweel(result)

        if not keep_diacritics:
            result = araby.strip_tashkeel(result)

        # Normalize alef variants
        result = araby.normalize_alef(result)

        # Normalize teh marbuta to heh for indexing search
        result = re.sub(r"[ة]", "ه", result)

        # Normalize alef maqsura to yaa
        result = re.sub(r"[ى]", "ي", result)

        # Clean non-Arabic punctuation whitespace
        result = re.sub(r"\s+", " ", result)

        return result.strip().lower()

    def extract_stems(self, text: str) -> Set[str]:
        """
        Extract light stems for words in text to bridge morphological variants.
        E.g. 'المكتبة' -> 'مكتبه' -> 'مكتب'
        """
        normalized = self.normalize(text, keep_diacritics=False)
        words = re.findall(r"[\u0600-\u06FF\w]+", normalized)
        stems: Set[str] = set()

        for w in words:
            if len(w) < 3:
                continue
            stem = self.stemmer.light_stem(w)
            if stem:
                stems.add(stem)
            stems.add(w)

        return stems

    def split_sentences(self, text: str) -> List[str]:
        """
        Split Arabic text into coherent sentences using Arabic sentence delimiters
        (النقطة .، علامة الاستفهام ؟، علامة التعجب !، الفاصلة المنقوطة ؛، وفاصل الأسطر).
        """
        if not text or not text.strip():
            return []

        # Split on sentence boundaries followed by whitespace
        pattern = r"(?<=[.؟!؛\n])\s+"
        parts = re.split(pattern, text)
        sentences = [p.strip() for p in parts if p.strip()]
        return sentences

    def chunk_text(
        self,
        text: str,
        max_chunk_chars: int = 400,
        overlap_chars: int = 50,
    ) -> List[str]:
        """
        Arabic-aware document chunker.
        1. Segments by paragraphs (\n\n) first.
        2. Splits large paragraphs by Arabic sentence boundaries.
        3. Enforces max_chunk_chars while maintaining sliding overlap.
        """
        if not text or not text.strip():
            return []

        raw_paragraphs = re.split(r"\n\s*\n", text)
        chunks: List[str] = []

        for para in raw_paragraphs:
            trimmed = para.strip()
            if not trimmed:
                continue

            if len(trimmed) <= max_chunk_chars:
                chunks.append(trimmed)
                continue

            # Paragraph exceeds max size, split by Arabic sentences
            sentences = self.split_sentences(trimmed)
            current_chunk = ""

            for sentence in sentences:
                candidate = f"{current_chunk} {sentence}".strip() if current_chunk else sentence
                if len(candidate) <= max_chunk_chars:
                    current_chunk = candidate
                else:
                    if current_chunk:
                        chunks.append(current_chunk)
                    if len(current_chunk) > overlap_chars:
                        overlap_prefix = current_chunk[-overlap_chars:]
                        current_chunk = f"{overlap_prefix} {sentence}".strip()
                    else:
                        current_chunk = sentence.strip()

            if current_chunk:
                chunks.append(current_chunk)

        return chunks


text_processor = ArabicTextProcessor()
