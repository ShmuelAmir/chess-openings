"""
Chess Opening Deviation Analyzer - FastAPI Backend
"""
import os
import time
import secrets
import hashlib
import base64
from urllib.parse import urlencode

import chess
import httpx
from fastapi import FastAPI, HTTPException, Query, Header, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from contextlib import contextmanager

from lichess import LichessClient, LichessRateLimitError
from chess_com import ChessComAccountNotFoundError, ChessComClient
from game_cache import get_game_cache
from opening_distribution import DistributionFilters, opening_distribution
from opening_normalizer import OpeningNormalizer
from recall_gaps import RecallFilters
from sources import CacheGameSource
from users import User, fetch_studies_cached, invalidate_analyses, user_for

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


async def user_or_401(token: str) -> User:
    """The token's User; a token Lichess refuses is the user's error (401)."""
    with invalid_token_is_401():
        return await user_for(token)


async def owned_studies_or_401(token: str) -> list[dict]:
    """The token owner's studies; an invalid token is the user's error (401)."""
    with invalid_token_is_401():
        return await fetch_studies_cached(token)


def not_repertoire_view(user: User, owned_studies: list[dict]) -> dict:
    """Every owned study, and whether the User marked it "not repertoire"."""
    excluded = user.exclusions.excluded_studies()
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
    user = await user_or_401(token)
    return not_repertoire_view(user, await owned_studies_or_401(token))


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
    user = await user_or_401(token)
    owned_studies = await owned_studies_or_401(token)

    # Only the user's own studies can be excluded; this also drops stale ids
    owned_ids = {study["id"] for study in owned_studies}
    user.exclusions.set_excluded_studies(set(update.excluded) & owned_ids)
    user.pipeline.invalidate_repertoire()

    return not_repertoire_view(user, owned_studies)


@app.get("/api/chess-com/validate/{username}")
async def validate_chess_com_username(username: str):
    """Check that a Chess.com account exists before we store it."""
    async with ChessComClient() as client:
        try:
            await client.get_archives(username)
        except ChessComAccountNotFoundError as e:
            raise HTTPException(
                status_code=404,
                detail=f"{e}. Use your Chess.com username, not your email.",
            )
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
        user = await user_for(token)
        return await user.pipeline.recall_view(chess_com_username, filters, now=now)


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
        user = await user_for(token)
        return {"gaps": await user.pipeline.practice_queue(chess_com_username, filters, now=now)}


class DrillAttemptIn(BaseModel):
    gap_position_key: str
    passed: bool
    first_miss_position_key: str | None = None


@app.post("/api/drill-attempts", status_code=201)
async def record_drill_attempt(attempt: DrillAttemptIn, authorization: str = Header(...)):
    """
    Record one of the user's finished Drill Attempts: a pass, or a fail with
    the position of its first miss. Drill Attempts never change Recall Gaps.
    """
    user = await user_or_401(authorization.replace("Bearer ", ""))
    try:
        user.drill_attempts.record(
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
    games = await CacheGameSource(get_game_cache()).games(chess_com_username)
    return opening_distribution(games, DistributionFilters(
        time_classes=time_classes,
        rated=rated,
        color={"white": chess.WHITE, "black": chess.BLACK}.get(color),
        from_month=(from_year, from_month),
        to_month=(to_year, to_month),
        from_ts=from_ts,
        to_ts=to_ts,
    ))


# ================== Game Cache Endpoints ==================

@app.get("/api/sync")
async def get_sync(
    chess_com_username: str = Query(...),
    authorization: str = Header(...),
):
    """The Sync's state: progress, each source's status and the last result."""
    token = authorization.replace("Bearer ", "")
    return (await user_or_401(token)).sync.status(chess_com_username)


@app.post("/api/sync")
async def start_sync(
    chess_com_username: str = Query(...),
    authorization: str = Header(...),
):
    """
    Start a Sync of both sources and return its state; poll GET /api/sync
    for progress. While the user's Sync runs for another account, this
    account's runs after it.
    """
    token = authorization.replace("Bearer ", "")
    sync = (await user_or_401(token)).sync
    sync.start(chess_com_username)
    return sync.status(chess_com_username)


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
