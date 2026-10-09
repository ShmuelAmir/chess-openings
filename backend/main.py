"""
Chess Opening Deviation Analyzer - FastAPI Backend
"""
import os
import time
import asyncio
import secrets
import hashlib
import base64
from urllib.parse import urlencode

import httpx
from fastapi import FastAPI, HTTPException, Query, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contextlib import contextmanager

from lichess import LichessClient, LichessRateLimitError
from chess_com import ChessComClient
from game_cache import get_game_cache
from exclusions import get_exclusion_store
from drill_attempts import get_drill_attempt_store
from opening_distribution import opening_distribution
from opening_normalizer import OpeningNormalizer
from pipeline import RepertoireAnalysisPipeline, GameFilters
from recall_gaps import RecallFilters
from sources import LichessRepertoireSource, CacheGameSource
from sync import ChessComSync, RepertoireSyncLog, Sync

app = FastAPI(title="Chess Opening Analyzer")

# CORS for local development
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
LICHESS_CLIENT_ID = os.getenv("LICHESS_CLIENT_ID", "chess-opening-analyzer")
REDIRECT_URI = os.getenv("REDIRECT_URI", "http://localhost:5173/callback")

# In-memory PKCE store (for demo; in production use Redis or similar)
pkce_store: dict[str, str] = {}

# Short-lived cache of a token's studies, so repeated page loads / duplicate
# frontend requests don't each hit the Lichess API (which rate-limits hard).
STUDIES_CACHE_TTL = 60  # seconds
_studies_cache: dict[str, tuple[float, list[dict]]] = {}
_studies_locks: dict[str, asyncio.Lock] = {}


