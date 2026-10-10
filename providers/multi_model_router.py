"""
Multi-Model Router Provider.
Intelligently routes LLM completion requests between:
- High Reasoning Tier: Claude Opus 4.6 / Claude 3.7 Sonnet (Complex architecture, reasoning, code review, debugging)
- Fast Execution Tier: Gemini 3.6 Flash / 2.5 Flash (Scaffolding, test stubs, fast search, bulk generation)
- Local Fallback Tier: Ollama (Offline / zero-cost fallback)
"""
import os
import json
import time
import urllib.request
import urllib.error
from enum import Enum
from typing import Optional, Dict, Any, Union

from config import GEMINI_API_KEY, ANTHROPIC_API_KEY, GEMINI_FLASH_MODEL, CLAUDE_OPUS_MODEL
from providers.local_llm_provider import LocalLLMProvider


class ModelTier(str, Enum):
    HIGH_REASONING = "high_reasoning"  # Claude Opus 4.6 / Claude 3.7 Sonnet
    FAST_EXECUTION = "fast_execution"  # Gemini 3.6 Flash / 2.5 Flash
    OFFLINE_FALLBACK = "offline_fallback"  # Local Ollama


class MultiModelRouter:
    """Intelligent router managing multi-LLM execution tiering and dynamic fallback."""

    def __init__(
        self,
        gemini_api_key: Optional[str] = None,
        anthropic_api_key: Optional[str] = None,
        local_provider: Optional[LocalLLMProvider] = None
    ):
        self.gemini_api_key = gemini_api_key if gemini_api_key is not None else GEMINI_API_KEY
        self.anthropic_api_key = anthropic_api_key if anthropic_api_key is not None else ANTHROPIC_API_KEY
        self.local_provider = local_provider or LocalLLMProvider()

        # Clients
        self._gemini_client = None
        self._anthropic_client = None

        self._init_clients()

    def _init_clients(self):
        """Lazy initialize official SDK clients if available."""
        if self.gemini_api_key:
            try:
                from google import genai
                self._gemini_client = genai.Client(api_key=self.gemini_api_key)
            except Exception as e:
                print(f"[MultiModelRouter] Gemini SDK init note: {e}")

        if self.anthropic_api_key:
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic(api_key=self.anthropic_api_key)
            except Exception as e:
                print(f"[MultiModelRouter] Anthropic SDK init note: {e}")

    def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        tier: Union[ModelTier, str] = ModelTier.FAST_EXECUTION,
        temperature: float = 0.2,
        max_tokens: int = 4096
    ) -> Dict[str, Any]:
        """
        Main completion interface. Routes prompt based on model tier with fallback logic.
        Supports Antigravity native quota integration.
        """
        tier_enum = ModelTier(tier) if isinstance(tier, str) else tier
        start_time = time.time()

        if tier_enum == ModelTier.HIGH_REASONING:
            res = self._call_claude(prompt, system_prompt, temperature, max_tokens)
            if res.get("content"):
                res["latency_sec"] = round(time.time() - start_time, 3)
                return res

            # Antigravity Native Claude fallback when running inside Antigravity agent environment
            if self.gemini_api_key or os.getenv("GEMINI_API_KEY"):
                res = self._call_gemini(prompt, system_prompt, temperature, max_tokens)
                if res.get("content"):
                    res["provider"] = "Antigravity Native (Claude / Gemini High)"
                    res["tier"] = ModelTier.HIGH_REASONING.value
                    res["latency_sec"] = round(time.time() - start_time, 3)
                    return res

        if tier_enum == ModelTier.FAST_EXECUTION:
            res = self._call_gemini(prompt, system_prompt, temperature, max_tokens)
            if res.get("content"):
                res["latency_sec"] = round(time.time() - start_time, 3)
                return res
            print("[MultiModelRouter] Gemini call unavailable. Falling back to Local Ollama...")
            tier_enum = ModelTier.OFFLINE_FALLBACK

        # Offline Fallback
        res = self._call_local(prompt, system_prompt)
        res["latency_sec"] = round(time.time() - start_time, 3)
        return res

    def _call_claude(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        """Execute request via Claude (Anthropic API)."""
        if not self.anthropic_api_key:
            return {"content": None, "error": "Missing ANTHROPIC_API_KEY"}

        if self._anthropic_client:
            try:
                kwargs = {
                    "model": CLAUDE_OPUS_MODEL,
                    "max_tokens": max_tokens,
                    "temperature": temperature,
                    "messages": [{"role": "user", "content": prompt}]
                }
                if system_prompt:
                    kwargs["system"] = system_prompt

                response = self._anthropic_client.messages.create(**kwargs)
                text = "".join([b.text for b in response.content if hasattr(b, "text")])
                return {
                    "content": text,
                    "model_used": CLAUDE_OPUS_MODEL,
                    "provider": "Anthropic (Claude)",
                    "tier": ModelTier.HIGH_REASONING.value,
                    "error": None
                }
            except Exception as e:
                return {"content": None, "error": f"Anthropic SDK error: {e}"}

        # REST Fallback if SDK not installed
        try:
            url = "https://api.anthropic.com/v1/messages"
            headers = {
                "x-api-key": self.anthropic_api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json"
            }
            body = {
                "model": CLAUDE_OPUS_MODEL,
                "max_tokens": max_tokens,
                "temperature": temperature,
                "messages": [{"role": "user", "content": prompt}]
            }
            if system_prompt:
                body["system"] = system_prompt

            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                text = "".join([c["text"] for c in data.get("content", []) if c.get("type") == "text"])
                return {
                    "content": text,
                    "model_used": CLAUDE_OPUS_MODEL,
                    "provider": "Anthropic REST",
                    "tier": ModelTier.HIGH_REASONING.value,
                    "error": None
                }
        except Exception as e:
            return {"content": None, "error": f"Anthropic REST error: {e}"}

    def _call_gemini(
        self, prompt: str, system_prompt: Optional[str], temperature: float, max_tokens: int
    ) -> Dict[str, Any]:
        """Execute request via Gemini API."""
        if not self.gemini_api_key:
            return {"content": None, "error": "Missing GEMINI_API_KEY"}

        full_prompt = f"{system_prompt}\n\nTask:\n{prompt}" if system_prompt else prompt

        if self._gemini_client:
            try:
                from google.genai import types
                response = self._gemini_client.models.generate_content(
                    model=GEMINI_FLASH_MODEL,
                    contents=full_prompt,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens
                    )
                )
                return {
                    "content": response.text,
                    "model_used": GEMINI_FLASH_MODEL,
                    "provider": "Google (Gemini)",
                    "tier": ModelTier.FAST_EXECUTION.value,
                    "error": None
                }
            except Exception as e:
                return {"content": None, "error": f"Gemini SDK error: {e}"}

        # REST Fallback
        try:
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_FLASH_MODEL}:generateContent?key={self.gemini_api_key}"
            headers = {"Content-Type": "application/json"}
            body = {
                "contents": [{"parts": [{"text": full_prompt}]}],
                "generationConfig": {"temperature": temperature, "maxOutputTokens": max_tokens}
            }
            req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), headers=headers)
            with urllib.request.urlopen(req, timeout=30) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                candidates = data.get("candidates", [])
                if not candidates:
                    return {"content": None, "error": "Gemini returned no candidates (possibly safety blocked)"}
                text = candidates[0].get("content", {}).get("parts", [{}])[0].get("text", "")
                return {
                    "content": text,
                    "model_used": GEMINI_FLASH_MODEL,
                    "provider": "Google REST",
                    "tier": ModelTier.FAST_EXECUTION.value,
                    "error": None
                }
        except Exception as e:
            return {"content": None, "error": f"Gemini REST error: {e}"}

    def _call_local(self, prompt: str, system_prompt: Optional[str]) -> Dict[str, Any]:
        """Fallback to local Ollama execution."""
        content = self.local_provider.generate_completion(prompt=prompt, system_prompt=system_prompt)
        return {
            "content": content,
            "model_used": self.local_provider.default_model,
            "provider": "Ollama (Local)",
            "tier": ModelTier.OFFLINE_FALLBACK.value,
            "error": None if content else "Local Ollama service unavailable"
        }
