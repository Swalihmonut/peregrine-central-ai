"""
Comprehensive Test Suite for Peregrine Arabic RAG & MAG Infrastructure
Validates:
1. Arabic exact retrieval
2. Arabic semantic retrieval
3. Diacritised / unvocalised query invariance
4. Arabic morphological root/stem variants
5. English-Arabic mixed language queries
6. Metadata category filtering
7. Source citation correctness and page references
8. Strict cross-user memory and document isolation
9. User memory update, forgetting, and purge retention
10. Anti-hallucination / No-answer fallback when evidence is missing
"""

import unittest
from knowledge_core.arabic_nlp import ArabicTextProcessor, text_processor
from knowledge_core.embeddings import DeterministicArabicEmbeddings, MockProviderEmbeddings
from knowledge_core.vector_store import VectorStore, DocumentChunk
from knowledge_core.arabic_rag import ArabicRAGEngine, SyntheticHeritageCorpus
from knowledge_core.arabic_mag import ArabicMAGEngine, PedagogicalMemoryItem


class TestArabicTextProcessor(unittest.TestCase):
    """Test Arabic normalization, stemming, and sentence splitting."""

    def test_diacritic_removal_and_normalization(self):
        text_vocalized = "الْعِلْمُ نُورٌ وَالْجَهْلُ ظَلَامٌ"
        normalized = text_processor.normalize(text_vocalized)
        self.assertEqual(normalized, "العلم نور والجهل ظلام")

    def test_alef_and_tatweel_normalization(self):
        text_tatweel = "إِعْــــرَابُ الأَفْـــــعَالِ"
        normalized = text_processor.normalize(text_tatweel)
        self.assertEqual(normalized, "اعراب الافعال")

    def test_arabic_sentence_splitting(self):
        text = "هذا باب المبتدأ والخبر. وهما ركنا الجملة الاسمية! هل يستغني أحدهما عن الآخر؟ لا يستغني."
        sentences = text_processor.split_sentences(text)
        self.assertEqual(len(sentences), 4)
        self.assertIn("هذا باب المبتدأ والخبر.", sentences[0])