def _token_key(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


async def fetch_studies_cached(token: str) -> list[dict]:
    """
    Return the token owner's studies, using a short-lived cache.

    Concurrent callers for the same token share a single upstream request.
    """
    key = _token_key(token)
    lock = _studies_locks.setdefault(key, asyncio.Lock())

    async with lock:
        cached = _studies_cache.get(key)
        if cached and time.monotonic() - cached[0] < STUDIES_CACHE_TTL:
            return cached[1]

        async with LichessClient(token=token) as client:
            account = await client.get_account()
            studies = await client.get_user_studies(account["username"])

        _studies_cache[key] = (time.monotonic(), studies)
        return studies


# One pipeline per Lichess user, so their Repertoire stays cached between requests.
_pipelines: dict[str, RepertoireAnalysisPipeline] = {}


def pipeline_for(token: str) -> RepertoireAnalysisPipeline:
    """The analysis pipeline holding this user's cached Repertoire."""
    key = _token_key(token)
    if key not in _pipelines:
        _pipelines[key] = RepertoireAnalysisPipeline(
            repertoire_source=LichessRepertoireSource(
                lichess_token=token,
                list_studies=lambda: fetch_studies_cached(token),
                excluded_studies=get_exclusion_store().excluded_studies,
            ),
            game_source=CacheGameSource(get_game_cache()),
            drill_attempts=get_drill_attempt_store().attempts,
        )
    return _pipelines[key]


def invalidate_analyses():
    """Drop every pipeline's last analysis, after the cached games changed."""
    for pipeline in _pipelines.values():
        pipeline.invalidate_games()


# One Sync per Lichess user and Chess.com account
REPERTOIRE_FRESH_SECONDS = 30
_syncs: dict[tuple[str, str], Sync] = {}


def sync_for(token: str, chess_com_username: str) -> Sync:
    """The Sync of this user's Chess.com games and Lichess Repertoire."""
    key = (_token_key(token), chess_com_username.lower())
    if key not in _syncs:
        pipeline = pipeline_for(token)

        async def refresh_repertoire() -> bool:
            # List the studies afresh, so new ones join the Repertoire; a
            # Repertoire built moments ago (e.g. by the page that just
            # opened) is fresh enough, and spares the Lichess rate limit
            _studies_cache.pop(_token_key(token), None)
            return await pipeline.refresh_repertoire(fresh_within=REPERTOIRE_FRESH_SECONDS)

        def games_last_success():
            status = get_game_cache().get_sync_status(chess_com_username)
            return status["last_sync_at"] if status else None

        games_sync = ChessComSync(get_game_cache(), client=ChessComClient)

        async def sync_games(on_month):
            try:
                return await games_sync.sync(chess_com_username, on_month)
            except httpx.HTTPStatusError as e:
                # Chess.com answers unknown players with 404 or 410 Gone.
                if e.response.status_code in (404, 410):
                    raise RuntimeError(
                        f"No Chess.com account named '{chess_com_username}'"
                    ) from e
                raise

        _syncs[key] = Sync(
            sync_games=sync_games,
            refresh_repertoire=refresh_repertoire,
            games_last_success=games_last_success,
            repertoire_log=RepertoireSyncLog(user=_token_key(token)),
            on_games_changed=invalidate_analyses,
            previous_gap_statuses=lambda: pipeline.last_gap_statuses(chess_com_username),
            gap_statuses=lambda: pipeline.gap_statuses(chess_com_username),
        )
    return _syncs[key]


def sync_view(token: str, chess_com_username: str) -> dict:
    """The Sync's state, with how many games are cached."""
    return {
        **sync_for(token, chess_com_username).status(),
        "cached_games": get_game_cache().count_games(chess_com_username),
    }


@app.exception_handler(LichessRateLimitError)
async def lichess_rate_limit_handler(request: Request, exc: LichessRateLimitError):
    """Surface Lichess rate limiting as a 429 instead of a 500."""
    return JSONResponse(
        status_code=429,
        content={"detail": str(exc)},
        headers={"Retry-After": str(exc.retry_after)},
    )


@app.exception_handler(httpx.HTTPStatusError)
async def upstream_error_handler(request: Request, exc: httpx.HTTPStatusError):
    """Mirror upstream 4xx errors instead of reporting them as our own 500."""
    status = exc.response.status_code
    if 400 <= status < 500:
        return JSONResponse(
            status_code=status,
            content={"detail": f"Upstream request failed: {exc}"},
        )
    return JSONResponse(
        status_code=502,
        content={"detail": f"Upstream request failed: {exc}"},
    )


def generate_pkce():
    """Generate PKCE code verifier and challenge."""
    code_verifier = secrets.token_urlsafe(64)
    code_challenge = base64.urlsafe_b64encode(
        hashlib.sha256(code_verifier.encode()).digest()
    ).decode().rstrip("=")
    return code_verifier, code_challenge


@app.get("/api/auth/lichess")
async def lichess_auth():
    """Start Lichess OAuth flow - returns URL for frontend to redirect to."""
    code_verifier, code_challenge = generate_pkce()
    state = secrets.token_urlsafe(32)
    
    # Store verifier for callback
    pkce_store[state] = code_verifier
    
    params = {
        "response_type": "code",
        "client_id": LICHESS_CLIENT_ID,
        "redirect_uri": REDIRECT_URI,
        "scope": "study:read",
        "code_challenge_method": "S256",
        "code_challenge": code_challenge,
        "state": state,
    }
    
    auth_url = f"https://lichess.org/oauth?{urlencode(params)}"
    return {"auth_url": auth_url, "state": state}


@app.post("/api/auth/callback")
async def lichess_callback(code: str = Query(...), state: str = Query(...)):
    """Exchange authorization code for access token."""
    code_verifier = pkce_store.pop(state, None)
    if not code_verifier:
        raise HTTPException(status_code=400, detail="Invalid state parameter")
    
    async with LichessClient() as client:
        token_data = await client.exchange_token(
            code=code,
            code_verifier=code_verifier,
            redirect_uri=REDIRECT_URI,
            client_id=LICHESS_CLIENT_ID,
        )
    
    return token_data


@app.get("/api/lichess/me")
async def get_lichess_user(authorization: str = Header(...)):
    """Get current Lichess user info."""
    token = authorization.replace("Bearer ", "")
    async with LichessClient(token=token) as client:
        return await client.get_account()


@contextmanager
def invalid_token_is_401():
    """Lichess refusing the token upstream (401/403) is the user's error (401)."""
    try:
        yield
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (401, 403):
            raise HTTPException(status_code=401, detail="Invalid Lichess token")
        raise


async def owned_studies_or_401(token: str) -> list[dict]:
    """The token owner's studies; an invalid token is the user's error (401)."""
    with invalid_token_is_401():
        return await fetch_studies_cached(token)


def not_repertoire_view(owned_studies: list[dict]) -> dict:
    """Every owned study, and whether it is marked "not repertoire"."""
    excluded = get_exclusion_store().excluded_studies()
    return {
        "studies": sorted(
            (
                {
                    "id": study["id"],
                    "name": study["name"],
                    "opening_name": OpeningNormalizer.normalize(study["name"]),
                    "excluded": study["id"] in excluded,
                }
                for study in owned_studies
            ),
            key=lambda study: study["opening_name"].lower(),
        ),
    }


@app.get("/api/not-repertoire")
async def get_not_repertoire(authorization: str = Header(...)):
    """The "not repertoire" exclusion list, over every study the user owns."""
    token = authorization.replace("Bearer ", "")
    return not_repertoire_view(await owned_studies_or_401(token))


class NotRepertoireUpdate(BaseModel):
    excluded: list[str]


@app.put("/api/not-repertoire")
async def update_not_repertoire(
    update: NotRepertoireUpdate,
    authorization: str = Header(...),
):
    """
    Replace the "not repertoire" exclusion list. The Repertoire is rebuilt
    without the excluded studies on the next request.
    """
    token = authorization.replace("Bearer ", "")
    owned_studies = await owned_studies_or_401(token)

    # Only the user's own studies can be excluded; this also drops stale ids
    owned_ids = {study["id"] for study in owned_studies}
    get_exclusion_store().set_excluded_studies(set(update.excluded) & owned_ids)
    for pipeline in _pipelines.values():
        pipeline.invalidate_repertoire()

    return not_repertoire_view(owned_studies)


@app.get("/api/chess-com/validate/{username}")
async def validate_chess_com_username(username: str):
    """Check that a Chess.com account exists before we store it."""
    async with ChessComClient() as client:
        try:
            await client.get_archives(username)
        except httpx.HTTPStatusError as e:
            # Chess.com answers unknown players with 404 or 410 Gone.
            if e.response.status_code in (404, 410):
                raise HTTPException(
                    status_code=404,
                    detail=f"No Chess.com account named '{username}'. Use your Chess.com username, not your email.",
                )
            raise
    return {"username": username, "valid": True}


def recall_filters(
    time_classes: list[str] | None,
    date_range: str,
    rated_only: bool,
    studies: list[str] | None,
    now: int,
) -> RecallFilters:
    """The recall view's Game Filters from its query parameters."""
    try:
        return RecallFilters.for_date_range(
            date_range,
            now=now,
            time_classes=time_classes,
            rated_only=rated_only,
            studies=studies,
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))


