#!/usr/bin/env python3
"""
Functional test for Mishkal Arabic Diacritizer.
Verifies:
1. Automatic diacritization (tashkeel)
2. Comparison with unvocalized input
"""

import mishkal.tashkeel as tashkeel

def test_mishkal():
    print("=== Testing Mishkal Diacritizer ===")

    tashkeeler = tashkeel.TashkeelClass()
    text = "شرب الطفل الحليب في الصباح"
    diacritized = tashkeeler.tashkeel(text)

    print(f"  Input text:        '{text}'")
    print(f"  Diacritized output: '{diacritized}'")

    assert len(diacritized) > len(text), "Output text should contain added diacritical marks"
    # Verify diacritics are present
    harakat = set("ًٌٍَُِّْ")
    found_harakat = any(ch in harakat for ch in diacritized)
    assert found_harakat, "No harakat found in Mishkal output"

    print("Mishkal: ALL TESTS PASSED SUCCESSFULLY.\n")

if __name__ == "__main__":
    test_mishkal()
