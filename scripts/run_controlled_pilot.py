#!/usr/bin/env python3
"""
Controlled Model Inference Pilot Runner (Beta V-001 Owner Approved)
Workspace: ~/peregrine-arabic-ai-lab

Executes strictly sequential, non-concurrent inference for:
1. Ollama Qwen3 4B
2. Ollama Mistral 7.2B
3. MLX Jais 3.7B 4-bit
4. Hosted Provider: Google Gemini (gemini-3.8-flash)

Safety Enforcements:
- Strictly sequential execution (never concurrent).
- Explicit model unloading between local runs.
- Max tokens = 512 per prompt.
- Disk space floor >= 15 GB checked before and after each run.
- Internal reasoning (<think>) captured and segregated from final answer.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import urllib.error

QUESTIONS = [
    {
        "id": "NAHW",
        "category": "Syntax (Nahw)",
        "prompt": "ما إعراب كلمة الطالب في الجملة: كتب الطالب الدرس؟",
        "ground_truth": "الطالب: فاعل مرفوع وعلامة رفعه الضمة الظاهرة على آخره."
    },
    {
        "id": "SARF",
        "category": "Morphology (Sarf)",
        "prompt": "صرّف الفعل كتب في الماضي والمضارع والأمر مع ضمير أنتَ.",
        "ground_truth": "الماضي: كَتَبْتَ | المضارع: تَكْتُبُ | الأمر: اكْتُبْ (اُكْتُبْ)"
    },
    {
        "id": "BALAGHA",
        "category": "Rhetoric (Balagha)",
        "prompt": "اشرح الصورة البلاغية في قولنا: العلم نور.",
        "ground_truth": "تشبيه بليغ: حُذفت منه أداة التشبيه ووجه الشبه، وبقي المشبه (العلم) والمشبه به (نور)."
    }
]

RESULTS_DIR = "/Users/muhammedswaliht/peregrine-arabic-ai-lab/results"
os.makedirs(RESULTS_DIR, exist_ok=True)


def check_disk_space() -> float:
    total, used, free = shutil.disk_usage("/")
    free_gb = free / (1024 ** 3)
    if free_gb < 15.0:
        raise RuntimeError(f"FATAL: Available disk space ({free_gb:.2f} GB) breached the 15 GB floor!")
    return free_gb


def unload_ollama_model(model_name: str):
    """Force Ollama to unload model from unified memory by sending keep_alive: 0."""
    try:
        url = "http://127.0.0.1:11434/api/generate"
        payload = json.dumps({"model": model_name, "keep_alive": 0}).encode("utf-8")
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=5) as r:
            pass
        print(f"Unloaded {model_name} from Ollama memory.")
    except Exception as e:
        print(f"Notice during {model_name} unload: {e}")


def run_ollama_pilot(model_name: str) -> list[dict]:
    print(f"\n=======================================================")
    print(f"  STARTING SEQUENTIAL PILOT: {model_name} (Ollama)")
    print(f"=======================================================")
    check_disk_space()
    results = []

    for q in QUESTIONS:
        print(f"\n[{q['id']}] Prompt: {q['prompt']}")
        payload = {
            "model": model_name,
            "messages": [{"role": "user", "content": q["prompt"]}],
            "stream": True,
            "options": {
                "temperature": 0.2,
                "num_predict": 512
            }
        }
        req = urllib.request.Request(
            "http://127.0.0.1:11434/api/chat",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        start_time = time.perf_counter()
        ttft = None
        thinking_parts = []
        content_parts = []
        done_chunk = {}

        try:
            with urllib.request.urlopen(req, timeout=120) as resp:
                for line in resp:
                    if not line.strip():
                        continue
                    chunk = json.loads(line.decode("utf-8"))
                    msg = chunk.get("message", {})
                    th = msg.get("thinking")
                    co = msg.get("content")

                    if ttft is None and (th or co):
                        ttft = time.perf_counter() - start_time

                    if th:
                        thinking_parts.append(th)
                    if co:
                        content_parts.append(co)

                    if chunk.get("done"):
                        done_chunk = chunk

            latency_s = time.perf_counter() - start_time
            prompt_tokens = done_chunk.get("prompt_eval_count", 0)
            eval_tokens = done_chunk.get("eval_count", 0)
            eval_duration_s = (done_chunk.get("eval_duration", 1) or 1) / 1e9
            throughput = eval_tokens / eval_duration_s if eval_duration_s > 0 else 0

            thinking_text = "".join(thinking_parts).strip()
            final_content = "".join(content_parts).strip()
            done_reason = done_chunk.get("done_reason", "stop")

            res_entry = {
                "provider": "ollama",
                "model": model_name,
                "question_id": q["id"],
                "category": q["category"],
                "prompt": q["prompt"],
                "ground_truth": q["ground_truth"],
                "status": "success" if final_content else "reasoning_only_empty_content",
                "done_reason": done_reason,
                "final_answer": final_content,
                "reasoning_trace": thinking_text,
                "prompt_tokens": prompt_tokens,
                "completion_tokens": eval_tokens,
                "total_tokens": prompt_tokens + eval_tokens,
                "ttft_s": round(ttft or 0, 3),
                "total_latency_s": round(latency_s, 3),
                "throughput_tps": round(throughput, 2)
            }
            results.append(res_entry)
            print(f"  Status: {res_entry['status']} | TTFT: {res_entry['ttft_s']}s | Latency: {res_entry['total_latency_s']}s | Tokens: {res_entry['completion_tokens']} | Tps: {res_entry['throughput_tps']}")
            print(f"  Final Answer Preview: {final_content[:120]}...")

        except Exception as e:
            res_entry = {
                "provider": "ollama",
                "model": model_name,
                "question_id": q["id"],
                "category": q["category"],
                "prompt": q["prompt"],
                "ground_truth": q["ground_truth"],
                "status": "error",
                "error": str(e),
                "final_answer": "",
                "reasoning_trace": ""
            }
            results.append(res_entry)
            print(f"  ERROR: {e}")

    # Explicitly unload model
    unload_ollama_model(model_name)
    time.sleep(2)
    return results


def run_jais_mlx_pilot() -> list[dict]:
    print(f"\n=======================================================")
    print(f"  STARTING SEQUENTIAL PILOT: IFM/Jais-3-3.7B-MLX-4bit (MLX)")
    print(f"=======================================================")
    check_disk_space()

    import mlx.core as mx
    from mlx_lm import load, generate

    model_id = "IFM/Jais-3-3.7B-MLX-4bit"
    print(f"Loading {model_id} via Apple MLX...")
    t0 = time.perf_counter()
    model, tokenizer = load(model_id, trust_remote_code=True)
    load_time_s = time.perf_counter() - t0
    print(f"Jais loaded in {load_time_s:.2f}s")

    results = []
    for q in QUESTIONS:
        print(f"\n[{q['id']}] Prompt: {q['prompt']}")
        messages = [{"role": "user", "content": q["prompt"]}]
        if hasattr(tokenizer, "apply_chat_template") and tokenizer.chat_template:
            formatted_prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            formatted_prompt = q["prompt"]

        t_gen_start = time.perf_counter()
        raw_response = generate(
            model,
            tokenizer,
            prompt=formatted_prompt,
            max_tokens=512,
            verbose=False
        )
        t_gen_end = time.perf_counter()
        gen_duration_s = t_gen_end - t_gen_start

        # Delimit and segregate thinking if present
        clean_content = raw_response
        thinking_text = ""
        if "</ifm|think>" in raw_response:
            parts = raw_response.split("</ifm|think>")
            thinking_text = parts[0].replace("<ifm|think>", "").strip()
            clean_content = parts[-1].strip()
        elif "<ifm|think>" in raw_response:
            parts = raw_response.split("<ifm|think>")
            clean_content = parts[-1].strip()

        # Token count estimates
        prompt_tokens = len(tokenizer.encode(formatted_prompt))
        completion_tokens = len(tokenizer.encode(raw_response))
        throughput = completion_tokens / gen_duration_s if gen_duration_s > 0 else 0
        peak_gpu_mem_gb = mx.metal.get_peak_memory() / (1024 ** 3)

        res_entry = {
            "provider": "mlx",
            "model": model_id,
            "question_id": q["id"],
            "category": q["category"],
            "prompt": q["prompt"],
            "ground_truth": q["ground_truth"],
            "status": "success",
            "done_reason": "stop" if completion_tokens < 512 else "length",
            "final_answer": clean_content,
            "reasoning_trace": thinking_text,
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
            "load_time_s": round(load_time_s, 2),
            "total_latency_s": round(gen_duration_s, 3),
            "throughput_tps": round(throughput, 2),
            "peak_metal_memory_gb": round(peak_gpu_mem_gb, 2)
        }
        results.append(res_entry)
        print(f"  Status: {res_entry['status']} | Latency: {res_entry['total_latency_s']}s | Tokens: {res_entry['completion_tokens']} | Tps: {res_entry['throughput_tps']} | Peak Metal: {res_entry['peak_metal_memory_gb']} GB")
        print(f"  Final Answer Preview: {clean_content[:120]}...")

    # Clear references to unload
    del model
    del tokenizer
    mx.metal.clear_cache()
    print("Unloaded Jais MLX from Metal memory.")
    time.sleep(2)
    return results


def run_gemini_hosted_pilot() -> list[dict]:
    print(f"\n=======================================================")
    print(f"  STARTING BOUNDED PILOT: Google Gemini (gemini-3.8-flash)")
    print(f"=======================================================")
    check_disk_space()

    # Read API Key
    api_key = ""
    env_path = "/Users/muhammedswaliht/Developer/peregrine-arabic-ai-mvp/.env.local"
    if os.path.exists(env_path):
        with open(env_path) as f:
            for line in f:
                if line.startswith("GEMINI_API_KEY="):
                    api_key = line.strip().split("=", 1)[1]

    if not api_key:
        print("ERROR: GEMINI_API_KEY not found in .env.local")
        return []

    model_name = "gemini-3.8-flash"
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={api_key}"
    results = []

    for q in QUESTIONS:
        print(f"\n[{q['id']}] Prompt: {q['prompt']}")
        payload = {
            "contents": [
                {
                    "parts": [{"text": q["prompt"]}]
                }
            ],
            "generationConfig": {
                "temperature": 0.2,
                "maxOutputTokens": 512
            }
        }

        req = urllib.request.Request(
            url,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"}
        )

        t_start = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                latency_s = time.perf_counter() - t_start
                data = json.loads(resp.read().decode("utf-8"))

                candidate = data.get("candidates", [{}])[0]
                content_part = candidate.get("content", {}).get("parts", [{}])[0]
                text_out = content_part.get("text", "").strip()
                finish_reason = candidate.get("finishReason", "STOP")

                usage = data.get("usageMetadata", {})
                prompt_tokens = usage.get("promptTokenCount", 0)
                completion_tokens = usage.get("candidatesTokenCount", 0)
                total_tokens = usage.get("totalTokenCount", prompt_tokens + completion_tokens)

                # Cost estimate ($0.15/1M input, $0.60/1M output)
                cost_usd = ((prompt_tokens / 1e6) * 0.15) + ((completion_tokens / 1e6) * 0.60)
                throughput = completion_tokens / latency_s if latency_s > 0 else 0

                res_entry = {
                    "provider": "gemini",
                    "model": model_name,
                    "question_id": q["id"],
                    "category": q["category"],
                    "prompt": q["prompt"],
                    "ground_truth": q["ground_truth"],
                    "status": "success",
                    "done_reason": finish_reason,
                    "final_answer": text_out,
                    "reasoning_trace": "",
                    "prompt_tokens": prompt_tokens,
                    "completion_tokens": completion_tokens,
                    "total_tokens": total_tokens,
                    "total_latency_s": round(latency_s, 3),
                    "throughput_tps": round(throughput, 2),
                    "cost_usd": round(cost_usd, 6)
                }
                results.append(res_entry)
                print(f"  Status: success | Latency: {res_entry['total_latency_s']}s | Tokens: {res_entry['completion_tokens']} | Cost: ${cost_usd:.6f}")
                print(f"  Final Answer Preview: {text_out[:120]}...")

        except Exception as e:
            res_entry = {
                "provider": "gemini",
                "model": model_name,
                "question_id": q["id"],
                "category": q["category"],
                "prompt": q["prompt"],
                "ground_truth": q["ground_truth"],
                "status": "error",
                "error": str(e),
                "final_answer": "",
                "reasoning_trace": ""
            }
            results.append(res_entry)
            print(f"  ERROR: {e}")

    return results


def main():
    print("================================================================")
    print("  PEREGRINE ARABIC AI — CONTROLLED MODEL INFERENCE PILOT")
    print("  Sequential Non-Concurrent Execution")
    print("================================================================")

    all_results = {}

    # 1. Pilot 1: Qwen3 4B
    all_results["qwen3_4b"] = run_ollama_pilot("qwen3:4b")

    # 2. Pilot 2: Mistral 7.2B
    all_results["mistral_7b"] = run_ollama_pilot("mistral:latest")

    # 3. Pilot 3: Jais 3.7B MLX
    all_results["jais_3_7b"] = run_jais_mlx_pilot()

    # 4. Pilot 4: Hosted Gemini
    all_results["gemini_3_8_flash"] = run_gemini_hosted_pilot()

    # Save aggregated raw results
    output_path = os.path.join(RESULTS_DIR, "controlled_pilot_beta_v001.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved raw aggregated results to {output_path}")
    check_disk_space()
    print("Disk space safety check: OK (> 15 GB free preserved).")


if __name__ == "__main__":
    main()
