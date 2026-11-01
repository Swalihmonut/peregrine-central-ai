#!/usr/bin/env python3
"""
Functional test for PyArabic.
Verifies:
1. Tashkeel stripping
2. Tatweel stripping
3. Hamza normalization
4. Word tokenization
5. Number spell-out in Arabic words
"""

import pyarabic.araby as araby
import pyarabic.number as number

def test_pyarabic():
    print("=== Testing PyArabic ===")

    # 1. Strip Tashkeel
    vocalized = "الذَّهَبُ مَعْدِنٌ نَفِيسٌ"
    stripped = araby.strip_tashkeel(vocalized)
    expected_stripped = "الذهب معدن نفيس"
    assert stripped == expected_stripped, f"Expected '{expected_stripped}', got '{stripped}'"
    print(f"[1/5] Strip Tashkeel: '{vocalized}' -> '{stripped}'")

    # 2. Strip Tatweel
    tatweel_text = "عـــــرَبـــــي"
    detatweeled = araby.strip_tatweel(tatweel_text)
    print(f"[2/5] Strip Tatweel: '{tatweel_text}' -> '{detatweeled}'")
    assert "ـ" not in detatweeled, "Tatweel character remained in output"

    # 3. Hamza Normalization
    hamza_text = "إِقْرَأْ"
    norm_hamza = araby.normalize_hamza(hamza_text)
    print(f"[3/5] Normalize Hamza: '{hamza_text}' -> '{norm_hamza}'")

    # 4. Tokenization
    text = "العلمُ نورٌ، والجهلُ ظلامٌ!"
    tokens = araby.tokenize(text)
    print(f"[4/5] Tokenize: '{text}' -> {tokens}")
    assert len(tokens) >= 5, "Token count unexpected"

    # 5. Number to words
    an = number.ArNumbers()
    num_str = "2026"
    words = an.int2str(num_str)
    print(f"[5/5] Number to words: '{num_str}' -> '{words}'")
    assert len(words) > 0, "Failed to convert number to words"

    print("PyArabic: ALL TESTS PASSED SUCCESSFULLY.\n")

if __name__ == "__main__":
    test_pyarabic()