class TestArabicRAGSuite(unittest.TestCase):
    """Comprehensive tests for Arabic RAG engine."""

    def setUp(self):
        self.rag = ArabicRAGEngine()

    def test_1_arabic_exact_retrieval(self):
        """Test Case 1: Exact Arabic query matches target heritage treatise."""
        query = "المسند والمسند إليه المبتدأ والمبني عليه"
        result = self.rag.retrieve(query, top_k=2)
        self.assertTrue(result["has_sufficient_evidence"])
        self.assertGreater(len(result["citations"]), 0)
        top_citation = result["citations"][0]
        self.assertEqual(top_citation["source_id"], "src_sibawayh_kitab")
        self.assertIn("سيبويه", top_citation["author"])

    def test_2_arabic_semantic_retrieval(self):
        """Test Case 2: Semantic retrieval without exact phrase matching."""
        query = "تناسب الحروف وأثرها في قوة الدلالة وضعفها مثل أكل اليابس والرطب"
        result = self.rag.retrieve(query, top_k=2)
        self.assertTrue(result["has_sufficient_evidence"])
        top_citation = result["citations"][0]
        self.assertEqual(top_citation["source_id"], "src_ibn_jinni_khasais")
        self.assertIn("ابن جني", top_citation["author"])

    def test_3_diacritised_vs_unvocalised_invariance(self):
        """Test Case 3: Fully diacritised query matches unvocalised index seamlessly."""
        query_diacritized = "الْفَاعِلُ الَّذِي كَمَرْفُوعَيْ أَتَى"
        result_vocal = self.rag.retrieve(query_diacritized, top_k=1)

        query_plain = "الفاعل الذي كمرفوعي اتى"
        result_plain = self.rag.retrieve(query_plain, top_k=1)

        self.assertTrue(result_vocal["has_sufficient_evidence"])
        self.assertTrue(result_plain["has_sufficient_evidence"])
        self.assertEqual(
            result_vocal["citations"][0]["source_id"],
            result_plain["citations"][0]["source_id"],
        )
        self.assertEqual(result_vocal["citations"][0]["source_id"], "src_ibn_malik_alfiyyah")

    def test_4_arabic_morphology_variants(self):
        """Test Case 4: Morphological stem matching bridges inflectional forms."""
        # Query uses derived active participle 'الناظم' and verb 'ينتظم'
        query = "تناسب المعاني في النظم والبيان عند الجرجاني"
        result = self.rag.retrieve(query, top_k=1)
        self.assertTrue(result["has_sufficient_evidence"])
        self.assertEqual(result["citations"][0]["source_id"], "src_jurjani_dalail")

    def test_5_english_arabic_mixed_query(self):
        """Test Case 5: Bilingual English/Arabic mixed query."""
        query = "What did Sibawayh say about المسند والمسند إليه in Arabic grammar?"
        result = self.rag.retrieve(query, top_k=2)
        self.assertTrue(result["has_sufficient_evidence"])
        self.assertEqual(result["citations"][0]["source_id"], "src_sibawayh_kitab")

    def test_6_metadata_category_filter(self):
        """Test Case 6: Category filter restricts search domain."""
        query = "البيان واللفظ والمعنى"
        # Search specifically within 'literature' category (Al-Jahiz)
        result_lit = self.rag.retrieve(query, category="literature", top_k=2)
        self.assertTrue(result_lit["has_sufficient_evidence"])
        self.assertEqual(result_lit["citations"][0]["source_id"], "src_jahiz_bayan")

        # Search specifically within 'balagha' category (Al-Jurjani)
        result_balagha = self.rag.retrieve(query, category="balagha", top_k=2)
        self.assertTrue(result_balagha["has_sufficient_evidence"])
        self.assertEqual(result_balagha["citations"][0]["source_id"], "src_jurjani_dalail")

    def test_7_source_citation_correctness(self):
        """Test Case 7: Citations preserve provenance, author, title, and page numbers."""
        query = "دلالة اللفظ أوسع من كل إشارة"
        result = self.rag.retrieve(query, top_k=1)
        self.assertTrue(result["has_sufficient_evidence"])
        cit = result["citations"][0]
        self.assertEqual(cit["source_id"], "src_jahiz_bayan")
        self.assertEqual(cit["title"], "البيان والتبيين")
        self.assertEqual(cit["page_number"], 61)
        self.assertIn("الجاحظ", cit["author"])
        self.assertTrue(len(cit["excerpt"]) > 20)

    def test_8_document_deletion(self):
        """Test Case 8: Document deletion cascade completely removes chunks."""
        # Ingest a custom research document
        custom_id = "doc_custom_tafsir_01"
        self.rag.ingest_document(
            source_id=custom_id,
            title="مقدمة في التفسير اللغوي",
            author="باحث معاصر",
            content="هذا بحث لغوي حديث حول وجوه الإعراب في التفاسير القديمة وشواهدها.",
            category="academic",
            page_number=5,
        )

        # Verify it can be retrieved
        res_before = self.rag.retrieve("وجوه الإعراب في التفاسير القديمة", category="academic")
        self.assertTrue(res_before["has_sufficient_evidence"])
        self.assertEqual(res_before["citations"][0]["source_id"], custom_id)

        # Delete the document
        deleted_count = self.rag.delete_document(custom_id)
        self.assertGreaterEqual(deleted_count, 1)

        # Verify it can no longer be retrieved
        res_after = self.rag.retrieve("وجوه الإعراب في التفاسير القديمة", category="academic")
        sources_after = [c["source_id"] for c in res_after["citations"]]
        self.assertNotIn(custom_id, sources_after)

    def test_10_no_answer_behaviour_on_missing_evidence(self):
        """Test Case 10: Missing evidence triggers explicit no-answer fallback."""
        # Query unrelated to the corpus (quantum mechanics in semiconductors)
        irrelevant_query = "ميكانيكا الكم وأشباه الموصلات في فيزياء الجوامد"
        result = self.rag.retrieve(irrelevant_query, min_similarity=0.25)
        self.assertFalse(result["has_sufficient_evidence"])
        self.assertEqual(len(result["citations"]), 0)
        self.assertIsNotNone(result["fallback_message"])
        self.assertIn("لم نجد شواهد تراثية موثقة كافية", result["fallback_message"])


