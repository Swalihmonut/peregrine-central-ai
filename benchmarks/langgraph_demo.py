#!/usr/bin/env python3
"""LangGraph Multi-Agent Orchestration Demo for Arabic Philological Analysis.

Architecture: Parallel Fork-Join Execution
           ┌───────────┐
           │   START   │
           └─────┬─────┘
                 │ (fan-out / parallel)
        ┌────────┴────────┐
        ▼                 ▼
 ┌───────────────┐ ┌───────────────┐
 │ Grammar Agent │ │ Rhetoric Agent│
 └──────┬────────┘ └──────┬────────┘
        │                 │
        └────────┬────────┘ (fan-in / converge)
                 ▼
        ┌─────────────────┐
        │ Final Evaluator │
        └────────┬────────┘
                 ▼
            ┌─────────┐
            │   END   │
            └─────────┘

Agents:
1. Grammar Agent (محلل النحو والإعراب): Parses syntax and inflectional structure concurrently.
2. Rhetoric Agent (محلل البلاغة والبيان): Analyzes rhetoric, eloquence, and imagery concurrently.
3. Final Evaluator (المقوّم والجامع النهائي): Converges outputs, synthesizes analyses, and audits quality.

Default Question: حلّل قوله تعالى: إن الله غفور رحيم من حيث النحو والبلاغة.
Default Model: qwen3:4b via ChatOllama

Owner: Agent 3 (Arabic Model Benchmark and Multi-Agent Engineer)
Workspace: ~/peregrine-arabic-ai-lab
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
import operator
import os
from pathlib import Path
import sys
import time
from typing import Annotated, Any, Dict, List, Optional, TypedDict

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_ollama import ChatOllama
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph


def _merge_latencies(a: Dict[str, float], b: Dict[str, float]) -> Dict[str, float]:
    """Reducer to merge latency dictionaries from parallel branches."""
    res = dict(a)
    res.update(b)
    return res


class ArabicAnalysisState(TypedDict):
    """Shared state dictionary passed across agents in the graph."""

    verse_text: str
    grammar_analysis: str
    rhetoric_analysis: str
    evaluation_report: str
    agent_latencies: Annotated[Dict[str, float], _merge_latencies]
    metadata: Dict[str, Any]
    errors: Annotated[List[str], operator.add]
    success: bool


def create_grammar_agent(llm: Any):
    """Agent specialized in Arabic syntax (Nahw) and inflectional parsing (I'rab).

    Executes in parallel branch directly from START.
    """

    def grammar_node(state: ArabicAnalysisState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        verse = state["verse_text"]
        print("  -> [Parallel Branch 1: Grammar Agent] Parsing syntax and inflection...")

        system_instruction = (
            "أنت «خبير النحو والإعراب العربي». مهمتك تحليل النص القرآني تحليلاً نحوياً دقيقاً وشاملاً:\n"
            "1. تفكيك الجملة إلى أركانها النحوية وتحديد أدواتها والنوع التركيبي (جملة اسمية منسوخة).\n"
            "2. إعراب كل كلمة إعراباً مفصلاً مع ذكر العلامة الإعرابية وحكمها (إن، لفظ الجلالة، غفور، رحيم).\n"
            "3. بيان أوجه الإعراب في تعدد الخبر (هل 'رحيم' خبر ثانٍ، أم نعت، أم بدل؟ وما الرأي الأرجح والعلة النحوية؟).\n"
            "استخدم المصطلحات النحوية التراثية الأصيلة واحرص على الضبط العلمي الدقيق."
        )

        user_content = f"النص القرآني المراد تحليله نحوياً:\n«{verse}»"

        try:
            response = llm.invoke([
                SystemMessage(content=system_instruction),
                HumanMessage(content=user_content),
            ])
            content = response.content if hasattr(response, "content") else str(response)
            latency = time.perf_counter() - t0
            print(f"  ✓ [Grammar Agent] Completed in {latency:.2f}s")
            return {
                "grammar_analysis": content,
                "agent_latencies": {"grammar_agent": round(latency, 3)},
                "errors": [],
            }
        except Exception as e:
            latency = time.perf_counter() - t0
            err_msg = f"GrammarAgent Error: {type(e).__name__}: {str(e)}"
            print(f"  ✗ [Grammar Agent] Failed: {err_msg}")
            return {
                "grammar_analysis": "",
                "errors": [err_msg],
                "agent_latencies": {"grammar_agent": round(latency, 3)},
            }

    return grammar_node


def create_rhetoric_agent(llm: Any):
    """Agent specialized in Arabic rhetoric (Balagha: Ma'ani, Bayan, Badi').

    Executes in parallel branch directly from START.
    """

    def rhetoric_node(state: ArabicAnalysisState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        verse = state["verse_text"]
        print("  -> [Parallel Branch 2: Rhetoric Agent] Analyzing rhetorical eloquence and imagery...")

        system_instruction = (
            "أنت «خبير البلاغة والبيان العربي». مهمتك استخراج الأسرار البلاغية والجمالية للنص القرآني:\n"
            "1. أسرار علم المعاني: توكيد الجملة بـ (إنّ)، ودلالة الجملة الاسمية على الثبوت والدوام، وسر تنكير الخبرين (غفور رحيم) للتعظيم والإطلاق.\n"
            "2. أسرار علم البيان والاشتقاق: دلالة صيغتي المبالغة (فَعُول: غفور) و (فَعِيل: رحيم) وعلة الجمع بينهما وتقديم المغفرة على الرحمة (التخلية قبل التحلية ومحو الذنوب قبل الإنعام).\n"
            "3. أسرار علم البديع والتناسب: الفاصلة القرآنية وتوازن الإيقاع ورعاية الفواصل والمقاطع الصوتية.\n"
            "حلل النص بأسلوب بلاغي رصين معتمداً على المتن القرآني مباشرة."
        )

        user_content = f"النص القرآني المراد تحليله بلاغياً:\n«{verse}»"

        try:
            response = llm.invoke([
                SystemMessage(content=system_instruction),
                HumanMessage(content=user_content),
            ])
            content = response.content if hasattr(response, "content") else str(response)
            latency = time.perf_counter() - t0
            print(f"  ✓ [Rhetoric Agent] Completed in {latency:.2f}s")
            return {
                "rhetoric_analysis": content,
                "agent_latencies": {"rhetoric_agent": round(latency, 3)},
                "errors": [],
            }
        except Exception as e:
            latency = time.perf_counter() - t0
            err_msg = f"RhetoricAgent Error: {type(e).__name__}: {str(e)}"
            print(f"  ✗ [Rhetoric Agent] Failed: {err_msg}")
            return {
                "rhetoric_analysis": "",
                "errors": [err_msg],
                "agent_latencies": {"rhetoric_agent": round(latency, 3)},
            }

    return rhetoric_node


def create_evaluator_agent(llm: Any):
    """Final Evaluator that converges outputs from both parallel branches.

    Performs multi-agent synthesis, cross-verification, and generates a structured summary.
    Note: Evaluator output is an orchestration synthesis, not an empirical ground truth replacement.
    """

    def evaluator_node(state: ArabicAnalysisState) -> Dict[str, Any]:
        t0 = time.perf_counter()
        verse = state["verse_text"]
        grammar = state.get("grammar_analysis", "")
        rhetoric = state.get("rhetoric_analysis", "")

        # If both parallel branches failed to produce content
        if not grammar and not rhetoric:
            latency = time.perf_counter() - t0
            return {
                "evaluation_report": "تعذر إجراء التقييم النهائي نظراً لعدم توفر مخرجات من فرعي النحو والبلاغة المتوازيين.",
                "agent_latencies": {"evaluator_agent": round(latency, 3)},
                "success": False,
            }

        print("  -> [Converged Node: Final Evaluator] Synthesizing parallel analyses and auditing quality...")

        system_instruction = (
            "أنت «المُقوِّم اللغوي والجامع التركيبي». مهمتك تقييم ودمج مخرجات وكيل النحو ووكيل البلاغة الصادرة بالتوازي في تقرير تحليلي ختامي متكامل:\n"
            "1. المواءمة والربط بين المعطيات النحوية (الإعراب وتعدد الأخبار) والأسرار البلاغية (التوكيد والتنكير وصيغ المبالغة).\n"
            "2. تدقيق السلامة اللغوية والتأكد من خلو التحليل من التناقض أو الهلوسة العلمية.\n"
            "3. تقديم بطاقة تقييم تركيبية موجزة للمخرجات اللغوية.\n"
            "تنبيه منهجي: تقييمك يمثل تلخيصاً وفحصاً استدلالياً داخلياً ولا يغني عن الاحتكام إلى معايير الحقيقة المرجعية التراثية."
        )

        user_content = (
            f"النص الأصلي: «{verse}»\n\n"
            f"=== مخرجات فرع النحو (Grammar Branch) ===\n{grammar}\n\n"
            f"=== مخرجات فرع البلاغة (Rhetoric Branch) ===\n{rhetoric}\n\n"
            "المطلوب: تقديم التركيب النهائي والتقويم الأكاديمي الشامل."
        )

        try:
            response = llm.invoke([
                SystemMessage(content=system_instruction),
                HumanMessage(content=user_content),
            ])
            content = response.content if hasattr(response, "content") else str(response)
            latency = time.perf_counter() - t0
            print(f"  ✓ [Final Evaluator] Completed in {latency:.2f}s")
            return {
                "evaluation_report": content,
                "agent_latencies": {"evaluator_agent": round(latency, 3)},
                "success": True,
            }
        except Exception as e:
            latency = time.perf_counter() - t0
            err_msg = f"EvaluatorAgent Error: {type(e).__name__}: {str(e)}"
            print(f"  ✗ [Final Evaluator] Failed: {err_msg}")
            return {
                "evaluation_report": "",
                "errors": [err_msg],
                "agent_latencies": {"evaluator_agent": round(latency, 3)},
                "success": False,
            }

    return evaluator_node


def build_arabic_graph(llm: Any) -> Any:
    """Build and compile the parallel LangGraph workflow.

    Topology:
      START -> grammar_agent  -> final_evaluator -> END
      START -> rhetoric_agent -> final_evaluator -> END
    """
    workflow = StateGraph(ArabicAnalysisState)

    workflow.add_node("grammar_agent", create_grammar_agent(llm))
    workflow.add_node("rhetoric_agent", create_rhetoric_agent(llm))
    workflow.add_node("final_evaluator", create_evaluator_agent(llm))

    # Parallel fan-out from START
    workflow.add_edge(START, "grammar_agent")
    workflow.add_edge(START, "rhetoric_agent")

    # Parallel fan-in to final_evaluator
    workflow.add_edge("grammar_agent", "final_evaluator")
    workflow.add_edge("rhetoric_agent", "final_evaluator")

    # Convergence to END
    workflow.add_edge("final_evaluator", END)

    return workflow.compile()


def verify_graph_topology(compiled_graph: Any) -> bool:
    """Validate that the compiled graph enforces parallel branch execution."""
    edges = [(e.source, e.target) for e in compiled_graph.get_graph().edges]
    required_edges = [
        ("__start__", "grammar_agent"),
        ("__start__", "rhetoric_agent"),
        ("grammar_agent", "final_evaluator"),
        ("rhetoric_agent", "final_evaluator"),
        ("final_evaluator", "__end__"),
    ]
    for req in required_edges:
        if req not in edges:
            return False
    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="LangGraph Parallel Multi-Agent Arabic Philological Analysis Workflow"
    )
    parser.add_argument(
        "--question",
        type=str,
        default="حلّل قوله تعالى: إن الله غفور رحيم من حيث النحو والبلاغة.",
        help="Input text/verse to analyze",
    )
    parser.add_argument(
        "--model",
        type=str,
        default=os.environ.get("OLLAMA_MODEL", "qwen3:4b"),
        help="Ollama model name (default: qwen3:4b)",
    )
    parser.add_argument(
        "--endpoint",
        type=str,
        default=os.environ.get("OLLAMA_ENDPOINT", "http://127.0.0.1:11434"),
        help="Ollama server endpoint (default: http://127.0.0.1:11434)",
    )
    parser.add_argument(
        "--provider",
        type=str,
        choices=["ollama", "openai", "mlx"],
        default=os.environ.get("LLM_PROVIDER", "ollama"),
        help="LLM provider: 'ollama' or 'openai'/'mlx' (default: ollama)",
    )
    parser.add_argument(
        "--max-tokens",
        type=int,
        default=1024,
        help="Maximum generation tokens per node (default: 1024)",
    )
    parser.add_argument(
        "--temperature",
        type=float,
        default=0.2,
        help="Generation temperature",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent.parent / "results" / "langgraph",
        help="Directory to save final workflow reports",
    )
    parser.add_argument(
        "--save-result",
        action="store_true",
        help="Save result artifact when run produces genuine successful analysis",
    )
    parser.add_argument(
        "--verify-graph",
        action="store_true",
        help="Verify graph topology (parallel branches) and exit without calling LLM",
    )

    args = parser.parse_args()

    # Initialize shared model through ChatOllama or ChatOpenAI
    if args.provider in ("openai", "mlx"):
        llm = ChatOpenAI(
            base_url=args.endpoint if args.endpoint != "http://127.0.0.1:11434" else "http://localhost:8080/v1",
            api_key="not-needed",
            model=args.model if args.model != "qwen3:4b" else "IFM/Jais-3-3.7B-MLX-4bit",
            temperature=args.temperature,
            max_tokens=args.max_tokens,
        )
    else:
        llm = ChatOllama(
            base_url=args.endpoint,
            model=args.model,
            temperature=args.temperature,
            num_predict=args.max_tokens,
        )

    graph = build_arabic_graph(llm)

    if args.verify_graph:
        is_parallel = verify_graph_topology(graph)
        print("=== LangGraph Topology Verification ===")
        print("Compiled Graph Edges:")
        for edge in graph.get_graph().edges:
            print(f"  {edge.source} -> {edge.target}")
        print(f"Parallel Branch Topology Verified: {is_parallel}")
        return 0 if is_parallel else 1

    print("============================================================")
    print("LangGraph Parallel Arabic Multi-Agent Orchestration Demo")
    print(f"Architecture: Two Parallel Branches (Grammar & Rhetoric) -> Final Evaluator")
    print(f"Model: {args.model}")
    print(f"Endpoint: {args.endpoint}")
    print(f"Question: {args.question}")
    print("============================================================")

    initial_state: ArabicAnalysisState = {
        "verse_text": args.question,
        "grammar_analysis": "",
        "rhetoric_analysis": "",
        "evaluation_report": "",
        "agent_latencies": {},
        "metadata": {
            "model": args.model,
            "endpoint": args.endpoint,
            "architecture": "parallel_fork_join",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        "errors": [],
        "success": False,
    }

    t_start = time.perf_counter()
    print("\n[Executing LangGraph: START -> (grammar_agent || rhetoric_agent) -> final_evaluator -> END]")

    final_state = graph.invoke(initial_state)
    total_latency = time.perf_counter() - t_start

    print("\n============================================================")
    print("Execution Summary:")
    print(f"  Total Duration: {total_latency:.2f}s")
    print(f"  Agent Latencies: {final_state.get('agent_latencies')}")
    print(f"  Errors: {final_state.get('errors')}")
    print(f"  Success: {final_state.get('success')}")
    print("============================================================")

    if final_state.get("success"):
        print("\n--- [المخرجات النهائية للمقوم والجامع] ---")
        print(final_state.get("evaluation_report", ""))

        if args.save_result:
            args.output_dir.mkdir(parents=True, exist_ok=True)
            run_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
            res_file = args.output_dir / f"langgraph_run_{run_id}.json"
            with open(res_file, "w", encoding="utf-8") as f:
                json.dump(final_state, f, ensure_ascii=False, indent=2)
            print(f"\n[Saved genuine multi-agent execution record to: {res_file}]")
        return 0
    else:
        print("\n[Notice] Workflow did not complete successfully with genuine model outputs.")
        print("Reason: Model endpoint is unavailable or model has not finished downloading/loading.")
        print("Note: In compliance with Agent 3 rules, no fabricated records have been generated.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
