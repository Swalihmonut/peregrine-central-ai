# AI Speaking Partner Architecture & Design: Rashid & Maryam (Beta V-001)

**Document Reference:** `PEREGRINE-SPEAKING-PARTNER-DESIGN-2026-10-31`  
**Author:** Agent 1 (Arabic NLP & Speech Integration Engineer)  
**Target Platform:** Peregrine Arabic AI Beta V-001  
**Source Inspection:** `https://github.com/Swalihmonut/khaliji-arabic-through-stories` (Read-Only)  
**Date:** October 31, 2026  
**Status:** Approved Architectural Specification

---

## 1. Executive Summary & Context

The Peregrine Arabic AI Speaking Partner delivers an immersive conversational practice environment for Arabic learners, anchored in authentic Gulf (*Khaliji*) and Emirati cultural contexts.

Learners engage in spoken audio dialogue with two culturally grounded AI personas:
- **Rashid (راشد):** A young Emirati professional from Abu Dhabi, warm, encouraging, conversational, skilled in Majlis hospitality, workplace etiquette, and contemporary Emirati life.
- **Maryam (مريم):** An Emirati educator and cultural specialist from Dubai/Sharjah, articulate, culturally grounded, specializing in heritage vocabulary, storytelling, and phonological precision.

This design builds upon empirical insights from the existing Reader application (`khaliji-arabic-through-stories`), extracts proven components, and replaces fragile client-side heuristics with a **clean, modular, and replaceable interface architecture**.

---

## 2. Forensic Review of the Existing Reader Implementation

A read-only inspection of the Reader codebase (`khaliji-arabic-through-stories`) revealed the current state of speech capabilities:

```
khaliji-arabic-through-stories/
├── src/lib/khalijiVoiceState.ts          # Persona config (Hamdan & Fatima) & local storage state
├── src/lib/arabicSpeech.ts               # Browser Web Speech API synthesizer & text cleaners
├── src/lib/khalijiPronunciationScorer.ts  # Levenshtein distance transcript comparison
├── tts_synthesize.py                     # edge-tts batch pipeline with phonetic regex overrides
└── src/components/KhalijiAiTutorDrawer.tsx # UI chat drawer with microphone recording
```

### Key Technical Findings from Reader
1. **TTS Personas in Reader:** Configured as `ar-AE-HamdanNeural` (male) and `ar-AE-FatimaNeural` (female) via Microsoft Edge Neural TTS. The speech quality for UAE Arabic is exceptionally high, naturalistic, and expressive.
2. **Phonetic Pronunciation Overrides (`tts_synthesize.py`):** The Reader team discovered that neural TTS engines default to strict Modern Standard Arabic (MSA) unless colloquial Gulf words are explicitly diacritized. They implemented a dictionary of phonetic overrides (e.g., `ريال` $\rightarrow$ `رَيَّالْ`, `مب` $\rightarrow$ `مُبْ`, `وايد` $\rightarrow$ `وَايِدْ`, `باجر` $\rightarrow$ `بَاجِرْ`). This insight is directly adopted into Beta V-001.
3. **Flawed Pronunciation Scoring (`khalijiPronunciationScorer.ts`):** The existing scorer uses Levenshtein edit distance between the *speech-to-text transcript* and the *expected target text*. 

---

## 3. Critical Scientific Guardrail: The ASR Scoring Fallacy

> [!CAUTION]
> **Architectural Guardrail:** We must **NEVER** pretend that speech-to-text transcription alone provides authentic phonetic pronunciation scoring.

### Why ASR Transcript Matching is Scientifically Flawed for Pronunciation Feedback:
1. **Language Model Autocorrection:** Modern ASR engines (such as Whisper or Google ASR) use deep language model decoders. When an English-speaking student pronounces a word with heavy phonetic distortion (e.g. saying `"ahlan"` with an English `h` rather than pharyngeal `ح`, or pronouncing `ق` as `k`), the language model's prior probability overrides the acoustic error and outputs the correct text (`"أهلاً"`). The student receives a misleading **100% pronunciation score** despite poor phonetics!
2. **Dialectal Penalization:** Conversely, if an advanced student pronounces an authentic Emirati dialectal sound (e.g. pronouncing `ق` as the Gulf voiced velar stop `[g]` in `"قريب"` $\rightarrow$ `"gireeb"`, or `ج` as `[y]` in `"مسجد"` $\rightarrow$ `"masyid"`), an MSA-trained ASR engine fails to recognize the word or transcribes it as a bizarre non-word. The student is penalized with a **0% score** for authentic dialect speech!
3. **Absence of Acoustic Timing:** Text transcripts contain zero acoustic duration, pitch contour, or formant frequencies. They cannot detect missing shaddah, improper syllable stress, or vowel elongation errors.

