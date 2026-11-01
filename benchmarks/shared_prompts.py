#!/usr/bin/env python3
"""Canonical Shared Prompt Configuration for Arabic AI Benchmark Suites.

Author: Benchmark Infrastructure and Evaluation Reliability Engineer
Workspace: ~/peregrine-arabic-ai-lab
Version: 2.0.0
"""

from __future__ import annotations

from typing import Dict, List, Optional


# Canonical classical Arabic system instruction used identically by all runners.
# Harmonized to guarantee 100% character-for-character equivalence between Qwen and Jais.
CANONICAL_BENCHMARK_SYSTEM_PROMPT = (
    "أنت باحث لغوي وأكاديمي متخصص في علوم اللغة العربية وآدابها. "
    "أجب عن السؤال بدقة علمية رصينة ومباشرة، واذكر القواعد والشواهد والمصطلحات التراثية بدقة، "
    "وتجنب اللحن والهلوسة."
)


def build_chat_messages(
    prompt: str,
    system_prompt: Optional[str] = None,
) -> List[Dict[str, str]]:
    """Construct standard OpenAI/ChatML messages list.

    Guarantees that both Ollama and MLX/OpenAI endpoints receive the exact
    same structured message sequence:
    1. system message (if provided)
    2. user message
    """
    sys_content = system_prompt if system_prompt is not None else CANONICAL_BENCHMARK_SYSTEM_PROMPT
    messages = []
    if sys_content and sys_content.strip():
        messages.append({"role": "system", "content": sys_content.strip()})
    messages.append({"role": "user", "content": prompt.strip()})
    return messages
