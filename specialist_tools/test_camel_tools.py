#!/usr/bin/env python3
"""
Functional test for CAMeL Tools with the light dataset.
Verifies:
1. MorphologyDB and Morphological Analyzer
2. Maximum Likelihood Estimation (MLE) Disambiguator
3. Dialect Identifier (city26)
"""

import sys
from camel_tools.morphology.database import MorphologyDB
from camel_tools.morphology.analyzer import Analyzer
from camel_tools.disambig.mle import MLEDisambiguator
from camel_tools.dialectid import DialectIdentifier
from camel_tools.tokenizers.word import simple_word_tokenize

def test_camel_tools():
    print("=== Testing CAMeL Tools ===")

    # 1. Morphology
    print("[1/3] Testing Morphology Analyzer (calima-msa-r13)...")
    db = MorphologyDB.builtin_db("calima-msa-r13")
    analyzer = Analyzer(db)
    word = "كتاب"
    analyses = analyzer.analyze(word)
    assert len(analyses) > 0, f"Expected analyses for '{word}', got none"
    print(f"  Analyses count for '{word}': {len(analyses)}")
    print(f"  Sample analysis gloss: {analyses[0]['gloss']}")

    # 2. MLE Disambiguation
    print("[2/3] Testing MLE Disambiguator (calima-msa-r13)...")
    mle = MLEDisambiguator.pretrained("calima-msa-r13")
    sentence = "ذهب الولد إلى المدرسة"
    tokens = simple_word_tokenize(sentence)
    disambig = mle.disambiguate(tokens)
    assert len(disambig) == len(tokens), "Token count mismatch in disambiguation"
    print(f"  Sentence: {sentence}")
    for d in disambig:
        top_analysis = d.analyses[0].analysis
        print(f"    Word: {d.word:10} | Lemma: {top_analysis['lex']:10} | POS: {top_analysis['pos']}")

    # 3. Dialect Identification
    print("[3/3] Testing Dialect Identification (city26)...")
    did = DialectIdentifier.pretrained()
    sentences = [
        "عامل إيه يا باشا؟ وحشتني جداً",
        "شو أخبارك يا زلمة؟ كيف صحتك؟"
    ]
    predictions = did.predict(sentences)
    assert len(predictions) == 2, "Dialect prediction count mismatch"
    print(f"  Text 1: '{sentences[0]}' -> Top Dialect: {predictions[0].top}")
    print(f"  Text 2: '{sentences[1]}' -> Top Dialect: {predictions[1].top}")

    print("CAMeL Tools: ALL TESTS PASSED SUCCESSFULLY.\n")

if __name__ == "__main__":
    test_camel_tools()
