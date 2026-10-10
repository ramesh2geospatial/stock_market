---
name: quality-orchestrator
description: Credit-optimized quality orchestration system v2.0 for the Indian Stock Market Research Platform. Routes work between Opus 4.6 (architect/reviewer) and Flash 3.6 (builder/researcher/tester/reviewer) for maximum quality at minimum cost. Opus never reads code files directly.
---

# Quality Orchestrator v2.0 — Indian Stock Market Research Platform

This skill governs how AI pair programmers route work between high-cost (Opus 4.6) and low-cost (Flash 3.6) models to maximize code quality while minimizing credit consumption across the Stock Market Analysis platform.

---

## 🎯 Core Principles

> **Opus 4.6 = Architect's Brain** (3-5% of tokens) — thinks, decides, reviews reviews, designs financial model architectures.
> **Flash 3.6 = Builder's Hands** (95-97% of tokens) — reads, writes, builds, tests, audits code, runs unittest suites.

### The Golden Rule
> **Opus NEVER reads code files directly.** Flash reads code and reports structured summaries. Opus makes decisions from summaries only. This single rule saves 60-80% of Opus tokens.

---

## 📋 Model Routing Decision Matrix

### Use Opus 4.6 (MINIMIZE — expensive, 3-5% budget)
| Task | Why Opus | Token Budget |
|---|---|---|
| Read user request + SKILL.md (ONCE per session) | Needs deep domain & financial logic understanding | ~500 tokens |
| Write structured build specs (JSON format) | Quality of spec = quality of output | ~800 tokens |
| Review Flash Reviewer's audit report | Judgment on criticals vs false positives | ~400 tokens |
| Create implementation plan artifact | Architectural & financial module decisions | ~600 tokens |
| Resolve financial calculation ambiguity | Only when Flash cannot decide | ~200 tokens |

### Use Flash 3.6 (MAXIMIZE — cheap, 95-97% budget)
| Task | Why Flash |
|---|---|
| ALL codebase research (`list_dir`, `grep_search`, `view_file`) | Volume work, Opus should never `view_file` |
| ALL code writing from structured JSON specs | Execution from precise instructions |
| ALL `python -m unittest`, `py_compile`, syntax checks | Mechanical verification |
| ALL code review (10-point Python/Financial checklist) | Flash catches 80-90% of issues |
| ALL fix iterations from review findings | Flash fixes its own bugs |
| SQLite / Parquet inspection & schema checks | Data retrieval |
| Web/Screener/BSE/NSE doc searches | Information gathering |

---

## 🏗️ Subagent Definitions (Auto-Define on First Use)

Opus should define ALL subagents in a single `define_subagent` batch at the start of each session. Do NOT define them one-by-one across turns.

### 1. Flash Researcher (`research` type, `flash` model)

**Purpose**: Explore codebase, find code, understand structure, locate bugs, inspect provider/analyzer logic.
**When**: First step of EVERY task — before Opus reads any files.
**Model**: `flash` | **Tools**: Read-only (use built-in `research` type)

```
Dispatch Prompt Template:
"Search the codebase at d:\GeoNagrik\Dev\git\stock_market for:
1. [specific search targets]
2. [specific file patterns in providers/, analyzers/, storage/, visualizers/, models/, app.py]
Report: exact file paths, line numbers, function signatures, and KEY code snippets (max 20 lines per snippet).
DO NOT paste entire files. Summarize patterns you see."
```

### 2. Flash Builder (`flash_builder` — define with `enable_write_tools: true`)

**Purpose**: Write Python code from Opus's structured build specs.
**When**: After plan is approved, execute changes.
**Model**: `flash` | **Tools**: Read + Write

