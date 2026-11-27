# Architecture

How the Chess Opening Analyzer is built. Domain terms such as Repertoire, Recall Gap and Sync are defined in [GLOSSARY.md](../GLOSSARY.md). This file covers the code that implements them.

## Implementation notes on domain terms

- **Study color:** read from the orientation of the study's first chapter, using the Lichess PGN export with `?orientation=true`.
- **Repertoire trees:** one move tree per color, built only from that color's studies and keyed by SAN moves (for example "e4", "Nf3"). Each node tracks the moves available at that position.
- **Study membership:** for each position key and color, the Repertoire stores every study whose lines contain the position, with the chapter id and, when the position is on that chapter's mainline, its ply. That is enough for an "open in study" deep link.
- **Opening Name:** derived from the Lichess study name and normalized: hyphens become spaces and redundant prefixes are removed.
- **Game Filters:** all of them, including the Study filter, are remembered in the browser between visits.
- **Sync when already up to date:** a Repertoire fetched in the last `REPERTOIRE_FRESH_SECONDS` (30) counts as up to date. The Sync doesn't fetch it again, and its Lichess side still succeeds.

## Layered Orchestration

The system is organized in horizontal layers from request → response:

1. **HTTP Layer** (`main.py`, `users.py`)
   - Defines FastAPI endpoints (e.g. `/api/recall-view`)
   - Parses query parameters into domain objects
   - Delegates to orchestration layer: each handler asks `users.py` for the User (by Lichess token) and uses their pipeline or Sync
   - **`users.py`:** the per-User registry. A token's first request asks Lichess for its account (remembered for that token; a refusal is a 401). Each User holds their Lichess account, that account's exclusion list and Drill Attempts, their pipeline and their one Sync between requests; `main.py` keeps no per-User state
   - Returns JSON responses; the recall view is serialised as the pipeline returns it

2. **Orchestration Layer** (`pipeline.py`)
   - **`RepertoireAnalysisPipeline`:** Stateful orchestrator that coordinates the full analysis workflow
   - Owns caching logic for the user's Repertoire (TTL-based)
   - Defines abstract interfaces (`RepertoireSource`, `GameSource`) that concrete implementations must satisfy
   - Does NOT know about HTTP, Lichess, or Chess.com — all domain concepts

