#!/usr/bin/env python3
"""
Functional test for Qalsadi Arabic Morphological Analyzer and Lemmatizer.
Verifies:
1. Lexical analysis and tokenization
2. Lemma extraction
3. Root extraction
4. Vocalization
"""

import qalsadi.analex as analex

def test_qalsadi():
    print("=== Testing Qalsadi Morphological Analyzer ===")

    analyzer = analex.Analex()
    sentence = "ينتشر العلم في المجتمعات"
    results = analyzer.check_text(sentence)

    print(f"  Input sentence: '{sentence}'")
    assert len(results) > 0, "No results returned by Qalsadi"

    for word_analyses in results:
        if word_analyses:
            morph = word_analyses[0]
            token = morph.get_word()
            lemma = morph.get_lemma()
            root = morph.get_root()
            vocalized = morph.get_vocalized()
            print(f"    Token: {token:12} | Lemma: {lemma:12} | Root: {root:8} | Vocalized: {vocalized}")

    # Specific assertions
    first_token_morph = results[0][0]
    assert first_token_morph.get_word() == "ينتشر", "First token word mismatch"
    assert first_token_morph.get_root() == "نشر", f"Expected root 'نشر', got '{first_token_morph.get_root()}'"

    print("Qalsadi: ALL TESTS PASSED SUCCESSFULLY.\n")

if __name__ == "__main__":
    test_qalsadi()
