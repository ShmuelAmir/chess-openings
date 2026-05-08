# Chess Opening Analyzer — Domain Context

## Overview

**Chess Opening Analyzer** helps players identify where they deviated from their repertoire during chess games. Users link their Lichess study collections (which define their repertoire) to their Chess.com game history, and the analyzer finds the first move in each game that wasn't in their prepared opening lines.

## Core Concepts

### Repertoire

A collection of chess opening lines that a player has studied and prepared. Stored as Lichess Studies (one study per opening). Each study contains one or more chapters with PGN-formatted game trees showing the main lines and key variations.

**Repertoire tree:** A dual-perspective move tree built from the studies:

- **White tree:** Positions where it's White's turn to move (user's first move in games where they play White)
- **Black tree:** Positions where it's Black's turn to move (user's first move in games where they play Black)

The tree is indexed by chess moves (SAN notation, e.g. "e4", "Nf3"). At each position, the repertoire node tracks which moves are available (user's options).

### Deviation

The first move in a Chess.com game that was **not** available in the repertoire at that position. Signals either:

1. **Player error:** User played a move outside their prepared lines
2. **Opponent left book:** Opponent deviated first, requiring a non-prepared response
3. **Book completed:** Game reached the end of studied lines (rare)

### Game Filters

Selection criteria for analyzing only relevant games:

- **Time control:** bullet, blitz, rapid, daily
- **Rated:** Only rated games, or both rated and casual
- **Color:** White only, Black only, or both
- **Date range:** Year/month bounds (from_year/from_month to to_year/to_month) or Unix timestamps

### Opening Name

Human-readable label for a repertoire line. Examples: "Sicilian Defense", "Vienna Game", "London System". Extracted from Lichess study names and normalized (hyphens → spaces, redundant prefixes removed).

## Architecture: Layered Orchestration

The system is organized in horizontal layers from request → response:

1. **HTTP Layer** (`main.py`)
   - Defines FastAPI endpoints (e.g. `/api/analyze`)
   - Parses query parameters into domain objects
   - Delegates to orchestration layer
   - Returns JSON responses

2. **Orchestration Layer** (`pipeline.py`)
   - **`RepertoireAnalysisPipeline`:** Stateful orchestrator that coordinates the full analysis workflow
   - Owns caching logic for repertoires (TTL-based, keyed by study ID set)
   - Defines abstract interfaces (`RepertoireSource`, `GameSource`) that concrete implementations must satisfy
   - Does NOT know about HTTP, Lichess, or Chess.com — all domain concepts

3. **Source Layer** (`sources.py`)
   - Concrete implementations of abstract source interfaces
   - **`LichessRepertoireSource`:** Fetches studies from Lichess and builds `Repertoire` objects
   - **`CacheGameSource`:** Fetches games from the local SQLite cache, applies filters
   - These are adapters at the seams between the pipeline and external systems

4. **Domain Logic Layer**
   - **`repertoire.py`:** Defines `Repertoire`, `RepertoireNode`, `RepertoireBuilder`
   - **`analyzer.py`:** Defines `DeviationAnalyzer`, `DeviationResult`
   - **`game_cache.py`:** SQLite game storage and filtering
   - These modules are system-independent; they don't import HTTP libraries

5. **External Integration Layer**
   - **`lichess.py`:** Async HTTP client for Lichess API (OAuth, study fetching, PGN download)
   - **`chess_com.py`:** Async HTTP client for Chess.com API (archive listing, game fetching, ECO/opening extraction)

## Key Design Patterns

### Dependency Injection

The pipeline accepts abstract source interfaces, not concrete implementations. Callers (main.py) instantiate the concrete sources and inject them:

```python
repertoire_source = LichessRepertoireSource(lichess_token=token)
game_source = CacheGameSource()
pipeline = RepertoireAnalysisPipeline(
    repertoire_source=repertoire_source,
    game_source=game_source,
)
report = await pipeline.analyze(...)
```

This makes the pipeline testable: tests can inject mock sources.

### Repertoire Caching

The pipeline caches built repertoires by study ID set with a 1-hour TTL. Same studies requested within 1 hour reuse the cached tree; after TTL expires, a fresh repertoire is fetched. Balances performance (no rebuild) with data freshness.

### Error Handling

- **Analysis failure (per-game):** Log and continue. One failed game doesn't block the entire analysis.
- **Source failure (study not accessible):** Fail fast at the HTTP layer. Invalid token or inaccessible study is a user error, not a transient issue.

## Data Flows

### Analysis Request Flow

```
HTTP /api/analyze (study_ids, filters, token)
  ↓
HTTP layer validates token, collects study names
  ↓
Instantiate LichessRepertoireSource(token), CacheGameSource()
  ↓
Create RepertoireAnalysisPipeline
  ↓
Call pipeline.analyze(study_ids, study_names, username, filters)
  ↓
Pipeline._get_repertoire() checks cache; if miss, calls source.fetch_repertoire()
  ↓
LichessRepertoireSource.fetch_repertoire()
  ├─ Fetch each study's PGN from Lichess
  ├─ Feed to RepertoireBuilder
  └─ Return built Repertoire (white_tree, black_tree, position_index)
  ↓
Pipeline calls game_source.fetch_games(username, filters)
  ↓
CacheGameSource.fetch_games() queries local SQLite cache with filters
  ↓
Pipeline.analyze() iterates games, calls DeviationAnalyzer.analyze_game() for each
  ↓
Collects deviations into AnalysisReport
  ↓
Return {results: [...], total_games: N, analyzed_with_deviations: M}
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
