import time

from ..core.config import ASK_MORE_MAX_TURNS, OLLAMA_CODE_MODEL, OLLAMA_MODEL
from .content_reader import read_for_ask
from .folder_context import build_folder_context
from .llm_client import OllamaClient
from .prompts import (
    ASK_MORE_QUESTION,
    DEFAULT_QUESTION,
    binary_answer,
    build_ask_more_system,
    build_prompt,
    select_prompt,
)


class Explainer:
    def __init__(self, client=None):
        self.client = client or OllamaClient()

    def explain(self, record, question=None):
        started = time.perf_counter()
        question = (question or "").strip() or DEFAULT_QUESTION
        reading = read_for_ask(record["path"])
        if reading["kind"] == "binary":
            return {
                "answer": binary_answer(record),
                "model": "none (metadata only)",
                "elapsed_ms": int((time.perf_counter() - started) * 1000),
                "truncated": False,
                "binary": True,
            }
        model = OLLAMA_CODE_MODEL if record.get("category") == "code" else OLLAMA_MODEL
        system = select_prompt(record.get("category", "other"), record.get("extension", ""))
        prompt = build_prompt(record, reading["content"], question, reading["truncated"])
        answer = self.client.generate(prompt, system=system, model=model)
        return {
            "answer": answer,
            "model": model,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "truncated": reading["truncated"],
            "binary": False,
        }

    def explain_more(self, record, history=None, question=None):
        started = time.perf_counter()
        reading = read_for_ask(record["path"])
        context = build_folder_context(record["path"])
        model = OLLAMA_CODE_MODEL if record.get("category") == "code" else OLLAMA_MODEL
        system = build_ask_more_system(record, reading["content"], reading["truncated"], context)
        messages = []
        for turn in (history or [])[-ASK_MORE_MAX_TURNS:]:
            if not isinstance(turn, dict) or turn.get("role") not in ("user", "assistant"):
                continue
            content = (turn.get("content") or "").strip()
            if content:
                messages.append({"role": turn["role"], "content": content})
        question = (question or "").strip() or ASK_MORE_QUESTION
        messages.append({"role": "user", "content": question})
        answer = self.client.chat(messages, system=system, model=model)
        return {
            "answer": answer,
            "model": model,
            "elapsed_ms": int((time.perf_counter() - started) * 1000),
            "truncated": reading["truncated"],
            "binary": reading["kind"] == "binary",
            "context_files": len(context["siblings"]) + context["hidden"],
            "excerpt_files": list(context["excerpts"].keys()),
        }
