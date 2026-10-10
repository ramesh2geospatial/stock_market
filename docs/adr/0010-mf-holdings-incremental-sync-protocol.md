# ADR 0010: MF Holdings Incremental Sync Protocol (Supabase Cloud → Local SQLite)

- **Status**: Accepted
- **Date**: 2026-08-14
- **Deciders**: Lead Financial Data Architect

---

## 🎯 Context & Problem Statement

The MF Holdings Tracker needs to keep local SQLite cache synchronized with Supabase Cloud PostgreSQL. The `mf_stock_holdings` table grows by ~150,000 rows/month (44 AMCs × ~1,500 schemes × ~100 stocks). Full table downloads on every app launch would consume excessive bandwidth and time.

## 💡 Decision: Timestamp-Based Incremental Delta Sync

### Sync Protocol
1. **Client reads** `sync_metadata.last_synced_at` from local SQLite
2. **Client sends** `GET /rest/v1/mf_stock_holdings?created_at=gt.{last_synced_at}&order=created_at.asc&limit=500`
3. **Server returns** only rows created/updated after the client's watermark
4. **Client upserts** into local `mf_holdings_cache` using `ON CONFLICT (scheme_id, symbol, as_of_date) DO UPDATE`
5. **Client updates** `sync_metadata.last_synced_at = max(created_at)` from response

### Why PostgREST `?created_at=gt.{timestamp}` Over Full Download?
- **Bandwidth**: After initial sync (~5MB), monthly deltas are ~200KB (only new month's data)
- **Latency**: Incremental sync completes in <2 seconds vs 15-30 seconds for full download
- **Battery**: Minimal CPU/network usage on mobile devices
- **Supabase limits**: Stays well within free tier row-read quotas

### Why Local SQLite Cache Over Direct Supabase Reads?
- **Offline support**: App works with 0 connectivity after initial sync
- **Search latency**: Local SQLite queries execute in <1ms vs 200-500ms Supabase round-trip
- **Cost**: Zero Supabase API calls during normal browsing/filtering
- **Rate limiting**: No risk of hitting Supabase rate limits during user sessions

### Why `sync_metadata` Table Over Hardcoded Timestamps?
- **Per-table tracking**: Different tables can sync at different cadences
- **Auditability**: `row_count` field tracks cache completeness
- **Restartability**: Interrupted syncs resume from the last successful watermark
- **Testability**: Easy to mock and verify in unit tests

## 📊 Trade-offs

| Aspect | Pro | Con |
|--------|-----|-----|
| Eventual Consistency | Max 24h stale (configurable) | Not real-time |
| Storage | ~5MB local cache | Duplicate data (cloud + local) |
| Complexity | Simple HTTP GET + SQLite upsert | Need watermark management |
| Reliability | Graceful offline degradation | First sync requires connectivity |

## 📝 Consequences
- **Easier**: Offline browsing, zero-latency search, battery-friendly, predictable Supabase costs
- **Harder**: Cache invalidation on schema changes, potential stale data during monthly transition periods, need to handle `sync_metadata` corruption gracefully
