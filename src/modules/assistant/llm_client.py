import time

import requests

from ..core import config

_AVAILABILITY_TTL = 15.0


class OllamaError(Exception):
    pass


class OllamaClient:
    def __init__(self, host=None, model=None, timeout=None):
        self.host = (host or config.OLLAMA_HOST).rstrip("/")
        self.model = model or config.OLLAMA_MODEL
        self.timeout = timeout or config.ASK_TIMEOUT_SECONDS
        self.session = requests.Session()
        self._availability = None
        self._availability_at = 0.0

    def is_available(self):
        if self._availability is not None and time.time() - self._availability_at < _AVAILABILITY_TTL:
            return self._availability
        try:
            res = self.session.get(f"{self.host}/api/tags", timeout=2)
            res.raise_for_status()
            models = [m.get("name", "") for m in (res.json() or {}).get("models", [])]
            self._availability = (True, models)
        except (requests.RequestException, ValueError):
            self._availability = (False, [])
        self._availability_at = time.time()
        return self._availability

    def invalidate_availability(self):
        self._availability = None

    def generate(self, prompt, system=None, model=None):
        available, models = self.is_available()
        if not available:
            raise OllamaError("Ollama is not running - start it with `ollama serve`")
        use_model = model or self.model
        if models and not any(m == use_model or m.startswith(use_model + ":") for m in models):
            raise OllamaError(f"Model '{use_model}' is not downloaded - run `ollama pull {use_model}`")
        payload = {"model": use_model, "prompt": prompt, "stream": False}
        if system:
            payload["system"] = system
        try:
            res = self.session.post(f"{self.host}/api/generate", json=payload, timeout=self.timeout)
            res.raise_for_status()
        except requests.Timeout:
            raise OllamaError(f"Ollama timed out after {self.timeout}s - try a shorter question")
        except requests.ConnectionError:
            self.invalidate_availability()
            raise OllamaError("Ollama is not running - start it with `ollama serve`")
        except requests.HTTPError as exc:
            status = exc.response.status_code if exc.response is not None else "?"
            raise OllamaError(f"Ollama returned HTTP {status}")
        return ((res.json() or {}).get("response") or "").strip()