3. **Source Layer** (`sources.py`)
   - Concrete implementations of abstract source interfaces
   - **`LichessRepertoireSource`:** Fetches every study the user owns from Lichess and builds their `Repertoire`
   - **`CacheGameSource`:** Reads the user's games from the local SQLite cache as typed `Game`s, deciding the user's color and result (the only place either is worked out from the players' names)
   - These are adapters at the seams between the pipeline and external systems

4. **Domain Logic Layer**
   - **`repertoire.py`:** Defines `Repertoire`, `RepertoireNode`, `RepertoireBuilder`
   - **`repertoire_walker.py`:** Walks one game through the Repertoire into a walk record (`RepertoireWalker`, `WalkRecord`)
   - **`recall_gaps.py`:** The pure Recall Gap aggregator: groups walk records into the recall view (studies, ranked Recall Gaps, totals with the monthly Miss Rate and Miss Depth trend) under the Game Filters. Its view dataclasses are the wire contract of `/api/recall-view`
   - **`games.py`:** `Game`, one of the user's games as it crosses the game seam: URL, date, archive month, time class, rated, Chess.com's opening label, moves, and the user's color and result
   - **`opening_distribution.py`:** The pure Opening Distribution: filters the user's `Game`s by its own Game Filters (`DistributionFilters`: time controls, rated, color, archive-month and timestamp bounds), then counts openings by games played, the user's wins, draws and losses in each (by the result rule the recall view uses), first-move categories and the monthly trend, in UTC months, of the five most played openings
   - **`game_result.py`:** The pure result rule (`player_result`): the user's win, loss or draw from White's Chess.com result code, applied once by `CacheGameSource`, so the recall view and the Opening Distribution read the same result
   - **`game_cache.py`:** SQLite game storage; it returns a user's cached games and filters none
   - **`sync.py`:** The Sync service: Chess.com months into the game cache, the Lichess Repertoire refresh, each source's status
   - **`exclusions.py`:** A Lichess account's persisted "not repertoire" exclusion list (SQLite, next to the game cache)
   - **`drill_attempts.py`:** A Lichess account's persisted Drill Attempts (SQLite, next to the game cache)
   - Rows stored before these were kept per account are adopted by the first account to open each store
   - **`drill_scheduler.py`:** The pure drill scheduler: when each Recall Gap is next due, and a practice session's queue
   - These modules are system-independent; they don't import HTTP libraries

5. **External Integration Layer**
   - **`lichess.py`:** Async HTTP client for Lichess API (OAuth, study fetching, PGN download)
   - **`chess_com.py`:** Async HTTP client for Chess.com API (archive listing, game fetching, ECO/opening extraction)

## Key Design Patterns

### Dependency Injection

The pipeline accepts abstract source interfaces, not concrete implementations. `users.py` instantiates the concrete sources and injects them when it makes a User:

```python
repertoire_source = LichessRepertoireSource(lichess_token=token, list_studies=list_owned_studies)
game_source = CacheGameSource()
pipeline = RepertoireAnalysisPipeline(
    repertoire_source=repertoire_source,
    game_source=game_source,
)
view = await pipeline.recall_view(username, filters)
```

This makes the pipeline testable: tests can inject mock sources. The pipeline also takes a clock (default: real time), read wherever it needs the time; the User's Sync shares it. The Sync takes the pipeline itself, so Sync tests run the real pipeline and fake only `RepertoireSource`, `GameSource` and the Chess.com client.

### Repertoire Caching

`users.py` keeps one pipeline per User, and that pipeline caches the user's Repertoire with a 1-hour TTL. It is keyed as "the user's Repertoire", not by a set of study ids: the Study filter never changes what the Repertoire contains. Requests within the TTL reuse the cached trees; after it expires the Repertoire is rebuilt from every owned study, so a study newly created on Lichess joins at the next rebuild. Changing the "not repertoire" exclusion list (the Lichess account's, stored in SQLite next to the game cache) drops the cached Repertoire of the User who changed it, so the change takes effect on their next request.

A Sync rebuilds the Repertoire at once (joining a build already in flight, or skipping one fetched in the last 30 seconds) and keeps the previous trees if nothing changed. The pipeline also keeps its last analysis (every cached game walked through the Repertoire) and reuses it until the Repertoire changes or a Sync brings new games, so re-analysis runs only if something changed. New games drop only the syncing User's last analysis: another User linked to the same Chess.com account keeps theirs until their own next Sync or Repertoire change. Clearing an account's cached games drops every User's last analysis.

### Sync Service

`sync.py` holds the Sync (one per User, kept by `users.py`). The backend keeps no record of the linked Chess.com account: the browser names it on every request, so `start` and `status` take it. A Sync is made of the User's pipeline, `ChessComSync`, `RepertoireSyncLog` and the pipeline's clock, and calls the pipeline directly to refresh the Repertoire (skipping one fetched under `REPERTOIRE_FRESH_SECONDS`, 30, ago), drop the last analysis and diff the Recall Gaps. `ChessComSync` fetches the months the cache may lack — months not yet cached, months that failed last time (recorded in SQLite), and every month from the one of the last Sync on — and only advances the Chess.com last-sync time when no month failed. `Sync` runs both sources, each failing on its own, tracks each source's status and last-success time (both times persisted in SQLite: the game cache for Chess.com, read through `ChessComSync`, and `RepertoireSyncLog` for Lichess, by Lichess account), the number of cached games, and reports progress ("Fetching games… 2023-04"). It also diffs each Recall Gap's status in the pipeline's last analysis against the analysis after the Sync (`gap_changes`) for the "what changed" line; with no last analysis for the account (e.g. the first Sync, or the pipeline last analysed another account) only the new games are reported. Each account's result, Chess.com status and `runs` (finished Syncs) are kept apart, and a status for an account reports only its own, with that account's Chess.com last-success time and cached-game count; the Lichess side is the User's whichever account is asked about. A start for another account while a Sync runs makes that account next (at most one; a later start for yet another replaces it), and it runs once the running one finishes; while it waits, its status is `running` with "Waiting for another Sync…". `POST /api/sync` starts one; `GET /api/sync` polls it.

### Error Handling

- **Analysis failure (per-game):** Log and continue. One failed game doesn't block the entire analysis.
- **Source failure (invalid token, study not accessible):** Fail fast at the HTTP layer. It is a user error, not a transient issue. A token is checked on its first request, when Lichess is asked for its account, and after that only when the Repertoire is fetched: while it is cached, a revoked token still gets the cached view.

## Data Flows

### Analysis Request Flow

```
HTTP /api/recall-view (Game Filters, token)
  ↓
HTTP layer builds the Game Filters (RecallFilters.for_date_range; an unknown
date range preset is a 422)
  ↓
users.user_for(token): reuse the User's RepertoireAnalysisPipeline (one per
User, created on first request, once Lichess names the token's account, with
LichessRepertoireSource(token, list_studies, the account's exclusions), the
account's Drill Attempts,
CacheGameSource())
  ↓
Call pipeline.recall_view(username, filters)
  ↓
Pipeline._get_repertoire() checks cache; if miss, calls source.fetch_repertoire()
  ↓
LichessRepertoireSource.fetch_repertoire()
  ├─ List the user's owned studies, minus those marked "not repertoire"
  ├─ Fetch each owned study's PGN from Lichess (?orientation=true)
  ├─ Feed to RepertoireBuilder (each study into its first chapter's color tree)
  └─ Return built Repertoire (white_tree, black_tree, study membership, and
     each study's color and name)
  (Lichess refusing the token here, 401/403, is answered 401 "Invalid Lichess
  token"; the token is not checked while the Repertoire is cached)
  ↓
Pipeline calls game_source.games(username) — every cached game, as typed Games
with the user's color and result
  ↓
Pipeline walks each game with RepertoireWalker into a walk record
  ↓
aggregate(walked games, filters, Repertoire, now) groups the player errors
inside the filters into ranked Recall Gaps, each naming and deep-linking its
studies, counts the totals and the Miss Rate, buckets the last 12 months'
Miss Rate under every filter but the date range, counts the Open gaps shown
and the gaps Closed in the date range, and lists the Repertoire's studies
sorted by opening name, each with its Recall Gaps under every filter but the
Study filter
  ↓
HTTP layer returns the RecallView as is:
Return {studies: [{id, name, opening_name, color, gaps}], gaps: [...],
        totals: {analysed, opponent_left_book, book_completed, miss_rate,
                 trend: [{month, games, miss_rate}], open_gaps, closed_in_range}}
```

## Seams & Adapters

A **seam** is a boundary where behavior can be altered without editing the code that depends on it in place.

1. **Repertoire fetching seam:**
   - Abstract interface: `RepertoireSource`
   - Current adapter: `LichessRepertoireSource` (fetches from Lichess)
   - Alternative adapters: `MockRepertoireSource` (for testing), `FileRepertoireSource` (load from PGN file)

2. **Game fetching seam:**
   - Abstract interface: `GameSource.games(username) -> list[Game]`; filtering is the reader's (the Recall Gap aggregator, the Opening Distribution)
   - Current adapter: `CacheGameSource` (local SQLite); `/api/opening-stats` reads through it too
   - Alternative adapters: `ChessComDirectGameSource` (fetch from Chess.com live, if API allowed it)

3. **Frontend backend seam:**
   - Abstract interface: the backend object the recall view store (`createRecallView` in `frontend/src/recall/recallView.js`) and the sync client call: `readSyncState`, `startSync`, `loadRecallView`, `loadPracticeQueue`, `recordDrillAttempt`
   - Current adapter: `createHttpBackend` (`frontend/src/backend/httpBackend.js`, calls the API)
   - Alternative adapters: `createMemoryBackend` (`frontend/src/backend/memoryBackend.js`, for testing and the sample mode), where each call is scripted to answer, reply from its arguments, fail or delay. Frontend behaviour is tested at this seam, not through components: the recall view store (`recallView.test.js`), the sync client (`syncClient.test.js`) and the sample account (`sampleAccount.test.js`), each over the in-memory backend
   - **Sample mode:** `npm run dev:sample` (`vite --mode sample`, port 5174) runs the real frontend on the sample account (`frontend/src/sample/sampleAccount.js`): the in-memory adapter answering from made-up Studies, Recall Gaps and a year of games. `main.jsx` imports it only in that mode, so other builds leave it out, and `AuthProvider` and `SyncProvider` use it in place of the Lichess sign-in and the HTTP adapter. The Opening Distribution and Settings pages still call the backend server directly, so they show errors there
