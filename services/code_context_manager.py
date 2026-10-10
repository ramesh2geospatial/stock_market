"""
Code Context Manager.
Scans repository structure, extracts AST symbol definitions, and constructs token-optimized
context windows for LLM subagents.
"""
import os
import ast
from pathlib import Path
from typing import Dict, Any, List, Optional


class CodeContextManager:
    """Manages workspace discovery and context aggregation for coding LLMs."""

    def __init__(self, root_dir: Optional[str] = None):
        self.root_dir = Path(root_dir) if root_dir else Path(__file__).parent.parent.resolve()

    def get_workspace_summary(self, max_files: int = 50) -> Dict[str, Any]:
        """Collect file tree and brief outline of workspace python files."""
        summary = {"files": [], "structure": {}}
        count = 0

        for path in self.root_dir.rglob("*.py"):
            if count >= max_files:
                break
            rel_path = path.relative_to(self.root_dir).as_posix()
            if rel_path.startswith(".") or "venv" in rel_path or "__pycache__" in rel_path:
                continue

            symbols = self._extract_ast_symbols(path)
            summary["files"].append({
                "path": rel_path,
                "size_bytes": path.stat().st_size,
                "symbols": symbols
            })
            count += 1

        return summary

    def _extract_ast_symbols(self, file_path: Path) -> List[str]:
        """Extract top-level functions and classes from a python file."""
        symbols = []
        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                tree = ast.parse(f.read(), filename=file_path.name)
            for node in tree.body:
                if isinstance(node, ast.ClassDef):
                    symbols.append(f"class {node.name}")
                elif isinstance(node, ast.FunctionDef):
                    symbols.append(f"def {node.name}")
        except Exception:
            pass
        return symbols

    def build_prompt_context(self, target_files: Optional[List[str]] = None, max_chars: int = 25000) -> str:
        """Construct a formatted text context of target repository files for LLM prompt injections."""
        context_parts = []
        total_len = 0

        files_to_read = target_files or []
        if not files_to_read:
            # Pick key workspace files by default
            summary = self.get_workspace_summary(max_files=15)
            files_to_read = [f["path"] for f in summary["files"]]

        for rel_path in files_to_read:
            full_path = self.root_dir / rel_path
            if not full_path.exists():
                continue

            try:
                with open(full_path, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                snippet = f"--- FILE: {rel_path} ---\n{content}\n"
                if total_len + len(snippet) > max_chars:
                    # Truncate content to fit limit
                    remaining = max_chars - total_len
                    snippet = f"--- FILE: {rel_path} (Truncated) ---\n{content[:remaining]}\n"
                    context_parts.append(snippet)
                    break

                context_parts.append(snippet)
                total_len += len(snippet)
            except Exception as e:
                context_parts.append(f"--- FILE: {rel_path} (Error reading: {e}) ---\n")

        return "\n".join(context_parts)