class TestArabicMAGSuite(unittest.TestCase):
    """Comprehensive tests for Memory-Augmented Generation (MAG) engine."""

    def setUp(self):
        self.mag = ArabicMAGEngine()

    def test_8_cross_user_memory_isolation(self):
        """Test Case 8: Cross-user memory isolation is strictly enforced."""
        user_1 = "student_uuid_001"
        user_2 = "student_uuid_002"

        # Record pedagogical memory for User 1
        self.mag.add_approved_memory(
            user_id=user_1,
            category="grammar_weakness",
            key="weakness:al_idafa",
            summary="الطالب يواجه صعوبة في مطابقة المضاف والمضاف إليه",
        )

        # Record separate memory for User 2
        self.mag.add_approved_memory(
            user_id=user_2,
            category="pronunciation_weakness",
            key="weakness:dhad_sound",
            summary="الطالب يخلط بين حرفي الضاد والظاء في النطق الخليجي",
        )

        # User 1 should only retrieve User 1's memory
        u1_mems = self.mag.select_relevant_memories(user_1, "المضاف إليه")
        self.assertEqual(len(u1_mems), 1)
        self.assertEqual(u1_mems[0].key, "weakness:al_idafa")

        # User 2 should NOT retrieve User 1's memory
        u2_mems = self.mag.select_relevant_memories(user_2, "المضاف إليه")
        self.assertEqual(len(u2_mems), 0)

        # Cross-state security check: trying to add User 1 item to User 2 state raises error
        state_2 = self.mag.get_or_create_student_state(user_2)
        with self.assertRaises(PermissionError):
            foreign_item = PedagogicalMemoryItem(
                memory_id="illegal_mem",
                user_id=user_1,
                category="test",
                key="test",
                summary="tamper",
            )
            state_2.add_memory(foreign_item)

    def test_9_memory_update_forgetting_and_retention_purge(self):
        """Test Case 9: User can selectively forget memory or purge all stored profile data."""
        user_id = "student_uuid_privacy_test"

        mem1 = self.mag.add_approved_memory(
            user_id=user_id,
            category="dialect_preference",
            key="dialect:khaliji",
            summary="يفضل الطالب الأمثلة باللهجة الكويتية والإماراتية",
        )
        mem2 = self.mag.add_approved_memory(
            user_id=user_id,
            category="cefr_level",
            key="level:b1",
            summary="مستوى الطالب B1 في النحو الوظيفي",
        )

        # Selectively forget mem1
        forgotten = self.mag.forget_memory(user_id, mem1.memory_id)
        self.assertTrue(forgotten)

        # Confirm mem1 is gone but mem2 remains
        mems_after = self.mag.select_relevant_memories(user_id, "اللهجة")
        self.assertEqual(len(mems_after), 0)

        # Purge all user data (Right to be Forgotten)
        purged_count = self.mag.purge_user_memory(user_id)
        self.assertEqual(purged_count, 1)  # mem2 purged

        # Verify completely empty
        state = self.mag.get_or_create_student_state(user_id)
        self.assertEqual(len(state.long_term_memories), 0)

    def test_mag_context_assembly_and_token_budget(self):
        """Test 3-Tier MAG context assembly respects strict token limits."""
        user_id = "student_uuid_budget_test"

        # Layer 1: Short-term turns
        self.mag.record_turn(user_id, "user", "ما الفرق بين المبتدأ والفاعل؟")
        self.mag.record_turn(user_id, "assistant", "المبتدأ مرفوع يقع في أول الجملة الاسمية...")

        # Layer 2: Long-term approved memory
        self.mag.add_approved_memory(
            user_id=user_id,
            category="grammar_weakness",
            key="weakness:fa'il",
            summary="الطالب يخلط بين نائب الفاعل والفاعل في الأفعال المبنية للمجهول",
        )

        # Assemble MAG prompt context for new question
        context_envelope = self.mag.assemble_mag_prompt_context(
            user_id=user_id,
            query="هل يأتي الفاعل قبل الفعل؟",
            category="nahw",
            max_mag_tokens=200,
            max_rag_tokens=400,
        )

        self.assertTrue(context_envelope["has_grounded_evidence"])
        self.assertGreater(len(context_envelope["citations"]), 0)
        self.assertGreater(len(context_envelope["selected_memories"]), 0)
        self.assertEqual(len(context_envelope["short_term_history"]), 2)

        # Verify assembled system context contains MAG and RAG boundaries
        sys_context = context_envelope["system_instruction_context"]
        self.assertIn("=== الملف التعليمي التراكمي المعتمد للطالب (MAG) ===", sys_context)
        self.assertIn("=== شواهد ومصادر تراثية موثقة من قاعدة المعرفة ===", sys_context)
        self.assertIn("ابن مالك", sys_context)

        # Verify bounded length (token budget safeguard: under 2500 characters)
        self.assertLess(len(sys_context), 2500)


if __name__ == "__main__":
    unittest.main()
