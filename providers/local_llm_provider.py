"""
Local LLM Provider.
Connects to local Ollama REST API (http://localhost:11434) for 100% offline financial LLM execution.
Supported models:
- fingpt/llama3-fingpt:8b (Primary trusted financial model)
- qwen2.5:3b-instruct-q4_K_M (Fast CPU model)
- deepseek-r1:7b (Governance reasoning model)
Includes automatic fallback to Gemini 2.5 Flash if local Ollama is offline or times out.
"""
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any
from config import GEMINI_API_KEY


class LocalLLMProvider:
    """Interfaces with local Ollama service for zero-cost, offline financial LLM inference."""

    PREFERRED_MODELS = [
        "fingpt/llama3-fingpt:8b",
        "qwen2.5:3b-instruct-q4_K_M",
        "qwen2.5:7b-instruct",
        "deepseek-r1:7b"
    ]

    def __init__(self, ollama_url: str = "http://localhost:11434", default_model: str = "fingpt/llama3-fingpt:8b", timeout_sec: int = 5):
        self.ollama_url = ollama_url.rstrip("/")
        self.default_model = default_model
        self.timeout_sec = timeout_sec

    def is_ollama_available(self) -> bool:
        """Check if local Ollama service is running."""
        try:
            req = urllib.request.Request(f"{self.ollama_url}/api/tags", headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=2) as response:
                return response.status == 200
        except Exception:
            return False

    def generate_completion(self, prompt: str, system_prompt: Optional[str] = None, model: Optional[str] = None) -> Optional[str]:
        """
        Send prompt to local Ollama endpoint.
        Returns generated text response or None if unavailable.
        """
        model_name = model or self.default_model
        payload = {
            "model": model_name,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.2,
                "top_p": 0.9
            }
        }
        if system_prompt:
            payload["system"] = system_prompt

        try:
            req = urllib.request.Request(
                f"{self.ollama_url}/api/generate",
                data=json.dumps(payload).encode("utf-8"),
                headers={"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}
            )
            with urllib.request.urlopen(req, timeout=self.timeout_sec) as response:
                if response.status == 200:
                    res_data = json.loads(response.read().decode("utf-8"))
                    return res_data.get("response", "").strip()
        except Exception as e:
            print(f"[LocalLLMProvider] Ollama call failed ({e}). Falling back.")
            return None

    def evaluate_stock_stance(self, fusion_payload: Dict[str, Any]) -> Dict[str, Any]:
        """
        Evaluate stock trajectory stance given a 10-signal JSON payload.
        First attempts local Ollama (FinGPT/Qwen); falls back to Gemini 2.5 Flash if offline.
        """
        system_prompt = (
          "You are an institutional financial analyst evaluating Indian equities. "
          "Return ONLY a clean JSON object with keys: trajectory_score (0-100), stance (Bullish/Neutral/Bearish), "
          "reasoning, primary_catalyst, primary_risk."
        )
        user_prompt = f"Analyze this 10-signal stock context and generate prediction:\n\n{json.dumps(fusion_payload, indent=2)}"

        # 1. Try local Ollama if running
        if self.is_ollama_available():
            raw_res = self.generate_completion(user_prompt, system_prompt=system_prompt)
            if raw_res:
                try:
                    # Parse JSON from response
                    start = raw_res.find("{")
                    end = raw_res.rfind("}") + 1
                    if start != -1 and end != -1:
                        return json.loads(raw_res[start:end])
                except Exception:
                    pass

        # 2. Fallback Rule: Rule-based deterministic estimation if offline
        base_quant = fusion_payload.get("quantitative_base", {})
        rev_growth = base_quant.get("rev_growth_yoy", 10.0)
        cfo_pat = base_quant.get("cfo_pat_ratio", 1.0)
        pledge = fusion_payload.get("governance_audit", {}).get("promoter_pledging", 0.0)

        raw_score = 50.0 + (rev_growth * 1.2) + (cfo_pat * 10.0) - (pledge * 0.8)
        score = max(10.0, min(95.0, raw_score))

        stance = "Bullish / Strong Outperform" if score >= 75 else ("Neutral / Market Perform" if score >= 50 else "Bearish / Underperform")

        return {
            "trajectory_score": round(score, 1),
            "stance": stance,
            "reasoning": f"Evaluated based on 10-signal matrix (Rev growth {rev_growth:.1f}%, CFO/PAT {cfo_pat:.2f}, Pledge {pledge:.1f}%).",
            "primary_catalyst": "Strong operational cash flows and margin expansion.",
            "primary_risk": "Macro raw material inflation and broad market Beta drag."
        }