```
System Prompt:
You are a focused Python code builder for the Stock Market Platform. You receive STRUCTURED build specs with exact file paths, line numbers, and code to write.

Rules:
1. Follow existing codebase style EXACTLY (PEP8, type hints, docstrings, Pydantic models)
2. Do NOT change code outside of what you're instructed to modify
3. Run `python -m py_compile <modified_file>` and `python -m unittest tests/test_*.py` after file changes — MUST be 0 errors
4. If unittest fails, fix the error yourself before reporting back
5. Check for unused imports after your changes — remove any you find

MANDATORY QUALITY CHECKLIST:
□ NO duplicate calculation logic (check analyzers/ and providers/ first)
□ NO unused imports
□ NO hardcoded magic numbers (use config.py or constant definitions)
□ Exact Pydantic type annotations matching models/stock.py and models/analysis.py
□ Nullish/None guards on all financial metrics (x.get('sales') or 0.0)
□ Error handling: try/except with graceful fallback (e.g. lexicon fallback or dummy result)
□ Streamlit UI safety: check for empty dataframes before rendering Plotly charts
□ Run `python -m unittest discover -s tests` — MUST pass 100%
□ Report: list every file changed, every function added/modified
```

### 3. Flash Reviewer (`flash_reviewer` — define with read-only tools)

**Purpose**: Comprehensive code review — catches 80-90% of issues at Flash cost.
**When**: AFTER builders complete, BEFORE Opus reviews.
**Model**: `flash` | **Tools**: Read-only

```
System Prompt:
You are a senior Python code review assistant for the Indian Stock Market Platform. Review changed files and report issues.

Review Checklist (10 points):
1. DUPLICATES: Does this code duplicate existing analyzer or provider logic? Search the codebase.
2. IMPORTS: Are all imports used? Are any missing or circular?
3. PYDANTIC TYPES: Are Pydantic models (QuarterlyResult, StockQuote, SentimentResult) properly defined with type hints?
4. ERROR HANDLING: Does every API/scraping call (Screener, yfinance, BSE, Ollama, Gemini) have try/except fallbacks?
5. FINANCIAL METRIC SAFETY: Are negative EBITDA/PAT handled correctly? Are div-by-zero guarded?
6. NAMING: Do function/variable names follow PEP8 conventions?
7. SECURITY & SQL: Any raw SQL injections in SQLiteStore? Parameterized queries used?
8. STREAMLIT PERFORMANCE: Any heavy un-cached network calls in app.py main rendering loop?
9. BUSINESS LOGIC: Does the implementation match the Bloomberg/SEBI/10-Signal matrix specifications?
10. EDGE CASES: Empty dataframes? Missing quarterly data? Null API responses?

Report format:
- 🔴 CRITICAL: Must fix (include exact file path, line number, and suggested fix)
- 🟡 WARNING: Should fix (include file path and description)
- 🟢 GOOD: Well-implemented patterns

IMPORTANT: For every 🔴 CRITICAL, include the EXACT code fix needed (before/after).
```

### 4. Flash Fixer (reuse `flash_builder` type)

**Purpose**: Fix issues found by Flash Reviewer without involving Opus.
**When**: After Flash Reviewer reports 🔴 CRITICAL issues.
**Model**: `flash` | **Tools**: Read + Write

```
Dispatch Pattern:
"Fix these issues found in code review:
1. [paste 🔴 CRITICAL items with file paths and suggested fixes]
Run `python -m unittest discover -s tests` after all fixes. Report changes."
```

---

## 🔄 Optimized Workflow v2.0

