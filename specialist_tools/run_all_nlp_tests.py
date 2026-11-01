#!/usr/bin/env python3
"""
Master runner for Agent 1 Arabic NLP specialist tools verification.
Executes functional tests for:
1. CAMeL Tools
2. PyArabic
3. Mishkal
4. Qutrub (libqutrub)
5. Qalsadi
"""

import sys
import time

def run_suite():
    tests = [
        ("CAMeL Tools (with light dataset)", "test_camel_tools", "test_camel_tools"),
        ("PyArabic", "test_pyarabic", "test_pyarabic"),
        ("Mishkal", "test_mishkal", "test_mishkal"),
        ("Qutrub (libqutrub)", "test_qutrub", "test_qutrub"),
        ("Qalsadi", "test_qalsadi", "test_qalsadi"),
    ]

    print("==================================================")
    print("Agent 1: Arabic NLP Tools Functional Test Suite")
    print("==================================================\n")

    passed = 0
    failed = 0
    results = []

    for name, module_name, func_name in tests:
        t0 = time.time()
        print(f"Running test for {name}...")
        try:
            mod = __import__(module_name)
            func = getattr(mod, func_name)
            func()
            elapsed = time.time() - t0
            passed += 1
            results.append((name, "PASS", f"{elapsed:.2f}s"))
        except Exception as e:
            elapsed = time.time() - t0
            failed += 1
            print(f"FAILED: {e}\n")
            results.append((name, f"FAIL: {e}", f"{elapsed:.2f}s"))

    print("==================================================")
    print("Functional Test Summary:")
    print("==================================================")
    for name, status, duration in results:
        print(f"  {name:35} : {status:10} ({duration})")
    print("==================================================")
    print(f"Total: {len(tests)} | Passed: {passed} | Failed: {failed}")

    if failed > 0:
        sys.exit(1)

if __name__ == "__main__":
    run_suite()
