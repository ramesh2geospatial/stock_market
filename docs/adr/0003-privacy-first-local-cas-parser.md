# ADR 0003: Privacy-First Local CAS PDF Parser for Mutual Fund Folios

- **Status**: Accepted
- **Date**: 2026-08-13
- **Deciders**: Security Architect, Mobile Lead

## Context & Problem Statement

Users import their mutual fund holdings via CAMS / KFintech Consolidated Account Statements (CAS). Handling password-protected PDF statements on external servers poses severe PII, PAN, and regulatory compliance risks.

## Decision Drivers

1. **User Trust & Privacy**: Financial statements must never leave the user's mobile device unencrypted.
2. **Zero Server Liabilities**: Parsing CAS on-device eliminates backend database storage of sensitive user transaction records.

## Decision Outcome

Chosen Option: **On-Device Local CAS PDF Parsing**:
1. User selects/shares their CAMS/KFintech CAS PDF in the Flutter mobile app and enters their PDF password (stored securely in iOS Keychain / Android Keystore).
2. Local Dart PDF parsing engine extracts folio numbers, scheme names, unit balances, and purchase values directly on-device.
3. Only normalized scheme IDs and unit counts are matched against public NAV and holdings databases.

### Consequences

- **Positive**: 100% user privacy, compliance with DPDP Act 2023, zero server storage of PII/PAN data.
- **Negative**: Local Dart parsing logic must account for variations in CAMS and KFintech CAS PDF layout formats across different statement generator versions.
