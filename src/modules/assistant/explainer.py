import time

from ..core.config import OLLAMA_CODE_MODEL, OLLAMA_MODEL
from .content_reader import read_for_ask
from .llm_client import OllamaClient
from .prompts import DEFAULT_QUESTION, binary_answer, build_prompt, select_prompt


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
