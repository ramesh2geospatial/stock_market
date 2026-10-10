"""
Agentic Coding Orchestrator.
Coordinates multi-stage multi-model LLM execution for high-productivity software development:
1. Gemini 3.6 Flash (Fast Execution): Intent parsing & repository context assembly
2. Claude Opus 4.6 (High Reasoning): Architectural blueprinting & system design
3. Gemini 3.6 Flash (Fast Execution): Rapid code drafting & test scaffolding
4. Claude Opus 4.6 (High Reasoning): Adversarial code review, safety audit & final synthesis
"""
import json
import re
from typing import Dict, Any, List, Optional

from providers.multi_model_router import MultiModelRouter, ModelTier
from services.code_context_manager import CodeContextManager


class AgenticCodingOrchestrator:
    """Multi-agent orchestrator driving intelligent Claude Opus + Gemini Flash collaboration."""

    def __init__(self, router: Optional[MultiModelRouter] = None, context_manager: Optional[CodeContextManager] = None):
        self.router = router or MultiModelRouter()
        self.context_manager = context_manager or CodeContextManager()

    def process_prompt(self, prompt: str, target_files: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        Execute full agentic workflow for an incoming user coding prompt.
        Returns detailed output trace across all stages.
        """
        trace = {
            "prompt": prompt,
            "stages": [],
            "final_code": "",
            "summary": ""
        }

        # Context Assembly
        repo_context = self.context_manager.build_prompt_context(target_files=target_files)

        # Stage 1: Fast Task Decomposition & Intent Analysis (Gemini Flash)
        stage1_prompt = f"""Analyze the user's coding request and break it down into explicit component tasks.
User Request: {prompt}

Workspace Context:
{repo_context[:3000]}...

Provide a brief structured plan summarizing:
1. Core goal & scope
2. Primary files to modify or create
3. Potential edge cases or dependencies
"""
        stage1_res = self.router.generate(
            prompt=stage1_prompt,
            tier=ModelTier.FAST_EXECUTION,
            system_prompt="You are an expert AI Tech Lead analyzing user coding requests."
        )
        trace["stages"].append({
            "stage": "Stage 1: Intent & Task Decomposition",
            "model_used": stage1_res.get("model_used"),
            "provider": stage1_res.get("provider"),
            "output": stage1_res.get("content")
        })

        # Stage 2: High-Reasoning Architectural Blueprinting (Claude Opus 4.6)
        stage2_prompt = f"""You are the Lead Systems Architect. Produce an explicit implementation blueprint for the following task.

User Coding Request:
{prompt}

Task Analysis:
{stage1_res.get('content')}

Repository Context:
{repo_context}

Specify:
- Module interfaces, class structures, and function signatures.
- Type hints, exception handling requirements, and concurrency/performance considerations.
- Step-by-step code structure for the implementation.
"""
        stage2_res = self.router.generate(
            prompt=stage2_prompt,
            tier=ModelTier.HIGH_REASONING,
            system_prompt="You are a Principal Software Architect (Claude Opus). Produce rigorous design blueprints."
        )
        trace["stages"].append({
            "stage": "Stage 2: High Reasoning Architectural Blueprint",
            "model_used": stage2_res.get("model_used"),
            "provider": stage2_res.get("provider"),
            "output": stage2_res.get("content")
        })

        # Stage 3: Rapid Code Drafting (Gemini Flash)
        stage3_prompt = f"""Implement the complete, production-ready Python code based strictly on the Architectural Blueprint.

User Request: {prompt}

Architectural Blueprint:
{stage2_res.get('content')}

Repository Context:
{repo_context[:5000]}

Write complete, unbroken code with docstrings, type annotations, and error handling. Do not truncate code.
"""
        stage3_res = self.router.generate(
            prompt=stage3_prompt,
            tier=ModelTier.FAST_EXECUTION,
            system_prompt="You are a Fast AI Software Engineer. Write clean, complete code implementation."
        )
        trace["stages"].append({
            "stage": "Stage 3: Rapid Code Scaffolding",
            "model_used": stage3_res.get("model_used"),
            "provider": stage3_res.get("provider"),
            "output": stage3_res.get("content")
        })

        # Stage 4: Adversarial Code Audit & Final Synthesis (Claude Opus 4.6)
        stage4_prompt = f"""Review and audit the drafted code against the Architectural Blueprint and safety standards.

Original Request: {prompt}
Architectural Blueprint:
{stage2_res.get('content')}

Drafted Code Implementation:
{stage3_res.get('content')}

Perform a rigorous code audit:
1. Correct any missing imports, logic flaws, edge case unhandlings, or type bugs.
2. Refine docstrings and maintain absolute adherence to architectural invariants.
3. Output the FINAL, fully-polished, complete code ready to save to disk.
"""
        stage4_res = self.router.generate(
            prompt=stage4_prompt,
            tier=ModelTier.HIGH_REASONING,
            system_prompt="You are a Principal Code Reviewer & Security Auditor (Claude Opus). Deliver pristine, verified code."
        )
        trace["stages"].append({
            "stage": "Stage 4: Adversarial Audit & Final Synthesis",
            "model_used": stage4_res.get("model_used"),
            "provider": stage4_res.get("provider"),
            "output": stage4_res.get("content")
        })

        trace["final_code"] = self._extract_code_blocks(stage4_res.get("content") or stage3_res.get("content") or "")
        trace["summary"] = f"Successfully processed prompt using dual-model agent pipeline ({stage2_res.get('model_used')} + {stage3_res.get('model_used')})."

        return trace

    def _extract_code_blocks(self, text: str) -> str:
        """Extract code within triple backtick blocks if present, otherwise return raw text."""
        blocks = re.findall(r"```(?:python)?\s*\n(.*?)\n```", text, re.DOTALL)
        if blocks:
            return "\n\n".join(blocks)
        return text
