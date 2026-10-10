"""
Unit tests for the Agentic Coding System:
- MultiModelRouter tier resolution & fallbacks
- CodeContextManager AST scanning & context compilation
- AgenticCodingOrchestrator pipeline execution
"""
import unittest
from unittest.mock import MagicMock

from providers.multi_model_router import MultiModelRouter, ModelTier
from services.code_context_manager import CodeContextManager
from services.agentic_orchestrator import AgenticCodingOrchestrator


class TestAgenticCoder(unittest.TestCase):

    def test_code_context_manager_summary(self):
        """Verify context manager extracts AST symbols and workspace summary."""
        cm = CodeContextManager()
        summary = cm.get_workspace_summary(max_files=5)

        self.assertIn("files", summary)
        self.assertIsInstance(summary["files"], list)
        if summary["files"]:
            first_file = summary["files"][0]
            self.assertIn("path", first_file)
            self.assertIn("symbols", first_file)

    def test_code_context_manager_prompt_context(self):
        """Verify prompt context building."""
        cm = CodeContextManager()
        context = cm.build_prompt_context(max_chars=1000)

        self.assertIsInstance(context, str)
        self.assertLessEqual(len(context), 1200)

    def test_multi_model_router_fallback(self):
        """Verify router falls back gracefully when API keys are unconfigured."""
        mock_local = MagicMock()
        mock_local.generate_completion.return_value = "Mocked Ollama Code Output"

        router = MultiModelRouter(
            gemini_api_key="",
            anthropic_api_key="",
            local_provider=mock_local
        )

        res = router.generate("Write a test function", tier=ModelTier.HIGH_REASONING)
        self.assertEqual(res["content"], "Mocked Ollama Code Output")
        self.assertEqual(res["tier"], ModelTier.OFFLINE_FALLBACK.value)

    def test_agentic_orchestrator_mocked_pipeline(self):
        """Verify full orchestrator pipeline execution with mocked router responses."""
        mock_router = MagicMock()
        mock_router.generate.side_effect = [
            {"content": "1. Scope: Add helper. 2. File: helper.py", "model_used": "gemini-2.5-flash", "provider": "Google"},
            {"content": "class Helper:\n    def run(self): pass", "model_used": "claude-3-7-sonnet-20250219", "provider": "Anthropic"},
            {"content": "```python\nclass Helper:\n    def run(self):\n        return True\n```", "model_used": "gemini-2.5-flash", "provider": "Google"},
            {"content": "```python\nclass Helper:\n    def run(self) -> bool:\n        '''Execute helper.'''\n        return True\n```", "model_used": "claude-3-7-sonnet-20250219", "provider": "Anthropic"}
        ]

        orchestrator = AgenticCodingOrchestrator(router=mock_router)
        result = orchestrator.process_prompt("Create a helper class")

        self.assertEqual(len(result["stages"]), 4)
        self.assertIn("class Helper", result["final_code"])
        self.assertIn("return True", result["final_code"])


if __name__ == "__main__":
    unittest.main()