### The Beta V-001 Honest Contract
In Peregrine Beta V-001, we explicitly separate:
- **Speech Recognition Match (ASR-based):** Measuring whether the student said the intended words (lexical recall). Labeled honestly in the UI as `"Transcript Accuracy: 92%"`.
- **Phonetic Pronunciation Feedback:** Generated contextually by LLM pedagogical rubrics based on common Gulf learner phonological errors (e.g. reminding students that `ريال` is pronounced with an emphatic `r` and double `y`, `ray-yaal`). True acoustic phone alignment (e.g. Azure Pronunciation Assessment or Kaldi GOP) is deferred to future enterprise sprints.

---

## 4. Minimal Replaceable Interface Specification

To decouple Peregrine from specific speech providers (allowing zero-friction swapping between browser APIs, Whisper, Edge-TTS, ElevenLabs, or Azure), the Speaking Partner architecture exposes four decoupled async interfaces:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SPEAKING PARTNER MODULAR INTERFACE                       │
│                                                                             │
│  [User Audio Blob] ──► 1. transcribeAudio(blob, metadata)                   │
│                                     │                                       │
│                                     ▼                                       │
│                        2. evaluatePronunciation(blob, target, transcript)   │
│                                     │                                       │
│                                     ▼                                       │
│                        3. generateSpeakingFeedback(eval, history)           │
│                                     │                                       │
│                                     ▼                                       │
│  [Partner Audio]   ◄── 4. synthesizeSpeech(response_text, persona)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 4.1 Interface 1: `transcribeAudio`
Converts raw user microphone audio into Arabic text.

```typescript
export interface AudioMetadata {
  mimeType: string;         // 'audio/webm;codecs=opus' or 'audio/wav'
  sampleRate: number;       // e.g. 16000 or 44100
  durationMs: number;
  expectedDialect?: 'emirati' | 'msa' | 'general_gulf';
}

export interface TranscriptionResult {
  transcript: string;       // Normalized Arabic transcript
  rawTranscript: string;    // Unmodified ASR output
  confidence: number;       // Confidence score (0.0 to 1.0)
  detectedLanguage: string; // e.g. 'ar-AE' or 'ar'
  engine: 'whisper' | 'web-speech-api' | 'azure';
}

export async function transcribeAudio(
  audioBlob: Blob,
  metadata: AudioMetadata
): Promise<TranscriptionResult>;
```

### 4.2 Interface 2: `synthesizeSpeech`
Converts Arabic text into natural voice audio for Rashid or Maryam.

```typescript
export interface TTSOptions {
  gender: 'male' | 'female';
  persona: 'rashid' | 'maryam';
  rate?: number;            // 0.85 (learning pace) to 1.0 (natural)
  applyDialectOverrides?: boolean;
}

export interface SynthesisResult {
  audioBuffer: ArrayBuffer;
  mimeType: string;         // 'audio/mp3' or 'audio/wav'
  durationMs: number;
  engine: 'edge-tts' | 'web-speech-api' | 'elevenlabs';
}

export async function synthesizeSpeech(
  text: string,
  options: TTSOptions
): Promise<SynthesisResult>;
```

### 4.3 Interface 3: `evaluatePronunciation`
Performs an honest, multi-dimensional assessment of the spoken turn.

```typescript
export interface WordAssessment {
  expected: string;
  recognized?: string;
  isMatched: boolean;
  score: number;            // 0 to 100
  phoneticNote?: string;    // e.g. "Focus on softening the J (ج -> ي)"
}

export interface PronunciationEvaluation {
  transcriptMatchScore: number; // 0 to 100 (Lexical alignment)
  isPassing: boolean;
  words: WordAssessment[];
  pedagogicalFeedbackAr: string;
  pedagogicalFeedbackEn: string;
  isAcousticScored: boolean;     // False in Beta V-001 (ASR-based match only)
}

export async function evaluatePronunciation(
  audioBlob: Blob,
  targetText: string,
  asrTranscript?: string
): Promise<PronunciationEvaluation>;
```

### 4.4 Interface 4: `generateSpeakingFeedback`
Drives the pedagogical conversational turn by the AI persona.

