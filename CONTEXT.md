# Chess Opening Analyzer — Domain Context

## Overview

**Chess Opening Analyzer** helps players identify where they deviated from their repertoire during chess games. Users link their Lichess study collections (which define their repertoire) to their Chess.com game history, and the analyzer finds the first move in each game that wasn't in their prepared opening lines.

## Core Concepts

### Repertoire

A collection of chess opening lines that a player has studied and prepared. Stored as Lichess Studies (one study per opening). Each study contains one or more chapters with PGN-formatted game trees showing the main lines and key variations.

**Repertoire trees:** one move tree per color, each built only from that color's studies:

- **White tree:** the lines of the White studies, walked for games where the user plays White
- **Black tree:** the lines of the Black studies, walked for games where the user plays Black

Each tree is indexed by chess moves (SAN notation, e.g. "e4", "Nf3"). At each position, the repertoire node tracks which moves are available.

**Study membership:** for each position key (and color), the Repertoire knows every study whose lines contain the position, and for each of those studies the chapter id and, when the position is on that chapter's mainline, its ply — enough for an "open in study" deep link.

**Which studies:** every study the user owns on Lichess, except those they have explicitly marked as "not repertoire".

**Study color:** every study belongs to exactly one color — White or Black — and contributes only to that color's tree. A study never mixes colors. The color is the orientation of the study's first chapter (Lichess PGN export with `?orientation=true`).

### Deviation

The first move in a Chess.com game that was **not** available in the repertoire at that position. Signals either:

1. **Player error:** User played a move outside their prepared lines
2. **Opponent left book:** Opponent deviated first, requiring a non-prepared response
3. **Book completed:** Game reached the end of studied lines (rare)

### Recall Gap

A repertoire position where the user has played a move outside their prepared lines at least once, across the analyzed games. It is the primary unit of the recall loop: one thing to fix.

- **Identity:** the position itself (board, side to move, castling, en passant — not the move counters), not the move path that reached it.
- **Occurrence:** each player-error *Deviation* at that position is one occurrence of the Recall Gap. The gap records which wrong moves were played and how often; different wrong moves at the same position are the same gap.
- **Book moves:** every repertoire move at the position is an acceptable answer; there is no single "correct" move.
- **Ranking:** by number of occurrences within the Game Filters window, ties broken by most recent occurrence.

- **Studies:** a Recall Gap belongs to every study whose lines contain its position.
- **Status:** *Open* or *Closed*. A gap is Closed once the user has reached its position in two real games since its last occurrence and played a book move both times. Only real games decide status — Drill Attempts never close or reopen a gap — and all games count, whatever the Game Filters. A new occurrence reopens a Closed gap and starts the count again.

Only player errors form Recall Gaps. *Opponent left book* and *book completed* Deviations are reported only as totals.

_Avoid:_ "mistake", "leak", "weak spot" as synonyms — use Recall Gap for the grouped unit and Deviation for the single-game event. For status, avoid "fixed", "resolved", "mastered" — use Closed.

### Drill Attempt

One practice run of a Recall Gap: the user replays the line from the first move up to the Recall Gap's position and plays a move there, while the opponent's moves are played for them. The line is the one from the gap's most recent occurrence. Any repertoire move counts as correct at every turn.

- **Outcome:** a pass, or a fail at the first wrong move. A failed attempt records the position where that first wrong move was played.
- **Relationship to Recall Gaps:** drill results decide when a Recall Gap is next due for practice. They never create Recall Gaps and never change their ranking, because Recall Gaps come only from real games.

_Avoid:_ "exercise", "puzzle", "quiz" — use Drill Attempt.

### Miss Rate

The share of analysed games in which the user made a player-error *Deviation*: the headline measure of whether recall is improving. It counts real games only; Drill Attempts never affect it. Game Filters narrow which games count, so selecting a study gives that study's Miss Rate.

_Avoid:_ "accuracy", "error rate" — Chess.com uses "accuracy" for engine scores.

### Game Filters

Selection criteria for analyzing only relevant games:

- **Time control:** bullet, blitz, rapid, daily
- **Rated:** Only rated games, or both rated and casual
- **Color:** White only, Black only, or both (Opening Distribution only — on the recall view, color is implied by the Study filter)
- **Date range:** Year/month bounds (from_year/from_month to to_year/to_month) or Unix timestamps
- **Study:** one or more studies; narrows which Recall Gaps are shown (and which games the totals count) without changing what counts as the Repertoire or as a Recall Gap. None selected means all studies. A gap is shown when any selected study contains its position; a game counts when the position where it left book (its Deviation position) is in a selected study — merely passing through a study's lines on the way into another's doesn't count.

All Game Filters, including the Study filter, are remembered in the browser between visits.

### Sync

Bringing both data sources up to date — Chess.com games into the local cache, and the Lichess Repertoire (studies and their lines) — then re-running the analysis if anything changed. Runs automatically when the app opens if the last Sync is stale, or on demand.

- **Partial Sync:** some Chess.com months or the Lichess refresh failed; what succeeded is kept, and the failed parts are retried on the next Sync.
- A Sync never interrupts a Drill Attempt; its analysis is applied once practice ends.

_Avoid:_ "refresh", "import" as synonyms — use Sync.

### Opening Name

Human-readable label for a repertoire line. Examples: "Sicilian Defense", "Vienna Game", "London System". Extracted from Lichess study names and normalized (hyphens → spaces, redundant prefixes removed).

## Architecture: Layered Orchestration

The system is organized in horizontal layers from request → response:

