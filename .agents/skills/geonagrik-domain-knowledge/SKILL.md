---
name: geonagrik-domain-knowledge
description: Master domain knowledge skill for GeoNagrik platform, covering ubiquitous language, user/vendor/provider personas, booking/queue token workflows, H3 spatial indexing, ad monetization, chat encryption, campaign rules, and governance models.
---

# GeoNagrik Domain Knowledge Skill

This skill brings the comprehensive ubiquitous language, domain model, and architectural rules of the **GeoNagrik Civic & Local Business Platform** (https://geonagrik.in) into the active agent environment.

---

## 👥 Persona Definitions & Ubiquitous Language

1. **Citizen (or Neighbor)**: A resident participant who posts geotagged community updates, tests water quality (TDS), discovers local stores, books services, and requests queue tokens.
2. **Vendor (or Storefront)**: A local business, clinic, service provider, or mobile merchant. Manages storefront profiles, products, services, daily promotional deals, provider rosters, and walk-in queue tokens.
3. **Provider (or Staff / Vehicle / Driver)**: An entity registered under a Vendor's roster. Static providers represent stylists, specialists, or doctors; mobile providers represent fleet units/drivers.
4. **Administrator (Admin)**: System operators verifying storefront submissions, auditing reported content, managing feature kill-switches, and enforcing platform compliance.

---

## 💳 Subscriptions & Monetization Rules

- **Basic (Free) Plan**: Single-operator storefront handling bookings and tokens from a single device dashboard.
- **Premium Subscription (₹499 / 30 Days)**: Unlocks provider roster delegation, scoped RBAC dashboards (Owner, Provider, Receptionist), multi-device real-time token sync, and advanced analytics.
- **Vendor Ad Monetization (70/30 Split)**: Platform revenue sharing allocating 70% of ad impression revenue to the Provider (`doctor_share_paisa`) and 30% to the platform (`platform_fee_paisa`), settled weekly via batch RPCs in paisa precision.

---

## 🛠️ Feature & Workflow Models

- **Booking (Appointment)**: Scheduled slot for a specific Service assigned to a Provider. States: `pending` → `confirmed` → `in_progress` → `completed` (or `cancelled`/`rejected`).
- **Token (Walk-in Queue Token)**: Digital queue number with estimated wait time and time bands (morning, afternoon, evening) for same-day walk-in service.
- **Category-Gated Booking**: System constraint restricting booking calendars and queue tokens strictly to valid service categories (`hospital`, `radiology`, `salon`, `car_rental`). Retail/produce categories are excluded.
- **Daily Deal**: Time-limited discount (flat/%) published by Vendors, bound to store profiles and notified to favoriters.
- **Community Post**: Geotagged update visible on the chronological **Nearby Proximity Feed**.

---

## 🌐 Spatial Indexing & Privacy Architecture

- **H3 Hexagonal Grid (Resolution 7 ~ 5 km²)**: Spatial clustering resolution ensuring precise home/citizen lat/lng coordinates are never exposed on map visualizers.
- **Guest Campaign Mode**: Privacy-isolated submission where lat/lng is stripped (`NULL`), storing only H3 grid indices (`h3_res4`, `h3_res6`, `h3_res7`, `h3_res8`).
- **Approximate Geospatial Isolation**: Enforced by atomic `SECURITY DEFINER` RPC `create_anonymous_post`.

---

## 💬 Chat, Security & Governance

- **Native Chat Encryption (`enc:v2:`)**: AES stream cipher format with CSPRNG IVs protecting message text in transit and storage.
- **Group Governance**: Creator/Admin/Member hierarchy with posting locks (`who_can_send_messages`), metadata shields (`who_can_edit_info`), admin approval join queues, and disappearing message TTLs (`off`, `24h`, `7d`, `90d`).
- **Privacy Shield**: Automatic disabling of 1:1 interaction controls when blocking is active between citizens/vendors.

---

## ⚡ Hard Item & Quality Governance

- **Hard Item Escalation Triggers**:
  1. Transactional Integrity & Concurrency (monetary paisa calculations, advisory locks, RPC concurrency).
  2. Security & Cryptographic Boundaries (`enc:v2:`, Supabase multi-tenant RLS, PII isolation).
  3. Domain Ambiguity (requires `/grill-with-docs` session + ADR creation).
  4. Execution Stall (failed automated tests after 1 retry).
- **Architecture Decision Records (ADRs)**: Stored in `docs/adr/00XX-<title>.md` for non-reversible, non-obvious technical trade-offs.
