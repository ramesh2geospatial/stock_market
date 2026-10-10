---
name: grill-with-docs
description: A relentless interview to sharpen a plan, architecture, or UX design while actively producing documentation (ADRs and domain glossary entries) as decisions resolve.
---

# Grill With Docs Skill

`/grill-with-docs` fuses **Relentless Interviewing (`/grilling`)** with **Active Domain Modeling (`/domain-modeling`)**.

## Workflow Protocol

1. **Relentless Interview Loop**:
   - Walk down each branch of the design tree one question at a time.
   - Resolve dependencies between decisions sequentially.
   - Provide recommended answers for each question based on domain knowledge and codebase facts.
   - Look up code/schema facts automatically via tools rather than asking the user trivial questions.

2. **Active Documentation Capture**:
   - As terms and domain rules crystallise during grilling, update `CONTEXT.md` immediately.
   - For high-impact, non-reversible trade-offs, draft an Architectural Decision Record in `docs/adr/00XX-<title>.md`.

3. **No Execution Before Shared Understanding**:
   - Hold code changes until the design is fully stress-tested and approved by the user.