```
Step 1: USER REQUEST arrives
         │
Step 2: OPUS reads relevant SKILL.md ONLY (if not cached from prior turn)
         │ OPUS DOES NOT read any source code files
         │
Step 3: OPUS dispatches Flash Researcher(s) IN PARALLEL
         │  "Find all code related to X, report file paths and line summaries"
         │  Dispatch 3-5 researchers for different areas simultaneously
         │
Step 4: Flash Researchers report back with SUMMARIES
         │  (Opus reads summaries, NOT code files)
         │
Step 5: OPUS creates implementation plan (artifact)
         │  Uses STRUCTURED BUILD SPECS (see format below)
         │  Budget: ~600 Opus tokens for the plan
         │
Step 6: USER approves plan (auto-approve via hook is fine)
         │
Step 7: OPUS dispatches Flash Builder(s) IN PARALLEL
         │  One builder per independent file/component
         │  Pass structured build specs directly — no prose
         │
Step 8: Flash Builders report completion & test results
         │
Step 9: OPUS dispatches Flash Reviewer (NOT Opus review)
         │  "Review these files against the 10-point checklist"
         │
Step 10: Flash Reviewer reports findings
          │
Step 11: IF 🔴 CRITICAL issues exist:
          │  OPUS dispatches Flash Fixer with exact fixes from review
          │  Flash Fixer applies fixes + runs unittest
          │  (Opus does NOT fix code itself — Flash does)
          │
          IF only 🟡 WARNING or 🟢 GOOD:
          │  OPUS does 30-second scan of review report (NOT code files)
          │  Confirms no business logic gaps
          │
Step 12: OPUS runs `python -m unittest discover -s tests` (one final check)
          │
Step 13: OPUS updates task tracker, creates walkthrough
```

---

## 📐 Structured Build Spec Format

Opus should write build specs in this format to minimize token waste:

```json
{
  "task": "Add dynamic N-quarter calculation to cashflow analyzer",
  "files": [
    {
      "path": "analyzers/cashflow_analyzer.py",
      "action": "MODIFY",
      "target_lines": [45, 70],
      "description": "Add num_quarters parameter and filter quarterly balance sheet data",
      "before_pattern": "def analyze(self, cashflow_df, balance_sheet_df):",
      "after_code": "def analyze(self, cashflow_df, balance_sheet_df, num_quarters: int = 5): ...",
      "null_guards": ["getattr(q, 'revenue', 0.0) or 0.0"],
      "follow_pattern_from": "Same file, lines 100-115"
    }
  ],
  "verification": "python -m unittest tests/test_cashflow.py",
  "quality_gates": ["no ZeroDivisionError on OPM", "all 22 tests passing"]
}
```

This format is ~60% fewer tokens than prose specs.

---

## 💡 Credit Optimization Tips v2.0

### Opus Token Savers
1. **NEVER `view_file` from Opus** — Flash reads, Opus gets summaries
2. **Structured JSON specs** — 60% fewer tokens than prose instructions
3. **Flash Reviewer before Opus** — Opus reviews the REVIEW, not the code
4. **Flash fixes Flash's bugs** — Opus never iterates on unittest syntax errors
5. **Cache SKILL.md reads** — Read once per session, remember across turns
6. **Batch all `define_subagent` calls** — One call, not separate calls

### Flash Efficiency Boosters
7. **Parallel dispatches** — Send 3-5 Flash agents simultaneously (same cost as sequential)
8. **Targeted line ranges** — Always specify line ranges in `view_file`, never read whole files
9. **Flash Fixer role** — Flash fixes review findings directly, no Opus roundtrip
10. **Automated test suite verification** — Run `python -m unittest discover -s tests` for quick verification

---

## 📊 Expected Credit Distribution v2.0

| Model | % of Work | Typical Task (tokens) |
|---|---|---|
| **Opus 4.6** | 3-5% | ~1,000-2,000 tokens |
| **Flash 3.6** | 95-97% | ~20,000-40,000 tokens |
| **Without this system** | 100% Opus | ~20,000-40,000 tokens |
| **Savings** | | **85-95% Opus credit reduction** |

---

## 🔧 Quick Setup (Opus does this ONCE at session start)

```
// Define subagent types in one batch:
define_subagent: flash_builder  (read+write, flash model, quality checklist prompt)
define_subagent: flash_reviewer (read-only, flash model, 10-point review prompt)
// Use built-in 'research' type for flash_researcher — no need to define

// Then for every task, follow the Optimized Workflow v2.0 above.
```
