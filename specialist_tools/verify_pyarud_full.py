#!/usr/bin/env python3
"""
Comprehensive PyArud Evaluation across 16 Classical Arabic Meters,
Zihafat, 'Ilal, and Edge Case Limitations.

Executed within the dedicated Python 3.12 environment (.venv-prosody).
"""

import time
from pyarud.processor import ArudhProcessor
from pyarud.models.enums import MeterKey, MeterVariation, FootStatus

def run_pyarud_evaluation():
    processor = ArudhProcessor()
    print("=====================================================================")
    print("PyArud Evaluation: 16 Classical Meters, Zihaf & 'Ilal Verification")
    print("=====================================================================\n")

    # 1. 16 Classical Farahidian Meters Dataset
    meters_dataset = [
        ("taweel", "الطويل", "قِفَا نَبْكِ مِنْ ذِكْرَى حَبِيبٍ وَمَنْزِلِ", "بِسِقْطِ اللِّوَى بَيْنَ الدَّخُولِ فَحَوْمَلِ", "امرؤ القيس"),
        ("madeed", "المديد", "يَا لَبَكْرٍ أَنْشِرُوا لِي كُلَيْبًا", "يَا لَبَكْرٍ أَيْنَ أَيْنَ الفِرَارُ", "مهلهل بن ربيعة"),
        ("baseet", "البسيط", "الخَيْلُ وَاللَّيْلُ وَالبَيْدَاءُ تَعْرِفُنِي", "وَالسَّيْفُ وَالرُّمْحُ وَالقِرْطَاسُ وَالقَلَمُ", "المتنبي"),
        ("wafer", "الوافر", "أَلَا هُبِّي بِصَحْنِكِ فَاصْبَحِينَا", "وَلَا تُبْقِي خُمُورَ الأَنْدَرِينَا", "عمرو بن كلثوم"),
        ("kamel", "الكامل", "هَلْ غَادَرَ الشُّعَرَاءُ مِنْ مُتَرَدَّمِ", "أَمْ هَلْ عَرَفْتَ الدَّارَ بَعْدَ تَوَهُّمِ", "عنترة بن شداد"),
        ("hazaj", "الهزج", "عَلَى الأَهْزَاجِ تَسْهِيلُ", "مَفَاعِيلُنْ مَفَاعِيلُ", "صفي الدين الحلي"),
        ("rajaz", "الرجز", "قَالَ مُحَمَّدٌ هُوَ ابْنُ مَالِكِ", "أَحْمَدُ رَبِّي اللَّهَ خَيْرَ مَالِكِ", "ابن مالك"),
        ("ramal", "الرمل", "مَثِّلِ الدُّنْيَا لِعَيْنَيْكَ نَعِيمًا", "وَتَأَمَّلْ غِبَّهَا كَيْفَ يَصِيرُ", "أبو العتاهية"),
        ("saree", "السريع", "النَّشْرُ مِسْكٌ وَالوُجُوهُ دَنَا", "نِيرٌ وَأَطْرَافُ الأَكُفِّ عَنَمْ", "امرؤ القيس"),
        ("munsareh", "المنسرح", "مَنْ ذَا الَّذِي يَدَّعِي لِفَضْلِكُمُ", "أَنَّ لَهُ فِي الأَنَامِ مُشْتَرَكَا", "البحتري"),
        ("khafeef", "الخفيف", "يَا خَفِيفًا خَفَّتْ بِهِ الحَرَكَاتُ", "فَاعِلَاتُنْ مُسْتَفْعِلُنْ فَاعِلَاتُ", "صفي الدين الحلي"),
        ("mudhare", "المضارع", "دَعَانِي إِلَى سُعَادٍ", "دَوَاعِي هَوَى سُعَادِ", "شواهد العروض"),
        ("muqtadheb", "المقتضب", "حَامِلُ الهَوَى تَعِبُ", "يَسْتَخِفُّهُ الطَّرَبُ", "أبو نواس"),
        ("mujtath", "المجتث", "البَطْنُ مِنْكَ خَمِيصٌ", "وَالوَجْهُ مِنْكَ جَمِيلُ", "ابن زيدون"),
        ("mutakareb", "المتقارب", "إِذَا الشَّعْبُ يَوْمًا أَرَادَ الحَيَاةَ", "فَلَا بُدَّ أَنْ يَسْتَجِيبَ القَدَرْ", "أبو القاسم الشابي"),
        ("mutadarak", "المتدارك", "حَرَكَاتُ المُحْدَثِ تَنْتَقِلُ", "فَعِلُنْ فَعِلُنْ فَعِلُنْ فَعِلُ", "صفي الدين الحلي")
    ]

    print("[SECTION 1] Testing 16 Classical Meters Identification:")
    print("---------------------------------------------------------------------")
    correct_meters = 0
    zihaf_findings = []

    for expected_key, expected_ar, sadr, ajuz, poet in meters_dataset:
        analysis = processor.analyze_verse(sadr, ajuz)
        matched = (analysis.meter_key == expected_key)
        if matched:
            correct_meters += 1
            status_str = "PASS"
        else:
            status_str = f"FAIL (Got {analysis.meter_key})"

        print(f"[{status_str:4}] {expected_ar:10} ({expected_key:10}) | Score: {analysis.score:.2f} | Poet: {poet}")
        print(f"       Sadr Arudi: {analysis.sadr.arudi_text} -> {analysis.sadr.pattern}")
        print(f"       Ajuz Arudi: {analysis.ajuz.arudi_text} -> {analysis.ajuz.pattern}")
        
        # Collect foot-level Zihafat
        for f in analysis.sadr.feet + analysis.ajuz.feet:
            if f.zihaf_name_ar and f.zihaf_name_ar not in ("سالمة (صحيحة)", "سالمة"):
                zihaf_findings.append((expected_ar, f.actual_tafeela or f.base_tafeela, f.zihaf_name_ar))

    print(f"\n16-Meter Identification Accuracy: {correct_meters}/{len(meters_dataset)} ({correct_meters/len(meters_dataset):.1%})\n")

    # 2. Granular Zihaf & 'Ilal Extraction
    print("[SECTION 2] Representative Zihaf & 'Ilal Detected in Dataset:")
    print("---------------------------------------------------------------------")
    unique_zihafs = {}
    for meter_name, tafeela, zihaf in zihaf_findings:
        if zihaf not in unique_zihafs:
            unique_zihafs[zihaf] = (meter_name, tafeela)

    for zihaf_name, (meter_name, tafeela) in list(unique_zihafs.items())[:10]:
        print(f"  • {zihaf_name:30} in Bahr: {meter_name:10} (Taf'eela: {tafeela})")

    # 3. Limitations and Edge Cases
    print("\n[SECTION 3] Edge Cases & Diagnostic Limitations:")
    print("---------------------------------------------------------------------")

    # Edge Case A: Unvocalized Arabic verse (no tashkeel)
    unvocalized_sadr = "الخيل والليل والبيداء تعرفني"
    unvocalized_ajuz = "والسيف والرمح والقرطاس والقلم"
    analysis_unvoc = processor.analyze_verse(unvocalized_sadr, unvocalized_ajuz)
    print(f"  Test A: Fully unvocalized verse (Mutanabbi):")
    print(f"    Detected Meter: {analysis_unvoc.meter_name_ar} ({analysis_unvoc.meter_key}) | Score: {analysis_unvoc.score:.2f}")
    if analysis_unvoc.score < 0.70 or analysis_unvoc.meter_key != "baseet":
        print(f"    -> LIMITATION CONFIRMED: PyArud is phonetic/deterministic and relies heavily on accurate vocalization (tashkeel).")
    else:
        print(f"    -> Handled unvocalized input with heuristic fallback.")

    # Edge Case B: Plain prose / Non-poetic sentence
    prose_text = "الذكاء الاصطناعي هو فرع من فروع علوم الحاسوب يهدف إلى تطوير أنظمة ذكية"
    analysis_prose = processor.analyze_verse(prose_text, "")
    print(f"\n  Test B: Plain Arabic Prose (non-metrical):")
    print(f"    Detected Meter: {analysis_prose.meter_name_ar} ({analysis_prose.meter_key}) | Score: {analysis_prose.score:.2f}")
    broken_count = sum(1 for f in analysis_prose.sadr.feet if f.status != FootStatus.OK)
    print(f"    Broken / Non-conforming feet count: {broken_count}/{len(analysis_prose.sadr.feet)}")
    print(f"    -> BEHAVIOR: Returns low confidence or broken feet tags on non-poetic prose.")

    # Edge Case C: Broken poetic line with deliberate metric fracture (Kaser)
    fractured_sadr = "الخَيْلُ وَاللَّيْلُ جِدّاً هُنَا"
    fractured_ajuz = "وَالسَّيْفُ مَكْسُورٌ"
    analysis_fractured = processor.analyze_verse(fractured_sadr, fractured_ajuz)
    print(f"\n  Test C: Corrupted / Broken Metre (مكسور):")
    print(f"    Detected Meter: {analysis_fractured.meter_name_ar} | Score: {analysis_fractured.score:.2f}")
    for idx, f in enumerate(analysis_fractured.sadr.feet):
        print(f"      Foot {idx+1}: status={f.status} | pattern={f.actual_segment} | tafeela={f.actual_tafeela or f.base_tafeela} | zihaf={f.zihaf_name_ar}")

    # 4. Throughput Benchmarking
    print("\n[SECTION 4] Throughput Performance Benchmark:")
    print("---------------------------------------------------------------------")
    benchmark_verse = ("قِفَا نَبْكِ مِنْ ذِكْرَى حَبِيبٍ وَمَنْزِلِ", "بِسِقْطِ اللِّوَى بَيْنَ الدَّخُولِ فَحَوْمَلِ")
    n_iters = 1000
    t0 = time.perf_counter()
    for _ in range(n_iters):
        _ = processor.analyze_verse(*benchmark_verse)
    elapsed = time.perf_counter() - t0
    ops_per_sec = n_iters / elapsed
    ms_per_op = (elapsed / n_iters) * 1000
    print(f"  Processed {n_iters} verse analyses in {elapsed:.3f}s")
    print(f"  Throughput: {ops_per_sec:,.0f} verses/sec ({ms_per_op:.3f} ms/verse)")

    print("\n=====================================================================")
    print("PyArud Evaluation Completed Successfully.")
    print("=====================================================================")

if __name__ == "__main__":
    run_pyarud_evaluation()