```typescript
export interface PartnerTurn {
  persona: 'rashid' | 'maryam';
  replyArabicText: string;
  replyEnglishTranslation: string;
  pronunciationTip?: string;
  culturalNote?: string;
  nextPromptArabic: string;
}

export async function generateSpeakingFeedback(
  evaluation: PronunciationEvaluation,
  userTranscript: string,
  conversationHistory: Array<{ role: 'user' | 'partner'; text: string }>
): Promise<PartnerTurn>;
```

---

## 5. Persona Profiles: Rashid & Maryam

```
┌──────────────────────────────────────┐ ┌──────────────────────────────────────┐
│           RASHID (راشد)              │ │           MARYAM (مريم)              │
│                                      │ │                                      │
│ Role: Emirati Peer & Host            │ │ Role: Emirati Educator & Storyteller │
│ Region: Abu Dhabi & Dubai            │ │ Region: Dubai & Sharjah              │
│ Avatar: 👨 (Kandura & Ghutra)         │ │ Avatar: 👩 (Abaya & Shayla)          │
│ Tone: Warm, witty, conversational    │ │ Tone: Poetic, articulate, encouraging│
│ Primary Focus: Majlis hospitality,   │ │ Primary Focus: Daily family life,    │
│ business etiquette, youth slang,     │ │ heritage culture, clear phonetics,   │
│ real-world street fluency.           │ │ storytelling and proverbs.           │
│                                      │ │                                      │
│ Signature Greeting:                  │ │ Signature Greeting:                  │
│ "يَا هَلَا وَاللهْ! حَيَّاكْ فِي     │ │ "مَرْحَبَا السَّاعْ! يَا مَرْحَبَا   │
│ مَجْلِسْنَا، شْحَالِكْ يَا خُويَا؟"  │ │ السَّاعْ، نَوَّرْتْنَا يَا هَلَا!"    │
└──────────────────────────────────────┘ └──────────────────────────────────────┘
```

### Emirati Phonetic Overrides for Personas
Both personas apply the verified phonetic dictionary from Reader's `tts_synthesize.py` prior to voice generation:
- `"ريال"` $\rightarrow$ `"رَيَّالْ"` (prevents TTS pronouncing it as currency *Riyal* instead of *man*).
- `"مب"` $\rightarrow$ `"مُبْ"` (Emirati negation *mub*).
- `"وايد"` $\rightarrow$ `"وَايِدْ"` (*wayed* = very/a lot).
- `"باجر"` $\rightarrow$ `"بَاجِرْ"` (*baacher* = tomorrow).
- `"شحالك"` $\rightarrow$ `"شْحَالِكْ"` (*sh-haalik* = how are you).
- `"فديتك"` $\rightarrow$ `"فِدَيْتِكْ"` (*fdaytik* = affectionate Gulf term).

---

## 6. Browser Recording & Audio Pipeline Architecture

### Audio Ingress Pipeline
1. **User Recording:** Browser captures microphone input via `navigator.mediaDevices.getUserMedia({ audio: true })`.
2. **MediaRecorder Compression:**
   - Chrome / Firefox / Edge: Encodes to `audio/webm;codecs=opus` at 32 kbps (lightweight, ~4 KB/sec).
   - Safari (macOS/iOS): Encodes to `audio/mp4` (AAC).
3. **Client-Side Silence Trimming:** Detects voice activity (VAD) via `AudioContext` AnalyserNode; stops recording automatically after 1.5 seconds of sustained silence.
4. **Transport to Backend:** Transmitted as binary `FormData` payload to `/api/speaking/transcribe`.

---

## 7. Recommended Technology Stack for Beta V-001

To ensure zero cost and immediate launch velocity without model downloading:
1. **ASR (Speech-to-Text):** 
   - Primary: **Browser Web Speech API (`webkitSpeechRecognition`)** set to `lang: 'ar-AE'`. Instantaneous, zero server CPU cost, zero bandwidth latency.
   - Fallback (Server-side): OpenAI Whisper Cloud API or local `faster-whisper` (deferred to cloud sprint).
2. **TTS (Text-to-Speech):**
   - Primary: **Edge-TTS Pipeline** using `ar-AE-HamdanNeural` (Rashid) and `ar-AE-FatimaNeural` (Maryam). Exceptional native Gulf accent, completely free.
   - Fallback: Browser Web Speech API (`speechSynthesis`) with standard Arabic voices.
3. **Scoring Engine:**
   - Honest ASR-based lexical match score powered by Levenshtein distance, accompanied by explicit disclaimer: `"Assessment measures word recognition; phonetic scoring in active training."`

---

**Certification:**  
*Compiled by Agent 1 (Arabic NLP & Speech Integration Engineer)*  
*Verified for Peregrine Arabic AI Beta V-001 — October 31, 2026*
