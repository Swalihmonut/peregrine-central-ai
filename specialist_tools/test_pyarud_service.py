#!/usr/bin/env python3
"""
Unit test for PyArud Prosody Service logic and contracts (Beta V-001).
Verifies:
1. Engine initialization
2. Canonical verse scansion (Al-Taweel & Al-Baseet)
3. Non-poetic prose rejection (dual-gate filter)
4. Diagnostic vowel density calculation
5. Qafiyah and Rawiy extraction
"""

import sys
from pathlib import Path

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from pyarud_service import PyArudEngine

def test_pyarud_service():
    print("=== Testing PyArud Prosody Service Logic ===")
    engine = PyArudEngine()

    # 1. Classical Verse: Al-Taweel (Imru' al-Qais)
    sadr_taweel = "قِفَا نَبْكِ مِنْ ذِكْرَى حَبِيبٍ وَمَنْزِلِ"
    ajuz_taweel = "بِسِقْطِ اللِّوَى بَيْنَ الدَّخُولِ فَحَوْمَلِ"
    res1 = engine.analyze(sadr=sadr_taweel, ajuz=ajuz_taweel)

    assert res1["status"] == "success", "Expected status success"
    data1 = res1["data"]
    assert data1["is_poetic"] is True, "Expected is_poetic to be True for Al-Taweel"
    assert data1["meter_key"] == "taweel", f"Expected 'taweel', got '{data1['meter_key']}'"
    assert data1["broken_feet_count"] == 0, f"Expected 0 broken feet, got {data1['broken_feet_count']}"
    assert data1["qafiyah"] is not None, "Expected Qafiyah data"
    assert data1["qafiyah"]["rawi"] == "ل", f"Expected Rawi 'ل', got '{data1['qafiyah']['rawi']}'"
    print(f"  [1/4] Classical Verse (Al-Taweel): PASS (Meter: {data1['meter_key']}, Rawi: {data1['qafiyah']['rawi']}, Latency: {res1['execution_time_ms']} ms)")

    # 2. Classical Verse: Al-Baseet (Al-Mutanabbi)
    sadr_baseet = "الخَيْلُ وَاللَّيْلُ وَالبَيْدَاءُ تَعْرِفُنِي"
    ajuz_baseet = "وَالسَّيْفُ وَالرُّمْحُ وَالقِرْطَاسُ وَالقَلَمُ"
    res2 = engine.analyze(sadr=sadr_baseet, ajuz=ajuz_baseet)
    data2 = res2["data"]
    assert data2["is_poetic"] is True, "Expected is_poetic to be True for Al-Baseet"
    assert data2["meter_key"] == "baseet", f"Expected 'baseet', got '{data2['meter_key']}'"
    assert data2["qafiyah"]["rawi"] == "م", f"Expected Rawi 'م', got '{data2['qafiyah']['rawi']}'"
    print(f"  [2/4] Classical Verse (Al-Baseet): PASS (Meter: {data2['meter_key']}, Rawi: {data2['qafiyah']['rawi']})")

    # 3. Non-Poetic Prose Rejection
    prose_sample = "الذكاء الاصطناعي هو فرع من فروع علوم الحاسوب يهدف إلى تطوير أنظمة ذكية"
    res3 = engine.analyze(sadr=prose_sample)
    data3 = res3["data"]
    assert data3["is_poetic"] is False, "Expected prose to be rejected (is_poetic: False)"
    assert data3["broken_feet_count"] > 0, "Expected broken feet in prose"
    assert data3["rejection_reason"] == "PROSE_OR_FRACTURED_METER"
    print(f"  [3/4] Prose Rejection Filter: PASS (is_poetic: False, broken_feet: {data3['broken_feet_count']}, reason: {data3['rejection_reason']})")

    # 4. Diagnostic Vowel Density
    density_vocalized = engine.calculate_vowel_density(sadr_taweel)
    density_unvocalized = engine.calculate_vowel_density("قف نبك من ذكرى حبيب ومنزل")
    assert density_vocalized > 0.40, f"Expected vocalized density > 0.40, got {density_vocalized}"
    assert density_unvocalized < 0.10, f"Expected unvocalized density < 0.10, got {density_unvocalized}"
    print(f"  [4/4] Vowel Density Calculation: PASS (Vocalized: {density_vocalized}, Unvocalized: {density_unvocalized})")

    print("\nALL PYARUD SERVICE LOGIC TESTS PASSED SUCCESSFULLY.")

if __name__ == "__main__":
    test_pyarud_service()
