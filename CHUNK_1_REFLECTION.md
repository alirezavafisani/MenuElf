# Chunk 1 Reflection

## What was built

Privacy-preserving usage analytics for MenuElf using SQLite. No third-party services, no cookies, no raw IP storage.

**Backend (`backend/analytics.py`):**
- SQLite event table tracking `page_view`, `search`, and `chat` events
- Privacy-preserving visitor hashing: IP + date + salt → SHA-256 truncated to 16 chars. Same visitor on the same day = same hash. Different day = different hash. Raw IPs never stored.
- `GET /stats` public endpoint returning total visitors, searches, chats, weekly visitors, and 14-day daily breakdown
- Middleware logs page views on `/`, `/app`, `/app/`
- Event logging wired into `/search-dishes` and `/chat` endpoints

**Frontend (`web/src/components/StatsCounter.tsx`):**
- Fetches `/stats` on mount, renders social proof counter in footer
- Shows "{searches} dishes served to {visitors} hungry Calgarians · {weekly} this week"
- Gracefully hidden when no data (returns null)

**Tests (`web/tests/analytics.spec.ts`):**
- Playwright E2E tests with a self-contained test server (mock search/chat + real analytics module)
- 3 persona simulation + stats counter UI verification + schema validation

## Playwright test results

All 3 tests **PASSED** (8.7s total):

```
┌──────────────┬──────────┬─────────┬─────────┐
│    Metric    │  Before  │  After  │  Delta  │
├──────────────┼──────────┼─────────┼─────────┤
│ Visitors     │        0 │       1 │      +1 │
│ Searches     │        0 │       6 │      +6 │
│ Chats        │        0 │       1 │      +1 │
│ Weekly       │        0 │       1 │         │
└──────────────┴──────────┴─────────┴─────────┘
```

- `total_visitors` increased by 1 (all 3 personas from localhost = same daily hash)
- `total_searches` increased by exactly 6 (2 + 1 + 3)
- `total_chats` increased by 1
- Footer counter displayed: "7 dishes served to 1 hungry Calgarians · 1 this week"
- `/stats` schema validated correctly

## What's working well

1. **Zero-dependency analytics.** Uses only Python stdlib (sqlite3, hashlib). No new pip packages. No external services to break.
2. **Privacy by design.** The daily-rotating hash means even if the DB leaks, you can't trace visitors back to IPs. This is better than most "privacy-friendly" analytics tools.
3. **Fail-safe pattern.** Every analytics call is wrapped in try/except. The main app cannot crash due to analytics. This is the right tradeoff — analytics is observability, not core functionality.
4. **The test infrastructure is reusable.** The lightweight test server pattern (mock endpoints + real analytics module) can be extended for future chunks without needing the full backend stack.

## Concerns and friction points

1. **SQLite on Railway is risky.** Railway uses ephemeral filesystems. The analytics DB will be wiped on every deploy unless the owner configures a persistent volume. This is the single biggest operational risk. Without a volume mount, the "proof of use" data vanishes regularly. The owner MUST set up a Railway volume mounted at the backend directory, or switch `ANALYTICS_DB_PATH` to point to a persistent location.

2. **The visitor hash conflates all localhost traffic.** In the Playwright tests, all 3 personas produced 1 unique visitor because they share `127.0.0.1`. Behind a reverse proxy (like Railway), all traffic may appear as the proxy's IP unless `X-Forwarded-For` is parsed. The middleware currently uses `request.client.host`, which behind a proxy is the proxy IP, not the real user. This will undercount unique visitors in production. Fix: use `request.headers.get("x-forwarded-for", request.client.host)` for the IP.

3. **`BaseHTTPMiddleware` has known performance issues.** Starlette's `BaseHTTPMiddleware` consumes the request body for every request, which can cause issues with streaming responses and adds latency. For a low-traffic app like MenuElf this is fine, but a pure ASGI middleware would be better at scale.

4. **The StatsCounter fetches `/stats` on every page load with no caching.** For a site with real traffic, this is a SQLite read on every visitor. Not a problem at MenuElf's scale, but adding a 60-second cache header or in-memory TTL cache on the stats endpoint would be easy and prudent.

5. **The `datetime.utcnow()` call is deprecated in Python 3.12+.** Should use `datetime.now(timezone.utc)` instead. Works fine now but will generate warnings eventually.

6. **Tests use a mock server, not the real backend.** The Playwright tests validate the analytics module in isolation, which is correct and fast. But they don't catch integration bugs (e.g., if the analytics import breaks the real `main.py` due to import order issues). A smoke test that actually starts the real backend would be more comprehensive, but requires all dependencies.

## Suggestions for improvement

**Should we add AI agents to the pipeline?**
Not for analytics. Analytics should be dumb, reliable infrastructure. An AI agent analyzing usage patterns could be useful in a later chunk (e.g., "what dishes are most searched but least available?"), but that's a feature on top of analytics, not part of the tracking pipeline.

**Should we remove any complexity?**
The `daily_breakdown` in `/stats` is more than we need for social proof. The footer only uses `total_visitors`, `total_searches`, and `weekly_visitors`. The daily breakdown is useful for a future admin dashboard but adds query complexity. Keep it — it's cheap and the extra SQL is readable.

**Are any prompts suboptimal?**
The chat system prompts in `main.py` are good but verbose. The menu JSON is dumped in full into every system prompt, which burns tokens. For chunk 2+, consider summarizing the menu or using RAG to inject only relevant items. This isn't an analytics issue but it's the biggest cost driver.

**Is the workflow correct?**
Yes. The event → SQLite → stats endpoint → frontend counter flow is the simplest possible architecture. No queues, no background workers, no external DBs. Correct for this stage.

**What would a senior engineer criticize?**
1. **No migration system.** If we need to alter the events table schema, there's no migration tooling. `CREATE TABLE IF NOT EXISTS` only works for the initial schema.
2. **No rate limiting on `/stats`.** Someone could hammer it. Low priority but worth noting.
3. **The analytics middleware runs synchronously inside an async server.** The `sqlite3` library blocks the event loop during writes. For proper async, use `aiosqlite`. At MenuElf's traffic this doesn't matter; at 100+ concurrent users it would.
4. **No data retention policy.** The events table will grow forever. Should add a cron or startup task that prunes events older than 90 days.

**What's the single biggest risk going into chunk 2?**
Railway filesystem persistence. If the analytics DB gets wiped on deploy, the owner will think analytics is broken. This needs to be solved before chunk 2 — either a Railway volume, or migrating to Supabase (which is already in the stack for user profiles) as the analytics store.
