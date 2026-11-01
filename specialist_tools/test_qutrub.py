#!/usr/bin/env python3
"""
Functional test for Qutrub (libqutrub Arabic verb conjugation library).
Verifies:
1. Verb instantiation and classification
2. Full paradigm conjugation
3. Pronoun-specific tense conjugation (Past, Present)
"""

import libqutrub.classverb as classverb

def test_qutrub():
    print("=== Testing Qutrub (libqutrub) ===")

    verb = "كَتَبَ"
    vc = classverb.VerbClass(verb, transitive=True, future_type="ُ")

    print(f"  Verb: {vc.verb}")
    print(f"  Type: {vc.vtype}")

    # Test individual pronoun conjugations
    test_cases = [
        ("الماضي المعلوم", "أنا", "كَتَبْتُ"),
        ("الماضي المعلوم", "نحن", "كَتَبْنَا"),
        ("المضارع المعلوم", "هو", "يَكْتُبُ"),
        ("المضارع المعلوم", "هم", "يَكْتُبُونَ")
    ]

    for tense, pronoun, expected in test_cases:
        result = vc.conjugate_tense_for_pronoun(tense, pronoun)
        print(f"  Tense: '{tense}' | Pronoun: '{pronoun}' -> Result: '{result}' (Expected: '{expected}')")
        assert result == expected, f"Mismatch: expected '{expected}', got '{result}'"

    # Test full conjugation table generation
    table_str = vc.conjugate_all_tenses()
    assert len(table_str) > 100, "Conjugation table string is empty or incomplete"
    print("  Full conjugation table generated successfully.")

    print("Qutrub: ALL TESTS PASSED SUCCESSFULLY.\n")

if __name__ == "__main__":
    test_qutrub()