@app.get("/api/recall-view")
async def recall_view(
    chess_com_username: str = Query(...),
    time_classes: list[str] = Query(None),
    date_range: str = Query("all"),
    rated_only: bool = Query(False),
    studies: list[str] = Query(None),
    authorization: str = Header(...),
):
    """
    The recall view under the Game Filters: the Repertoire's studies, the
    ranked Recall Gaps and the totals of the user's cached games.
    """
    token = authorization.replace("Bearer ", "")
    now = int(time.time())
    filters = recall_filters(time_classes, date_range, rated_only, studies, now)

    with invalid_token_is_401():
        return await pipeline_for(token).recall_view(chess_com_username, filters, now=now)


@app.get("/api/practice-session")
async def practice_session(
    chess_com_username: str = Query(...),
    time_classes: list[str] = Query(None),
    date_range: str = Query("all"),
    rated_only: bool = Query(False),
    studies: list[str] = Query(None),
    authorization: str = Header(...),
):
    """
    The practice-session queue: the due Open Recall Gaps among those the
    Game Filters show, in ranking order, each as the recall view shows it.
    """
    token = authorization.replace("Bearer ", "")
    now = int(time.time())
    filters = recall_filters(time_classes, date_range, rated_only, studies, now)

    with invalid_token_is_401():
        return {"gaps": await pipeline_for(token).practice_queue(chess_com_username, filters, now=now)}


class DrillAttemptIn(BaseModel):
    gap_position_key: str
    passed: bool
    first_miss_position_key: str | None = None


@app.post("/api/drill-attempts", status_code=201)
async def record_drill_attempt(attempt: DrillAttemptIn):
    """
    Record a finished Drill Attempt: a pass, or a fail with the position of
    its first miss. Drill Attempts never change Recall Gaps.
    """
    try:
        get_drill_attempt_store().record(
            attempt.gap_position_key,
            passed=attempt.passed,
            first_miss_position_key=attempt.first_miss_position_key,
            at=int(time.time()),
        )
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    return {"recorded": True}


@app.post("/api/opening-stats")
async def opening_stats(
    chess_com_username: str = Query(...),
    from_year: int = Query(...),
    from_month: int = Query(...),
    to_year: int = Query(...),
    to_month: int = Query(...),
    from_ts: int = Query(None),
    to_ts: int = Query(None),
    time_classes: list[str] = Query(None),
    rated: bool = Query(None),
    color: str = Query(None),  # "white", "black", or None for both
):
    """The Opening Distribution of the user's cached Chess.com games."""
    games = get_game_cache().get_cached_games(
        username=chess_com_username,
        time_classes=time_classes,
        rated=rated,
        color=color,
        from_year=from_year,
        from_month=from_month,
        to_year=to_year,
        to_month=to_month,
        from_ts=from_ts,
        to_ts=to_ts,
    )
    return opening_distribution(games, chess_com_username)


# ================== Game Cache Endpoints ==================

@app.get("/api/sync")
async def get_sync(
    chess_com_username: str = Query(...),
    authorization: str = Header(...),
):
    """The Sync's state: progress, each source's status and the last result."""
    token = authorization.replace("Bearer ", "")
    return sync_view(token, chess_com_username)


@app.post("/api/sync")
async def start_sync(
    chess_com_username: str = Query(...),
    authorization: str = Header(...),
):
    """
    Start a Sync of both sources (unless one is running) and return its
    state; poll GET /api/sync for progress.
    """
    token = authorization.replace("Bearer ", "")
    sync_for(token, chess_com_username).start()
    return sync_view(token, chess_com_username)


@app.delete("/api/chess-com/cache/{username}")
async def clear_cache(username: str):
    """Clear cached games for a user."""
    cache = get_game_cache()
    cache.clear_user_cache(username)
    invalidate_analyses()
    return {"message": f"Cache cleared for {username}"}


# Serve frontend static files in production
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
