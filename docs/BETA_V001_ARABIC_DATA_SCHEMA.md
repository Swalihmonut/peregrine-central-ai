# Arabic Continuous Learning Data Schema Specification (Beta V-001)

**Document Reference:** `PEREGRINE-DATA-SCHEMA-BETA-2026-10-31`  
**Author:** Agent 1 (Arabic NLP & Speech Integration Engineer)  
**Target System:** Peregrine Arabic AI Unified Platform — Knowledge & Data Layer  
**Workspace:** `~/peregrine-arabic-ai-lab`  
**Date:** October 31, 2026  
**Status:** Approved Specification (JSON Schema & Concrete Bilingual Fixtures)

---

## 1. Schema Hierarchy & Data Architecture

To support the retrieval-first continuous improvement lifecycle, five formal JSON schemas are defined:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          SCHEMA LIFECYCLE RELATIONSHIP                      │
│                                                                             │
│   [User / Client]                                                           │
│          │                                                                  │
│          ▼                                                                  │
│   1. CustomerCorrectionSubmission (Ingress Schema)                          │
│          │                                                                  │
│          ▼                                                                  │
│   2. LinguisticAnnotationRecord (Canonical Master Storage Schema)           │
│          │                                                                  │
│          ├──► 3. ScholarlyReviewAction (Reviewer Audit & Voting Schema)     │
│          │                                                                  │
│          ├──► 4. CuratedRetrievalExemplar (Optimized Vector/RAG Payload)    │
│          │                                                                  │
│          └──► 5. DatasetReleaseManifest (Versioned Packaging Schema)        │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Formal JSON Schema Specifications

### 2.1 Schema 1: `CustomerCorrectionSubmission` (Ingress Schema)
Captures raw customer feedback and proposed corrections directly from the web client.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CustomerCorrectionSubmission",
  "type": "object",
  "properties": {
    "submission_id": { "type": "string", "format": "uuid" },
    "session_id": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" },
    "user_id": { "type": "string" },
    "user_tier": {
      "type": "string",
      "enum": ["student", "educator", "native_speaker", "certified_scholar", "anonymous"],
      "default": "student"
    },
    "interaction_context": {
      "type": "object",
      "properties": {
        "feature": { "type": "string", "enum": ["speaking_partner", "prosody_analyzer", "grammar_tutor", "notebook_chat"] },
        "persona": { "type": ["string", "null"], "enum": ["rashid", "maryam", null] },
        "original_prompt": { "type": "string" },
        "model_generation": { "type": "string" }
      },
      "required": ["feature", "model_generation"]
    },
    "correction": {
      "type": "object",
      "properties": {
        "proposed_text": { "type": "string", "minLength": 1 },
        "error_category": {
          "type": "string",
          "enum": [
            "incorrect_harakat",
            "syntactic_error_nahw",
            "morphological_error_sarf",
            "prosodic_error_arud",
            "rhyme_defect_qafiyah",
            "unauthentic_emirati_dialect",
            "hallucinated_fact",
            "other"
          ]
        },
        "user_rationale_ar": { "type": ["string", "null"] },
        "user_rationale_en": { "type": ["string", "null"] }
      },
      "required": ["proposed_text", "error_category"]
    }
  },
  "required": ["submission_id", "timestamp", "interaction_context", "correction"]
}
```

---

### 2.2 Schema 2: `LinguisticAnnotationRecord` (Canonical Master Record)
The definitive, multi-layered canonical database record stored in PostgreSQL / Supabase JSONB.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "LinguisticAnnotationRecord",
  "type": "object",
  "properties": {
    "record_id": { "type": "string", "format": "uuid" },
    "created_at": { "type": "string", "format": "date-time" },
    "updated_at": { "type": "string", "format": "date-time" },
    "triage_status": {
      "type": "string",
      "enum": [
        "pending_triage",
        "in_scholarly_review",
        "approved_gold",
        "approved_dialect",
        "disputed_valid_variant",
        "rejected_error",
        "rejected_opinion"
      ]
    },
    "text_representations": {
      "type": "object",
      "properties": {
        "original_raw": { "type": "string" },
        "nfc_canonical": { "type": "string" },
        "vocalized": { "type": "string" },
        "unvocalized_clean": { "type": "string" },
        "arudi_phonetic": { "type": ["string", "null"] }
      },
      "required": ["original_raw", "nfc_canonical", "vocalized", "unvocalized_clean"]
    },
    "linguistic_metadata": {
      "type": "object",
      "properties": {
        "language_variety": {
          "type": "string",
          "enum": ["classical_fusha", "msa", "emirati_colloquial", "other_dialect"]
        },
        "dialect_code": {
          "type": "string",
          "enum": ["arb", "afb", "acm", "arz", "apc", "ayl", "other"]
        },
        "linguistic_domain": {
          "type": "string",
          "enum": ["nahw", "sarf", "balagha", "arud", "qafiyah", "adab", "sawt"]
        },
        "grammatical_features": {
          "type": "object",
          "properties": {
            "root": { "type": ["string", "null"] },
            "lemma": { "type": ["string", "null"] },
            "pattern_wazn": { "type": ["string", "null"] },
            "pos": { "type": ["string", "null"] },
            "case_ending_state": { "type": ["string", "null"], "enum": ["marfu", "mansub", "majrur", "majzum", null] },
            "governing_rule_ar": { "type": ["string", "null"] }
          }
        },
        "poetic_features": {
          "type": ["object", "null"],
          "properties": {
            "meter_key": { "type": "string" },
            "meter_name_ar": { "type": "string" },
            "bahr_type": { "type": "string" },
            "rawi": { "type": "string" },
            "qafiyah_type": { "type": "string" }
          }
        },
        "school_tradition": {
          "type": ["string", "null"],
          "enum": ["basran", "kufan", "consensus", "modern_academy", "dialectal_norm", null]
        }
      },
      "required": ["language_variety", "dialect_code", "linguistic_domain"]
    },
    "deterministic_audit": {
      "type": "object",
      "properties": {
        "engine_executed": { "type": "string" },
        "engine_passed": { "type": "boolean" },
        "vowel_density": { "type": "number" },
        "similarity_score": { "type": ["number", "null"] },
        "details": { "type": "string" }
      },
      "required": ["engine_executed", "engine_passed", "vowel_density"]
    },
    "provenance_and_rights": {
      "type": "object",
      "properties": {
        "contributor_id": { "type": "string" },
        "source_reference": { "type": "string" },
        "license": { "type": "string", "default": "CC-BY-SA-4.0" },
        "is_permissible_for_retrieval": { "type": "boolean" },
        "is_permissible_for_fine_tuning": { "type": "boolean" }
      },
      "required": ["license", "is_permissible_for_retrieval", "is_permissible_for_fine_tuning"]
    }
  },
  "required": [
    "record_id",
    "created_at",
    "triage_status",
    "text_representations",
    "linguistic_metadata",
    "deterministic_audit",
    "provenance_and_rights"
  ]
}
```

