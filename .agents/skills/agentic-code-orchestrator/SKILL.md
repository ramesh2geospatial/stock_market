---
name: agentic-code-orchestrator
description: Dual-model agentic AI coding orchestrator combining Claude Opus 4.6 (High Reasoning) and Gemini 3.6 Flash (Fast Execution).
---

# Agentic Code Orchestrator Skill

This skill governs all automated coding requests, script writing, refactoring, and feature builds in this workspace.

## 4-Stage Execution Protocol

When receiving a coding task or feature request:

1. **Stage 1 (Intent & Task Decomposition)**:
   - Call Gemini 3.6 Flash to parse prompt intent, workspace context, and sub-task dependencies.
2. **Stage 2 (Architectural Blueprint)**:
   - Call Claude Opus 4.6 to design strict interfaces, type annotations, and module structures.
3. **Stage 3 (Rapid Implementation)**:
   - Call Gemini 3.6 Flash to draft full implementation files.
4. **Stage 4 (Adversarial Audit & Synthesis)**:
   - Call Claude Opus 4.6 to review code against design invariants and apply final fixes.

## CLI Execution Command

```bash
python scripts/agentic_coder.py --prompt "<your_coding_prompt>" [--out <target_file_path>]
```
