# ADR-0001: Pipeline Orchestration with Dependency Injection

**Date:** 2026-05-08  
**Status:** Accepted (repertoire caching amended 2026-10-01, recall view assembly amended 2026-10-09, see below)  
**Context:** Backend analysis workflow orchestration

## Problem

The `/api/analyze` endpoint in `main.py` was monolithic (116 lines) and tightly coupled:

- Fetched studies from Lichess
- Built repertoire tree
- Fetched games from cache
- Ran analysis
- Returned results

**Issues:**

1. **Tight coupling:** Lichess client, game cache, and analysis logic were interleaved in the HTTP handler
2. **Poor testability:** Couldn't test analysis orchestration without FastAPI and real APIs
3. **No caching:** Repertoires rebuilt from scratch on every request, even for identical study IDs
4. **Scattered logic:** Changing analysis flow required edits to main.py, not a dedicated orchestration module

## Solution

Introduced a **`RepertoireAnalysisPipeline`** class that orchestrates the workflow via **dependency injection**:

1. **Abstract interfaces** define the seams:
   - `RepertoireSource`: "How do I get a repertoire?"
   - `GameSource`: "How do I get games?"

2. **Concrete implementations** are injected, not hardcoded:
   - `LichessRepertoireSource` (fetches from Lichess)
   - `CacheGameSource` (fetches from local SQLite)

3. **Pipeline owns orchestration:**
   - Caches repertoires by study ID set (1-hour TTL)
   - Coordinates fetch → build → analyze → report
   - Treats individual game analysis failures as non-fatal (log and continue)

4. **HTTP handler becomes thin:**
   - Validates token
   - Instantiates sources and pipeline
   - Returns JSON response
   - No orchestration logic

```python
# Old (monolithic)
async def analyze_games(...):
    # 116 lines of mixing HTTP, Lichess, cache, analysis logic

# New (layered)
async def analyze_games(...):
    token = authorization.replace("Bearer ", "")

    # Validate token
    # Collect study names

    # Create sources
    repertoire_source = LichessRepertoireSource(lichess_token=token)
    game_source = CacheGameSource()

    # Create pipeline
    pipeline = RepertoireAnalysisPipeline(repertoire_source, game_source)

    # Execute
    report = await pipeline.analyze(study_ids, study_names, username, filters)

    # Return
    return {...}
```

## Tradeoffs

**Pros:**

- **Locality:** All analysis orchestration lives in `pipeline.py`
- **Testability:** Tests can inject mock sources; no HTTP or API calls needed
- **Caching:** Repertoires cached by study ID set with TTL — repeated analyses are fast
- **Extensibility:** New implementations of `RepertoireSource` or `GameSource` drop in without changing the pipeline
- **Clarity:** HTTP layer is thin; orchestration layer is focused

**Cons:**

- **More boilerplate:** Sources must implement abstract interfaces (small cost)
- **Indirection:** Readers must follow interfaces to understand concrete behavior
- **Cache invalidation:** TTL-based caching is simple but coarse (can't invalidate on study edits)

## Risks & Mitigations

**Risk:** Cache staleness if user edits a Lichess study.  
**Mitigation:** 1-hour TTL is reasonable for most use cases. Could add explicit "refresh repertoire" endpoint later if needed.

**Risk:** If game analysis fails, we skip it silently (log only).  
**Mitigation:** Intentional — one bad game shouldn't block the entire analysis. Caller can monitor logs for failures.

## Future Work

- **Candidate 5 (deepen API clients):** Move PGN parsing and opening name normalization into `LichessRepertoireSource`, so it builds the tree directly (not via raw PGN strings)
- **Cache key extension:** Include a content hash of study PGN to detect edits, not just study ID

## Amendment (2026-10-01): one Repertoire per user

The Repertoire is now every study the user owns on Lichess (issue #21), so the cache is no longer keyed by a study ID set. The pipeline caches "the user's Repertoire" with the same 1-hour TTL, and a study created on Lichess joins at the next rebuild. `RepertoireSource.fetch_repertoire()` takes no study arguments, `LichessRepertoireSource` lists the user's owned studies on each rebuild, `main.py` keeps one pipeline per Lichess user so the cache is reused across requests, and `pipeline.analyze(username, filters)` no longer takes study ids or names. The rest of this decision stands.

## Amendment (2026-10-01): recall view replaces per-game analysis

The pipeline's `analyze` (one row per game via `DeviationAnalyzer`) is replaced by `pipeline.recall_view(username, filters)` (issue #22). It fetches every cached game, walks each through the Repertoire, and hands the walk records to the pure Recall Gap aggregator (`recall_gaps.py`), which applies the Game Filters itself, so that later rules can read all games while showing only the filtered ones. `/api/analyze` and `analyzer.py` are removed; `/api/recall-view` serves the view. The rest of this decision stands.

## Amendment (2026-10-09): the pipeline returns the complete recall view

`pipeline.recall_view(username, filters)` now returns the whole recall view (issue #59): the Repertoire's studies — name, opening name, color and number of Recall Gaps, sorted by opening name — beside the ranked Recall Gaps and the totals, and each gap's studies carry their name and deep link. Study names come from the Repertoire (`Repertoire.study_names`, filled by `RepertoireBuilder`), so the handler no longer lists the user's studies on every request, and a rename on Lichess is a Repertoire change that shows at the next rebuild. The handler serialises the view as is: the view dataclasses in `recall_gaps.py` (`RecallView`, `StudyView`, `RecallGap`, `Totals` and those they hold) are the wire contract, so a field added to them is a field added to the response. The date-range presets are built by `RecallFilters.for_date_range`, and `study_url` sits in `repertoire.py`. `/api/recall-view` and `/api/practice-session` no longer check the token on each request — a revoked token keeps getting the cached view until the Repertoire is next rebuilt — but still answer an upstream 401/403 from the Repertoire fetch with `401 "Invalid Lichess token"`. `/api/practice-session` returns the queued gaps in the recall view's shape, without `due_at`. The rest of this decision stands.
