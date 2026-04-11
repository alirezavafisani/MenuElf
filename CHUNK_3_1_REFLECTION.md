# Chunk 3.1 Reflection

## What was wrong

The chunk 3 CI smoke test was the first piece of code that actually tried to import `main.py` in a completely fresh environment (no `backend/menus/`, no `name_mapping.json`, no encrypted data bundle). It immediately tripped over an unguarded `os.listdir(MENUS_DIR)` call on line 97 of `backend/main.py`, inside `get_restaurant_names()`, which is called at module-import time on line 104.

Locally and on Railway, `backend/menus/` always exists — locally because the owner has the real files, on Railway because the Docker build extracts them from the encrypted tarball. The `os.listdir` call has been there since before the analytics work; it never crashed because it was never exercised without the directory present.

This is ironic: I added the smoke test specifically to catch chunk-1-style crashes before they hit Railway, and the first thing it caught was an import-time crash that chunks 1 and 2 happened to avoid only by accident. The smoke test did its job — but because Railway is configured to wait for CI, chunk 3's real Railway deploy is now blocked by a latent bug that existed in main all along.

## The fix

Two belt-and-suspenders changes:

1. **Fix 1 — make `get_restaurant_names()` resilient.** The `os.listdir(MENUS_DIR)` call is now wrapped in `try/except FileNotFoundError`, prints a warning, and returns an empty `NAME_MAPPING`. The caller on line 104 is also wrapped in its own try/except so any residual exception can't crash the import. If the dir is missing, the app starts with 0 restaurants — broken for production but harmless for CI (and production will never see this because Railway has the real data).

2. **Fix 2 — make CI create a fake `backend/menus/`.** Added `mkdir -p menus` to the smoke-test workflow right before the `python -c "from main import app"` line. This makes CI's environment one step closer to production without needing to decrypt the real data bundle.

Fix 1 alone would be enough to unblock CI. Fix 2 alone would also be enough. Having both means:
- If someone deletes Fix 2 in a future workflow refactor, Fix 1 still protects the app.
- If someone adds another unguarded I/O call at import time, Fix 2 gives them a realistic scratch space to work with.

## Verification

Simulated both paths locally with the real `main.py`:

```
=== TEST 1: WITHOUT menus/ dir (Fix 1 alone) ===
WARNING: MENUS_DIR /home/user/MenuElf/backend/menus not found. App will
start with no restaurants (expected in CI / fresh checkouts).
Found 0 restaurants
OK: app imported, RESTAURANT_LIST = empty

=== TEST 2: WITH empty menus/ dir (Fix 2 simulation) ===
Found 0 restaurants
OK: app imported successfully
```

Both work. Also ran the full chunk 3 Playwright suite as a regression check: **11 / 11 passed in 17.8s**, no changes in behaviour.

## Audit of other import-time side effects in `main.py`

I audited every module-level statement in `backend/main.py` for unguarded filesystem / network I/O that could crash import. Here's the full inventory:

| Line | Statement | Risk | Status |
|------|-----------|------|--------|
| L32 | `load_dotenv(...)` | No — `load_dotenv` is no-op on missing file | Safe |
| L34 | `client = OpenAI(api_key=...)` | No — constructor accepts `None` | Safe |
| L55 | `log_event / get_stats` import from `analytics.py` | Already wrapped in `try/except init_db()` from chunk 2 | Safe |
| L73-83 | Router imports (`user_intelligence`, `friends`, `group_dining`) | Could fail if routers do import-time I/O. Spot-checked: they use lazy `_get_supabase()` helpers, no top-level side effects | Safe |
| L104 | `RESTAURANT_LIST = get_restaurant_names()` | **Was the crash** | **FIXED** |
| L217 | `load_menu_index()` | Already wrapped in try/except inside the function | Safe |
| L230 | `load_places_data()` | Uses `os.path.isfile()` guard before `open()` | Safe |
| L243 | `load_photo_urls()` | Uses `os.path.isfile()` guard before `open()` | Safe |
| L256 | `load_restaurant_photos()` | Uses `os.path.isfile()` guard before `open()` | Safe |
| L262-265 | `PHOTO_MANIFEST` load | Uses `os.path.isfile()` guard before `open()` | Safe |

I also grepped the routers directory for `os.listdir`; there's one hit at `routers/group_dining.py:834` but it's deep inside a function body, not at module scope, so it's safe.

## Remaining import-time risks

Nothing truly dangerous, but a few medium-risk patterns worth noting:

1. **Router import chains.** The 3 routers under `routers/` each import lazily, but they pull in `engines/*` modules and `supabase` — the supabase client itself has C extensions (pyroaring, zstandard, etc.) that *could* fail to load on an exotic CPU architecture. Nothing I can do about that without auditing every transitive dep.

2. **`init_db()` in `analytics.py` still runs at import time** (wrapped in try/except from chunk 2). If the `ANALYTICS_DB_PATH` env var points somewhere exotic, the makedirs call in chunk 2's fix will silently swallow the error and the rest of the module will still work. Fine.

3. **`load_menu_index()` has a broad `try/except Exception`** that catches everything. If `menu_db.json` is present but malformed JSON, the exception is swallowed and `MENU_INDEX` stays empty — the app starts, but `/search-dishes` silently returns no results and `/random-dish` 404s. The health endpoint would reveal this, but there's no startup-time signal. Worth upgrading to log the exception type explicitly, but not critical enough for this hotfix.

4. **The `load_menu_index` / `load_places_data` / `load_photo_urls` / `load_restaurant_photos` functions all print on success but are *silent* when the file is missing** — they just set an empty dict. So in the smoke test we'd see "Found 0 restaurants" but no explicit "restaurant_places_data.json not found" messages. This is cosmetic but makes debugging harder when you're staring at CI logs trying to figure out why 3 different data sources are empty. Future cleanup.

5. **The CI smoke test still passes dummy Supabase keys.** It *should* be fine because Supabase access is lazy, but every time we add code that reads Supabase at module load, we'll get a fresh CI failure. It would be more robust to patch the smoke test to set `SUPABASE_URL=` to an unroutable localhost URL so any accidental call fails fast with a connection error rather than a silent DNS lookup — but that's pre-optimizing.

## The meta-lesson

Chunk 1 and chunk 2 both had the exact same class of bug — unguarded file-system calls at module-import time — and both landed in production. Chunk 3.1 is the third occurrence. This is a pattern, not an accident. The fix for the pattern (not just this instance) is: **treat any top-level call that touches the filesystem, network, or env as a hazard**, and either:
- wrap it in `try/except` with a warning-level log, or
- defer it to a startup-event handler or first-use lazy load.

A senior engineer would say this is `@app.on_event("startup")` territory — all the `load_*` calls should live there, not at module scope. That's a chunk-4-or-later refactor though. For now, the smoke test plus these defensive wrappers are enough to stop the bleeding.

## What's next

Railway deploy should go green once this lands. No behaviour changes in production (the real `menus/` dir exists there). The app now starts gracefully in any environment, which makes future CI jobs (lint, unit tests, load tests) easier to add without playing whack-a-mole with import-time crashes.
