# ADR 0002: Legal Open-Data Pipeline for Mutual Fund NAVs and AMC Holdings Disclosures

- **Status**: Accepted
- **Date**: 2026-08-13
- **Deciders**: Data Architect, Legal Compliance Team

## Context & Problem Statement

We need to pull daily Mutual Fund NAVs, scheme metadata, and monthly portfolio stock holdings legally without costly commercial subscriptions or violating web scraping terms of service.

## Decision Drivers

1. **Regulatory Open Data**: SEBI mandates all Indian AMCs to disclose daily NAVs on AMFI and monthly portfolio holdings (Excel/CSV) on statutory website portals by the 10th of every month.
2. **Zero Commercial API Fees**: Use open AMFI daily feeds and public `mfapi.in` endpoints.
3. **Legal Compliance**: Adhere to website terms of service by parsing statutory open download links and caching aggregated data server-side rather than aggressive real-time scraping.

## Decision Outcome

Chosen Option: **Hybrid Open-Data Pipeline**:
1. **Daily NAVs & Scheme Master**: Ingested directly from AMFI official `NAVAll.txt` and cached via `api.mfapi.in` REST API.
2. **Monthly Portfolio Holdings**: Serverless ETL pipeline that downloads statutory monthly portfolio files (CSV/XLSX) published by AMCs, normalizes stock allocations, and stores them in Supabase/PostgreSQL.

### Consequences

- **Positive**: 100% legal compliance with SEBI disclosures, zero API licensing costs, accurate stock-level holdings for 500+ Indian mutual funds.
- **Negative**: Portfolio holdings update monthly (aligned with SEBI 10th-of-month disclosure schedules) rather than real-time daily stock trade updates.
