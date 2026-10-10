---
name: domain-modeling
description: Build and sharpen a project's domain model. Use when pinning down domain terminology or ubiquitous language, recording architectural decisions (ADRs), or updating project context.
---

# Domain Modeling Skill

Actively build and sharpen the project's domain model as you design. This is the *active* discipline — challenging terms, inventing edge-case scenarios, and writing the glossary and decisions down the moment they crystallise.

## File Structure

- `CONTEXT.md` at root or context folder: Single source of truth for domain glossary and ubiquitous language.
- `docs/adr/`: Architecture Decision Records capturing non-obvious trade-offs.

## During the Session

### 1. Challenge Against the Glossary
When terms conflict with existing language in `CONTEXT.md`, flag it immediately.

### 2. Sharpen Fuzzy Language
Propose precise canonical terms for vague or overloaded words (e.g. distinguishing Citizen vs User, Vendor vs Storefront, Token vs Booking).

### 3. Discuss Concrete Scenarios
Stress-test domain relationships with specific edge-case scenarios to enforce clear boundary conditions.

### 4. Cross-Reference with Code & Schemas
Check if code, database RPCs, or schemas align with domain statements. Highlight any contradictions.

### 5. Update Glossary & ADRs Inline
- Update `CONTEXT.md` as terms resolve (keep devoid of low-level implementation details).
- Offer ADRs sparingly when decisions are hard to reverse, non-obvious, and reflect explicit trade-offs.