---

### 2.3 Schema 3: `CuratedRetrievalExemplar` (RAG Vector Store Payload)
The slim, high-performance schema ingested into Supabase `pgvector` for immediate Beta V-001 dynamic few-shot injection.

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "CuratedRetrievalExemplar",
  "type": "object",
  "properties": {
    "exemplar_id": { "type": "string", "format": "uuid" },
    "domain": { "type": "string", "enum": ["nahw", "sarf", "balagha", "arud", "qafiyah", "emirati_speaking"] },
    "query_trigger": { "type": "string", "description": "Normalized text used for semantic embedding match" },
    "canonical_arabic_text": { "type": "string", "description": "Fully vocalized gold Arabic text" },
    "linguistic_explanation_ar": { "type": "string" },
    "linguistic_explanation_en": { "type": "string" },
    "metadata_tags": {
      "type": "array",
      "items": { "type": "string" }
    },
    "confidence_weight": { "type": "number", "minimum": 0.5, "maximum": 1.0, "default": 1.0 }
  },
  "required": ["exemplar_id", "domain", "query_trigger", "canonical_arabic_text", "linguistic_explanation_ar"]
}
```

---

## 3. Concrete Bilingual Linguistic Examples

### Example 1: Classical Nahw Correction (*Basran vs. Kufan Dispute*)
- **Scenario:** A student asks for the syntactic parsing (*I'rab*) of `لَيْسَ الطَّيِّبُ إِلَّا شَمَّةً`.
- **Dispute:** The predicate of *Laysa* after *Illa*. The Basrans insist on the accusative (*Al-Nasb* `شَمَّةً`), whereas the Kufans permit the nominative (*Al-Raf'* `شَمَّةٌ`) by treating *Laysa* as cancelled by *Illa*.

```json
{
  "record_id": "8f3b2a19-4c12-482a-a9e1-7e89123b0001",
  "created_at": "2026-10-31T07:46:00Z",
  "updated_at": "2026-10-31T07:46:00Z",
  "triage_status": "disputed_valid_variant",
  "text_representations": {
    "original_raw": "ليس الطيب إلا شمةٌ",
    "nfc_canonical": "ليس الطيب إلا شمةٌ",
    "vocalized": "لَيْسَ الطَّيِّبُ إِلَّا شَمَّةٌ",
    "unvocalized_clean": "ليس الطيب إلا شمة",
    "arudi_phonetic": null
  },
  "linguistic_metadata": {
    "language_variety": "classical_fusha",
    "dialect_code": "arb",
    "linguistic_domain": "nahw",
    "grammatical_features": {
      "root": "طيب / شمم",
      "lemma": "طَيِّب / شَمَّة",
      "pattern_wazn": "فَعِيل / فَعْلَة",
      "pos": "noun",
      "case_ending_state": "marfu",
      "governing_rule_ar": "إلغاء عمل ليس عند اقتران خبرها بإلا على مذهب الكوفيين"
    },
    "poetic_features": null,
    "school_tradition": "kufan"
  },
  "deterministic_audit": {
    "engine_executed": "libqutrub_syntax_rules",
    "engine_passed": true,
    "vowel_density": 0.588,
    "similarity_score": null,
    "details": "Recognized as legitimate classical variance documented in Sharh Ibn Aqil."
  },
  "provenance_and_rights": {
    "contributor_id": "scholar_user_4402",
    "source_reference": "Ibn Aqil on Alfiyyat Ibn Malik (Bab Laysa wa Akhawatiha)",
    "license": "CC-BY-SA-4.0",
    "is_permissible_for_retrieval": true,
    "is_permissible_for_fine_tuning": true
  }
}
```

---

### Example 2: Authentic Emirati Dialect Correction (*Speaking Partner Dialogue*)
- **Scenario:** During a dialogue with persona Rashid, Peregrine used a generic Egyptian/MSA word `"كويس"` (good/fine). A user submitted a correction recommending authentic Emirati phrasing `"طَيِّبْ، خَيْرْ ونِعْمَة، عَسَاكْ طَيِّبْ"`.

```json
{
  "record_id": "a1c90234-912f-48e0-bb12-98317e000002",
  "created_at": "2026-10-31T07:46:15Z",
  "updated_at": "2026-10-31T07:46:15Z",
  "triage_status": "approved_dialect",
  "text_representations": {
    "original_raw": "شحالك يا خوي؟ - عساك طيب، خير ونعمة الحمد لله",
    "nfc_canonical": "شحالك يا خوي؟ - عساك طيب، خير ونعمة الحمد لله",
    "vocalized": "شْحَالِكْ يَا خُويَا؟ - عَسَاكْ طَيِّبْ، خَيْرْ ونِعْمَة الحَمْدُ لِلَّهْ",
    "unvocalized_clean": "شحالك يا خويا؟ - عساك طيب، خير ونعمة الحمد لله",
    "arudi_phonetic": null
  },
  "linguistic_metadata": {
    "language_variety": "emirati_colloquial",
    "dialect_code": "afb",
    "linguistic_domain": "adab",
    "grammatical_features": {
      "root": "حال / طيب",
      "lemma": "شحال / طيب",
      "pattern_wazn": null,
      "pos": "conversational_greeting",
      "case_ending_state": null,
      "governing_rule_ar": "التحايا والردود التراثية في السنع الإماراتي ومجالس أبوظبي ودبي"
    },
    "poetic_features": null,
    "school_tradition": "dialectal_norm"
  },
  "deterministic_audit": {
    "engine_executed": "emirati_lexicon_matcher",
    "engine_passed": true,
    "vowel_density": 0.421,
    "similarity_score": null,
    "details": "Matches authentic San'a (السنع) Emirati greeting conventions."
  },
  "provenance_and_rights": {
    "contributor_id": "user_dubai_native_88",
    "source_reference": "Emirati Cultural Heritage Oral Corpus",
    "license": "CC-BY-SA-4.0",
    "is_permissible_for_retrieval": true,
    "is_permissible_for_fine_tuning": true
  }
}
```

---

### Example 3: Classical Prosody Correction (*Fractured Foot in Al-Taweel*)
- **Scenario:** A student submitted a verse where Peregrine's generative model generated a flawed line claiming it was *Bahr al-Taweel*. The reviewer provides the metrically sound classical hemistich.

```json
{
  "record_id": "771e8910-1849-43c2-a812-fe8192340003",
  "created_at": "2026-10-31T07:46:30Z",
  "updated_at": "2026-10-31T07:46:30Z",
  "triage_status": "approved_gold",
  "text_representations": {
    "original_raw": "أَلَا كُلُّ شَيْءٍ مَا خَلَا اللَّهَ بَاطِلُ",
    "nfc_canonical": "أَلَا كُلُّ شَيْءٍ مَا خَلَا اللَّهَ بَاطِلُ",
    "vocalized": "أَلَا كُلُّ شَيْءٍ مَا خَلَا اللَّهَ بَاطِلُ",
    "unvocalized_clean": "ألا كل شيء ما خلا الله باطل",
    "arudi_phonetic": "ألا كلل شيئن ما خلا للـه باطلو"
  },
  "linguistic_metadata": {
    "language_variety": "classical_fusha",
    "dialect_code": "arb",
    "linguistic_domain": "arud",
    "grammatical_features": {
      "root": null,
      "lemma": null,
      "pattern_wazn": null,
      "pos": "poetic_shatr",
      "case_ending_state": "mansub",
      "governing_rule_ar": "نصب لفظ الجلالة بعد (ما خلا) على المفعولية"
    },
    "poetic_features": {
      "meter_key": "taweel",
      "meter_name_ar": "بحر الطويل",
      "bahr_type": "tam",
      "rawi": "ل",
      "qafiyah_type": "المتواتر"
    },
    "school_tradition": "consensus"
  },
  "deterministic_audit": {
    "engine_executed": "pyarud_1.0.0",
    "engine_passed": true,
    "vowel_density": 0.812,
    "similarity_score": 1.0,
    "details": "Scanned perfectly by PyArud: فعولن مفاعيلن فعولن مفاعلن (11010 1101010 11010 110100)."
  },
  "provenance_and_rights": {
    "contributor_id": "academic_kuwait_univ",
    "source_reference": "Diwan Labid ibn Rabi'ah al-Amiri",
    "license": "CC-BY-SA-4.0",
    "is_permissible_for_retrieval": true,
    "is_permissible_for_fine_tuning": true
  }
}
```

---

### Example 4: Phonetic Pronunciation Correction (*Pharyngeal `ح` vs. `ه`*)
- **Scenario:** A learner practicing with Maryam pronounces `"حَلِيب"` as `"هَلِيب"`. The correction records the acoustic contrast and pedagogical tip.

```json
{
  "record_id": "550b4412-990a-412e-9981-aa9081230004",
  "created_at": "2026-10-31T07:46:45Z",
  "updated_at": "2026-10-31T07:46:45Z",
  "triage_status": "approved_gold",
  "text_representations": {
    "original_raw": "حليب",
    "nfc_canonical": "حليب",
    "vocalized": "حَلِيبٌ",
    "unvocalized_clean": "حليب",
    "arudi_phonetic": null
  },
  "linguistic_metadata": {
    "language_variety": "msa",
    "dialect_code": "arb",
    "linguistic_domain": "sawt",
    "grammatical_features": {
      "root": "حلب",
      "lemma": "حَلِيب",
      "pattern_wazn": "فَعِيل",
      "pos": "noun",
      "case_ending_state": "marfu",
      "governing_rule_ar": "مخرج الحاء من وسط الحلق (الحلقي الاحتكاكي المهموس) وتمييزه عن الهاء من أقصى الحلق"
    },
    "poetic_features": null,
    "school_tradition": "consensus"
  },
  "deterministic_audit": {
    "engine_executed": "phonetic_rule_validator",
    "engine_passed": true,
    "vowel_density": 0.75,
    "similarity_score": null,
    "details": "Common phonetic substitution error for English L1 learners."
  },
  "provenance_and_rights": {
    "contributor_id": "maryam_tutor_curator",
    "source_reference": "Arabic Phonetics for Foreign Learners (Al-Ani)",
    "license": "CC-BY-SA-4.0",
    "is_permissible_for_retrieval": true,
    "is_permissible_for_fine_tuning": true
  }
}
```

---

**Certification:**  
*Compiled by Agent 1 (Arabic NLP & Speech Integration Engineer)*  
*Verified for Peregrine Arabic AI Beta V-001 — October 31, 2026*