1. **HTTP Layer** (`main.py`)
   - Defines FastAPI endpoints (e.g. `/api/recall-view`)
   - Parses query parameters into domain objects
   - Delegates to orchestration layer
   - Returns JSON responses

2. **Orchestration Layer** (`pipeline.py`)
   - **`RepertoireAnalysisPipeline`:** Stateful orchestrator that coordinates the full analysis workflow
   - Owns caching logic for the user's Repertoire (TTL-based)
   - Defines abstract interfaces (`RepertoireSource`, `GameSource`) that concrete implementations must satisfy
   - Does NOT know about HTTP, Lichess, or Chess.com — all domain concepts

3. **Source Layer** (`sources.py`)
   - Concrete implementations of abstract source interfaces
   - **`LichessRepertoireSource`:** Fetches every study the user owns from Lichess and builds their `Repertoire`
   - **`CacheGameSource`:** Fetches games from the local SQLite cache, applies filters
   - These are adapters at the seams between the pipeline and external systems

4. **Domain Logic Layer**
   - **`repertoire.py`:** Defines `Repertoire`, `RepertoireNode`, `RepertoireBuilder`
   - **`repertoire_walker.py`:** Walks one game through the Repertoire into a walk record (`RepertoireWalker`, `WalkRecord`)
   - **`recall_gaps.py`:** The pure Recall Gap aggregator: groups walk records into ranked Recall Gaps and totals under the Game Filters
   - **`game_cache.py`:** SQLite game storage and filtering
   - These modules are system-independent; they don't import HTTP libraries

5. **External Integration Layer**
   - **`lichess.py`:** Async HTTP client for Lichess API (OAuth, study fetching, PGN download)
   - **`chess_com.py`:** Async HTTP client for Chess.com API (archive listing, game fetching, ECO/opening extraction)

## Key Design Patterns

### Dependency Injection

The pipeline accepts abstract source interfaces, not concrete implementations. Callers (main.py) instantiate the concrete sources and inject them:

```python
repertoire_source = LichessRepertoireSource(lichess_token=token, list_studies=list_owned_studies)
game_source = CacheGameSource()
pipeline = RepertoireAnalysisPipeline(
    repertoire_source=repertoire_source,
    game_source=game_source,
)
view = await pipeline.recall_view(username, filters)
```

This makes the pipeline testable: tests can inject mock sources.

### Repertoire Caching

The HTTP layer keeps one pipeline per Lichess user, and that pipeline caches the user's Repertoire with a 1-hour TTL. It is keyed as "the user's Repertoire", not by a set of study ids: the Study filter never changes what the Repertoire contains. Requests within the TTL reuse the cached trees; after it expires the Repertoire is rebuilt from every owned study, so a study newly created on Lichess joins at the next rebuild.

### Error Handling

- **Analysis failure (per-game):** Log and continue. One failed game doesn't block the entire analysis.
- **Source failure (invalid token, study not accessible):** Fail fast at the HTTP layer. It is a user error, not a transient issue.

## Data Flows

### Analysis Request Flow

```
HTTP /api/recall-view (Game Filters, token)
  ↓
HTTP layer validates token
  ↓
Reuse the user's RepertoireAnalysisPipeline (one per Lichess user, created on
first request with LichessRepertoireSource(token, list_studies), CacheGameSource())
  ↓
Call pipeline.recall_view(username, filters)
  ↓
Pipeline._get_repertoire() checks cache; if miss, calls source.fetch_repertoire()
  ↓
LichessRepertoireSource.fetch_repertoire()
  ├─ List the user's owned studies
  ├─ Fetch each owned study's PGN from Lichess (?orientation=true)
  ├─ Feed to RepertoireBuilder (each study into its first chapter's color tree)
  └─ Return built Repertoire (white_tree, black_tree, study membership)
  ↓
Pipeline calls game_source.fetch_games(username, GameFilters()) — every cached game
  ↓
Pipeline walks each game with RepertoireWalker into a walk record
  ↓
aggregate(walked games, filters, studies of a position) groups the player
errors inside the filters into ranked Recall Gaps, counts the totals, and
counts each study's Recall Gaps under every filter but the Study filter
  ↓
Return {studies: [{id, name, opening_name, color, gaps}], gaps: [...],
        totals: {analysed, opponent_left_book, book_completed}}
```

## Seams & Adapters

A **seam** is a boundary where behavior can be altered without editing the pipeline in place.

1. **Repertoire fetching seam:**
   - Abstract interface: `RepertoireSource`
   - Current adapter: `LichessRepertoireSource` (fetches from Lichess)
   - Alternative adapters: `MockRepertoireSource` (for testing), `FileRepertoireSource` (load from PGN file)

2. **Game fetching seam:**
   - Abstract interface: `GameSource`
   - Current adapter: `CacheGameSource` (local SQLite)
   - Alternative adapters: `ChessComDirectGameSource` (fetch from Chess.com live, if API allowed it)

## Future Deepening Opportunities

(From the architecture review)

- **Candidate 2:** Frontend state consolidation (move analysis state from scattered components into a single context)
- **Candidate 3:** Opening name normalization (consolidate name cleanup rules into a single `OpeningNormalizer` module)
- **Candidate 4:** Cache sync → auto-reanalysis flow (explicit orchestration of sync + reanalysis)
- **Candidate 5:** Deepen API clients (move domain logic from callers into `LichessClient`, `ChessComClient`)
- **Candidate 6:** Repertoire tree traversal logic (extract `RepertoireWalker` to encapsulate tree walking)
