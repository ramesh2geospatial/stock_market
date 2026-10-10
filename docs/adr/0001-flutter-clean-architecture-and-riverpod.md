# ADR 0001: Flutter Clean Architecture & Riverpod for Cross-Platform Mobile App

- **Status**: Accepted
- **Date**: 2026-08-13
- **Deciders**: Lead Architect, Flutter Mobile Team

## Context & Problem Statement

We require a high-performance cross-platform mobile application for Android and iOS that renders mutual fund portfolios, stock-level holdings breakdown, sector pie charts, and portfolio overlap metrics smoothly.

## Decision Drivers

1. **Native Performance & Fluid UI**: Fast rendering of complex tables, charts, and tree maps.
2. **Codebase Compression**: 95%+ shared code between Android and iOS.
3. **State Management Reliability**: Deterministic reactive state management for offline caching and live NAV updates.

## Considered Options

1. **Flutter + Riverpod (Selected)**
2. React Native + Expo + Zustand
3. Native Kotlin (Android) + Swift (iOS)

## Decision Outcome

Chosen Option: **Flutter + Riverpod + Clean Architecture (Data, Domain, Presentation Layers)**.

### Consequences

- **Positive**: Single codebase for iOS & Android, high rendering performance via Impeller, excellent local SQLite integration, clean decoupling of UI and business logic.
- **Negative**: Requires Dart proficiency; PDF parsing for complex CAS statements requires Dart wrapper or native interop plugins (`pdf_text` / native bindings).
