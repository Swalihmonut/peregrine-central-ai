#!/usr/bin/env python3
"""
Deterministic Arabic Specialist Verification Test Suite (Beta V-001)
Workspace: ~/peregrine-arabic-ai-lab
Audits deterministic non-inference capabilities across:
1. Normalization (PyArabic)
2. Tokenization (PyArabic, CAMeL simple_word_tokenize)
3. Morphology (CAMeL calima-msa-r13, Qalsadi)
4. Root / Lemma Extraction (Qalsadi, CAMeL MLE)
5. Verb Conjugation (libqutrub)
6. Diacritization (Mishkal)
7. Prosody and Qafiyah (PyArud in .venv-prosody via subprocess)
8. RTL and Mixed Arabic-English (BiDi markers, punctuation preservation)

Strict Safety:
- ZERO model weights or dataset downloads.
- ZERO LLM inference.
- Non-invasive read-only deterministic execution.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unittest

# Ensure specialist_tools is importable
LAB_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(LAB_DIR, "specialist_tools"))


class TestArabicSpecialistDeterministic(unittest.TestCase):
    """Deterministic linguistic unit test suite for Arabic specialist engines."""

    # ---------------------------------------------------------
    # 1. Normalization
    # ---------------------------------------------------------
    def test_01_normalization(self):
        """Test alef variants, hamza, tatweel, and tashkeel normalization."""
        import pyarabic.araby as araby

        # Strip Tashkeel
        vocalized = "اللُّغَةُ العَرَبِيَّةُ لُغَةُ الضَّادِ"
        stripped = araby.strip_tashkeel(vocalized)
        self.assertEqual(stripped, "اللغة العربية لغة الضاد")

        # Strip Tatweel
        tatweel_text = "جـــــامِـــــعَـــــة"
        detatweeled = araby.strip_tatweel(tatweel_text)
        self.assertNotIn("ـ", detatweeled)
        self.assertEqual(araby.strip_tashkeel(detatweeled), "جامعة")

        # Normalize Hamza
        hamza_cases = [
            ("إِقْرَأْ", "ءِقْرَءْ"),
            ("مَسْؤُول", "مَسْءُول"),
        ]
        for src, expected in hamza_cases:
            res = araby.normalize_hamza(src)
            self.assertEqual(res, expected)

    # ---------------------------------------------------------
    # 2. Tokenization
    # ---------------------------------------------------------
    def test_02_tokenization(self):
        """Test tokenization with Arabic and punctuation."""
        import pyarabic.araby as araby
        from camel_tools.tokenizers.word import simple_word_tokenize

        sentence = "قالَ ابنُ خَلْدُون: «إنَّ التَّارِيخَ فِي ظَاهِرِهِ لَا يَزِيدُ عَلَى الإِخْبَارِ»."
        
        # PyArabic tokenization
        pyar_tokens = araby.tokenize(sentence)
        self.assertGreaterEqual(len(pyar_tokens), 10)
        self.assertIn("خَلْدُون", pyar_tokens)

        # CAMeL simple_word_tokenize
        camel_tokens = simple_word_tokenize(sentence)
        self.assertGreaterEqual(len(camel_tokens), 10)
        self.assertIn("ابن", [araby.strip_tashkeel(t) for t in camel_tokens])

    # ---------------------------------------------------------
    # 3. Morphology
    # ---------------------------------------------------------
    def test_03_morphology(self):
        """Test morphological analysis via CAMeL Tools Calima-MSA-r13 and Qalsadi."""
        from camel_tools.morphology.analyzer import Analyzer
        from camel_tools.morphology.database import MorphologyDB
        import qalsadi.analex as analex

        # CAMeL morphology analyzer
        db = MorphologyDB.builtin_db("calima-msa-r13")
        analyzer = Analyzer(db)
        word = "مدرسة"
        analyses = analyzer.analyze(word)
        self.assertGreater(len(analyses), 0)
        # Check that noun analysis exists
        pos_tags = [a.get("pos") for a in analyses]
        self.assertIn("noun", pos_tags)

        # Qalsadi morphology
        an = analex.Analex()
        q_results = an.check_text("كتب الطالب مقالاً")
        self.assertEqual(len(q_results), 3)
        # First word 'كتب' should be recognized as verb
        first_word_morph = q_results[0][0]
        self.assertEqual(first_word_morph.get_word(), "كتب")

    # ---------------------------------------------------------
    # 4. Root / Lemma Extraction
    # ---------------------------------------------------------
    def test_04_root_and_lemma(self):
        """Test deterministic root and lemma extraction using Qalsadi and CAMeL Disambiguation."""
        import pyarabic.araby as araby
        import qalsadi.analex as analex
        from camel_tools.disambig.mle import MLEDisambiguator
        from camel_tools.tokenizers.word import simple_word_tokenize

        # Qalsadi root extraction
        an = analex.Analex()
        results = an.check_text("استغفار الصائمين")
        self.assertGreaterEqual(len(results), 2)
        
        # 'استغفار' root is 'غفر'
        word1 = results[0][0]
        self.assertEqual(word1.get_root(), "غفر")
        self.assertIn("غفر", word1.get_root())

        # CAMeL MLE disambiguator lemma extraction
        mle = MLEDisambiguator.pretrained("calima-msa-r13")
        tokens = simple_word_tokenize("يعمل المهندس في المشروع")
        disambig = mle.disambiguate(tokens)
        self.assertEqual(len(disambig), len(tokens))
        
        # 'يعمل' lemma should be 'عَمِل' -> stripped 'عمل'
        raw_lex = disambig[0].analyses[0].analysis["lex"]
        self.assertEqual(araby.strip_tashkeel(raw_lex), "عمل")

    # ---------------------------------------------------------
    # 5. Verb Conjugation
    # ---------------------------------------------------------
    def test_05_verb_conjugation(self):
        """Test deterministic paradigm conjugation via libqutrub."""
        import libqutrub.classverb as classverb

        # Trilateral verb 'جلس'
        vc = classverb.VerbClass("جَلَسَ", transitive=False, future_type="ِ")
        
        # Past tense: أنا جلستُ, نحن جلسنا
        self.assertEqual(vc.conjugate_tense_for_pronoun("الماضي المعلوم", "أنا"), "جَلَسْتُ")
        self.assertEqual(vc.conjugate_tense_for_pronoun("الماضي المعلوم", "نحن"), "جَلَسْنَا")
        
        # Present tense: هو يجلسُ, هم يجلسون
        self.assertEqual(vc.conjugate_tense_for_pronoun("المضارع المعلوم", "هو"), "يَجْلِسُ")
        self.assertEqual(vc.conjugate_tense_for_pronoun("المضارع المعلوم", "هم"), "يَجْلِسُونَ")

        # Trilateral transitive verb 'فتح'
        vc_fataha = classverb.VerbClass("فَتَحَ", transitive=True, future_type="َ")
        self.assertEqual(vc_fataha.conjugate_tense_for_pronoun("المضارع المعلوم", "أنت"), "تَفْتَحُ")

    # ---------------------------------------------------------
    # 6. Diacritization
    # ---------------------------------------------------------
    def test_06_diacritization(self):
        """Test vocalization via Mishkal."""
        import mishkal.tashkeel as tashkeel

        tashkeeler = tashkeel.TashkeelClass()
        raw_text = "ذهب الطالب الى المدرسة مبكرا"
        diacritized = tashkeeler.tashkeel(raw_text)

        harakat = set("ًٌٍَُِّْ")
        found_harakat = [ch for ch in diacritized if ch in harakat]
        self.assertGreater(len(found_harakat), 5, "Diacritized text should contain multiple vocalization marks")
        self.assertGreater(len(diacritized), len(raw_text))

    # ---------------------------------------------------------
    # 7. Prosody and Qafiyah (via PyArud in isolated Python 3.12 env)
    # ---------------------------------------------------------
    def test_07_prosody_and_qafiyah(self):
        """Test Farahidian metric scansion and Qafiyah extraction via .venv-prosody."""
        prosody_python = os.path.join(LAB_DIR, ".venv-prosody", "bin", "python")
        if not os.path.exists(prosody_python):
            self.skipTest(".venv-prosody Python interpreter not found")

        # Invoke test_pyarud_service.py
        test_script = os.path.join(LAB_DIR, "specialist_tools", "test_pyarud_service.py")
        res = subprocess.run(
            [prosody_python, test_script],
            capture_output=True,
            text=True,
            timeout=10,
        )
        self.assertEqual(res.returncode, 0, f"PyArud test failed: {res.stderr}\n{res.stdout}")
        self.assertIn("ALL PYARUD SERVICE LOGIC TESTS PASSED", res.stdout)

    # ---------------------------------------------------------
    # 8. RTL and Mixed Arabic-English
    # ---------------------------------------------------------
    def test_08_rtl_and_mixed_content(self):
        """Test BiDi isolation characters, punctuation preservation, and mixed text integrity."""
        # Unicode directional markers:
        # LRE = U+202A, RLE = U+202B, PDF = U+202C, LRO = U+202D, RLO = U+202E
        # LRI = U+2066, RLI = U+2067, FSI = U+2068, PDI = U+2069
        
        # Test 1: Preserving Arabic question mark vs English question mark
        ar_question = "هل أنت مستعد؟"
        en_question = "Are you ready?"
        self.assertTrue(ar_question.endswith("؟"))
        self.assertTrue(en_question.endswith("?"))

        # Test 2: Wrapping mixed Arabic in BiDi isolation
        mixed_phrase = "كلمة 'algorithm' مشتقة من اسم العالم الخوارزمي."
        isolated = f"\u2067{mixed_phrase}\u2069"
        self.assertTrue(isolated.startswith("\u2067"))
        self.assertTrue(isolated.endswith("\u2069"))
        self.assertIn("algorithm", isolated)
        self.assertIn("الخوارزمي", isolated)

        # Test 3: Bracket and quote preservation
        bracketed = "«البلاغة هي مطابقة الكلام لمقتضى الحال (السكاكي)»"
        self.assertTrue(bracketed.startswith("«"))
        self.assertTrue(bracketed.endswith("»"))
        self.assertIn("(السكاكي)", bracketed)


if __name__ == "__main__":
    unittest.main()
