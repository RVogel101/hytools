"""HTTP client for local LLM inference with retry logic.

Supports Ollama (/api/chat) and any OpenAI-compatible endpoint
(/v1/chat/completions).  Includes exponential-backoff retries with
jitter, a quick benchmark method, and availability checks.
"""

from __future__ import annotations

import logging
import random
import time
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    """All knobs for the local LLM connection."""

    base_url: str = "http://localhost:11434"
    model: str = "llama3.1:8b"
    api_type: str = "ollama"          # "ollama" | "openai"
    temperature: float = 0.8
    max_tokens: int = 512
    timeout: int = 120                # per-request timeout (seconds)
    max_retries: int = 5
    base_delay: float = 1.0           # initial backoff (seconds)
    max_delay: float = 60.0           # ceiling for backoff
    jitter: float = 0.25              # ± fraction applied to delay


class LLMClient:
    """Thin wrapper around a local LLM server with retry + backoff."""

    def __init__(self, config: LLMConfig | None = None) -> None:
        self.config = config or LLMConfig()
        self._session = requests.Session()
        self.avg_tokens_per_sec: float | None = None

    # ------------------------------------------------------------------
    # public API
    # ------------------------------------------------------------------

    def generate(self, prompt: str, system: str = "") -> dict:
        """Send a chat-completion request with automatic retries.

        Returns
        -------
        dict with keys ``text``, ``tokens_generated``, ``duration_seconds``.
        """
        last_exc: BaseException | None = None
        for attempt in range(self.config.max_retries + 1):
            try:
                return self._call(prompt, system)
            except requests.ConnectionError as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    self._wait(attempt, exc)
            except requests.Timeout as exc:
                last_exc = exc
                if attempt < self.config.max_retries:
                    self._wait(attempt, exc)
            except requests.HTTPError as exc:
                last_exc = exc
                code = exc.response.status_code if exc.response is not None else 0
                if code in {429, 500, 502, 503} and attempt < self.config.max_retries:
                    self._wait(attempt, exc)
                else:
                    raise
        raise RuntimeError(f"LLM request failed after {self.config.max_retries + 1} attempts") from last_exc

    def is_available(self) -> bool:
        """Return True if the LLM server responds to a health-check."""
        try:
            if self.config.api_type == "ollama":
                r = self._session.get(f"{self.config.base_url}/api/tags", timeout=5)
            else:
                r = self._session.get(f"{self.config.base_url}/v1/models", timeout=5)
            return r.status_code == 200
        except Exception:
            return False

    def benchmark(self, n_samples: int = 3) -> dict:
        """Run *n_samples* short generations and measure throughput.

        Returns
        -------
        dict with ``avg_tokens_per_sec`` and ``avg_seconds_per_request``.
        If the server is unreachable, returns conservative fallback values.
        """
        prompt = "Write a short paragraph about the importance of preserving minority languages."
        durations: list[float] = []
        tokens: list[int] = []

        for i in range(n_samples):
            try:
                r = self.generate(prompt, system="You are a helpful assistant.")
                durations.append(r["duration_seconds"])
                tokens.append(r["tokens_generated"])
            except Exception as exc:
                logger.warning("Benchmark sample %d/%d failed: %s", i + 1, n_samples, exc)

        if not durations:
            # Conservative fallback (assume slow CPU inference).
            return {"avg_tokens_per_sec": 8.0, "avg_seconds_per_request": 20.0, "samples": 0}

        avg_dur = sum(durations) / len(durations)
        avg_tok = sum(tokens) / len(tokens)
        tps = avg_tok / avg_dur if avg_dur > 0 else 8.0
        self.avg_tokens_per_sec = tps
        return {"avg_tokens_per_sec": round(tps, 1), "avg_seconds_per_request": round(avg_dur, 2), "samples": len(durations)}

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    def _call(self, prompt: str, system: str) -> dict:
        if self.config.api_type == "ollama":
            return self._call_ollama(prompt, system)
        return self._call_openai(prompt, system)

    def _call_ollama(self, prompt: str, system: str) -> dict:
        url = f"{self.config.base_url}/api/chat"
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": self.config.temperature,
                "num_predict": self.config.max_tokens,
            },
        }
        t0 = time.monotonic()
        resp = self._session.post(url, json=payload, timeout=self.config.timeout)
        resp.raise_for_status()
        elapsed = time.monotonic() - t0

        data = resp.json()
        text = data.get("message", {}).get("content", "")
        tok_count = data.get("eval_count", max(len(text.split()), 1))
        if tok_count and elapsed > 0:
            self.avg_tokens_per_sec = tok_count / elapsed
        return {"text": text, "tokens_generated": tok_count, "duration_seconds": elapsed}

    def _call_openai(self, prompt: str, system: str) -> dict:
        url = f"{self.config.base_url}/v1/chat/completions"
        messages: list[dict] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        payload = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "max_tokens": self.config.max_tokens,
        }
        t0 = time.monotonic()
        resp = self._session.post(url, json=payload, timeout=self.config.timeout)
        resp.raise_for_status()
        elapsed = time.monotonic() - t0

        data = resp.json()
        text = data["choices"][0]["message"]["content"]
        tok_count = data.get("usage", {}).get("completion_tokens", max(len(text.split()), 1))
        if tok_count and elapsed > 0:
            self.avg_tokens_per_sec = tok_count / elapsed
        return {"text": text, "tokens_generated": tok_count, "duration_seconds": elapsed}

    def _backoff_delay(self, attempt: int) -> float:
        delay = min(self.config.base_delay * (2 ** attempt), self.config.max_delay)
        jitter = delay * self.config.jitter
        return delay + random.uniform(-jitter, jitter)

    def _wait(self, attempt: int, exc: BaseException) -> None:
        delay = self._backoff_delay(attempt)
        logger.warning("Attempt %d failed (%s), retrying in %.1fs …", attempt + 1, exc, delay)
        time.sleep(delay)
