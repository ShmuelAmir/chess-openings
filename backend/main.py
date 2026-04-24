"""
Chess Opening Deviation Analyzer - FastAPI Backend
"""
import os
import secrets
import hashlib
import base64
from urllib.parse import urlencode

from fastapi import FastAPI, HTTPException, Query, Header
from fastapi.staticfiles import StaticFiles
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

from datetime import datetime

from lichess import LichessClient
from chess_com import ChessComClient
from repertoire import RepertoireBuilder
from analyzer import DeviationAnalyzer
from game_cache import get_game_cache

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


@app.get("/api/lichess/studies")
async def get_lichess_studies(authorization: str = Header(...)):
    """Get list of user's Lichess studies."""
    token = authorization.replace("Bearer ", "")
    async with LichessClient(token=token) as client:
        account = await client.get_account()
        username = account["username"]
        studies = await client.get_user_studies(username)
        return {"studies": studies}


@app.get("/api/lichess/study/{study_id}")
async def get_study_pgn(study_id: str, authorization: str = Header(...)):
    """Get PGN content of a specific study."""
    token = authorization.replace("Bearer ", "")
    async with LichessClient(token=token) as client:
        pgn = await client.get_study_pgn(study_id)
        return {"pgn": pgn}


@app.get("/api/chess-com/archives/{username}")
async def get_chess_com_archives(username: str):
    """Get available game archives for a Chess.com user."""
    async with ChessComClient() as client:
        archives = await client.get_archives(username)
        return {"archives": archives}


@app.post("/api/analyze")
async def analyze_games(
    study_ids: list[str] = Query(...),
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
    study_names: list[str] = Query(None),
    authorization: str = Header(...),
):
    """Analyze games against repertoire and find deviations."""
    token = authorization.replace("Bearer ", "")
    
    # Fetch studies and build repertoire
    repertoire_builder = RepertoireBuilder()
    collected_study_names = []
    
    async with LichessClient(token=token) as lichess:
        account = await lichess.get_account()
        studies = await lichess.get_user_studies(account["username"])
        
        for study_id in study_ids:
            try:
                pgn = await lichess.get_study_pgn(study_id)
            except Exception as e:
                study_name = next(
                    (s["name"] for s in studies if s["id"] == study_id),
                    study_id
                )
                raise HTTPException(
                    status_code=403,
                    detail=f"Cannot access study '{study_name}' ({study_id}). Make sure the study is public, unlisted, or you are the owner."
                )
            study_name = next(
                (s["name"] for s in studies if s["id"] == study_id),
                "Unknown Opening"
            )
            collected_study_names.append(study_name)
            repertoire_builder.add_study(
                pgn,
                study_name,
                study_name,
                study_id,
            )
    
    repertoire = repertoire_builder.build()
    
    # Use actual opening names from the repertoire for filtering (not study names)
    # Extract all unique opening names that appear in the repertoire
    def extract_opening_names(node):
        """Recursively extract all opening names from the repertoire tree."""
        names = set()
        if node.opening_name:
            names.add(node.opening_name)
        for child in node.children.values():
            names.update(extract_opening_names(child))
        return names
    
    repertoire_opening_names = extract_opening_names(repertoire.white_tree)
    repertoire_opening_names.update(extract_opening_names(repertoire.black_tree))
    
    # Get games from cache (filtered by basic criteria)
    cache = get_game_cache()
    all_games = cache.get_cached_games(
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
    
    total_games = len(all_games)
    
    # Don't pre-filter by opening name - the DeviationAnalyzer will check
    # if the game's moves match any position in our repertoire tree.
    # This is more accurate than string-matching opening names.
    games = all_games
    
    # Analyze each game against the full repertoire tree
    analyzer = DeviationAnalyzer(repertoire)
    results = []
    
    for game in games:
        result = analyzer.analyze_game(game, chess_com_username)
        if result:
            # Add the Chess.com opening name to the result
            result["chess_com_opening"] = game.get("opening_name", "")
            results.append(result)
    
    return {
        "results": results,
        "total_games": total_games,
        "filtered_by_opening": len(games),
        "analyzed_with_deviations": len(results),
    }


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
    """Get opening distribution statistics from cached Chess.com games."""
    from collections import defaultdict
    
    # Get games from cache (filtered by basic criteria)
    cache = get_game_cache()
    games = cache.get_cached_games(
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
    
    username_lower = chess_com_username.lower()
    
    # Aggregate statistics
    opening_counts = defaultdict(int)
    opening_wins = defaultdict(int)
    opening_draws = defaultdict(int)
    opening_losses = defaultdict(int)
    category_counts = defaultdict(int)
    time_series = defaultdict(lambda: defaultdict(int))  # {month: {opening: count}}
    
    for game in games:
        opening_name = game.get("opening_name", "") or "Unknown"
        if not opening_name:
            opening_name = "Unknown"
        
        # Count openings
        opening_counts[opening_name] += 1
        
        # Determine result for user
        is_white = game.get("white", "").lower() == username_lower
        result = game.get("result", "")
        
        if result == "win":
            if is_white:
                opening_wins[opening_name] += 1
            else:
                opening_losses[opening_name] += 1
        elif result == "lose" or result == "checkmated" or result == "timeout" or result == "resigned" or result == "abandoned":
            if is_white:
                opening_losses[opening_name] += 1
            else:
                opening_wins[opening_name] += 1
        else:
            # Draw or other result
            opening_draws[opening_name] += 1
        
        # Categorize opening (e4, d4, c4, Nf3, etc.)
        category = categorize_opening(opening_name)
        category_counts[category] += 1
        
        # Time series data (by month)
        date_ts = game.get("date")
        if date_ts:
            dt = datetime.fromtimestamp(date_ts)
            month_key = f"{dt.year}-{dt.month:02d}"
            time_series[month_key][opening_name] += 1
    
    # Build response
    # All openings by count (no limit)
    all_openings = sorted(
        [(name, count) for name, count in opening_counts.items()],
        key=lambda x: x[1],
        reverse=True
    )
    
    # Opening performance data
    opening_performance = []
    for name, count in all_openings:
        wins = opening_wins.get(name, 0)
        draws = opening_draws.get(name, 0)
        losses = opening_losses.get(name, 0)
        total = wins + draws + losses
        win_rate = (wins / total * 100) if total > 0 else 0
        opening_performance.append({
            "opening": name,
            "games": count,
            "wins": wins,
            "draws": draws,
            "losses": losses,
            "win_rate": round(win_rate, 1),
        })
    
    # Category breakdown
    categories = [
        {"category": cat, "count": count}
        for cat, count in sorted(category_counts.items(), key=lambda x: x[1], reverse=True)
    ]
    
    # Time series for top 5 openings
    top_5_names = [name for name, _ in all_openings[:5]]
    trends = []
    for month_key in sorted(time_series.keys()):
        entry = {"month": month_key}
        for opening_name in top_5_names:
            entry[opening_name] = time_series[month_key].get(opening_name, 0)
        trends.append(entry)
    
    return {
        "total_games": len(games),
        "unique_openings": len(opening_counts),
        "top_openings": opening_performance,
        "categories": categories,
        "trends": trends,
        "top_opening_names": top_5_names,
    }


def categorize_opening(opening_name: str) -> str:
    """Categorize an opening by its first move family."""
    name_lower = opening_name.lower()
    
    # e4 openings
    e4_keywords = ["sicilian", "italian", "spanish", "ruy lopez", "french", "caro-kann", 
                   "scandinavian", "alekhine", "pirc", "modern", "king's pawn", "scotch",
                   "petroff", "petrov", "vienna", "bishop's opening", "center game",
                   "king's gambit", "philidor", "two knights"]
    
    # d4 openings
    d4_keywords = ["queen's gambit", "king's indian", "slav", "gruenfeld", "grunfeld",
                   "nimzo", "queen's indian", "dutch", "london", "trompowsky", "torre",
                   "colle", "catalan", "bogo", "benoni", "semi-slav"]
    
    # c4 openings
    c4_keywords = ["english"]
    
    # Nf3 openings
    nf3_keywords = ["reti", "réti"]
    
    for kw in e4_keywords:
        if kw in name_lower:
            return "e4 Openings"
    
    for kw in d4_keywords:
        if kw in name_lower:
            return "d4 Openings"
    
    for kw in c4_keywords:
        if kw in name_lower:
            return "c4 Openings"
    
    for kw in nf3_keywords:
        if kw in name_lower:
            return "Nf3 Openings"
    
    return "Other"


# ================== Game Cache Endpoints ==================

@app.get("/api/chess-com/cache-status/{username}")
async def get_cache_status(username: str):
    """Get cache status for a Chess.com user."""
    cache = get_game_cache()
    sync_status = cache.get_sync_status(username)
    game_count = cache.count_games(username)
    
    return {
        "username": username,
        "cached_games": game_count,
        "last_sync_at": sync_status["last_sync_at"] if sync_status else None,
        "last_synced_year": sync_status["last_synced_year"] if sync_status else None,
        "last_synced_month": sync_status["last_synced_month"] if sync_status else None,
    }


@app.post("/api/chess-com/sync/{username}")
async def sync_chess_com_games(username: str):
    """
    Sync games from Chess.com to local cache.
    
    Only fetches new games since the last sync.
    Always re-fetches the current month (games may still be played).
    """
    cache = get_game_cache()
    sync_status = cache.get_sync_status(username)
    
    # Get current date
    now = datetime.now()
    current_year, current_month = now.year, now.month
    
    # Determine starting point for sync
    async with ChessComClient() as client:
        # Get available archives from Chess.com
        try:
            archives = await client.get_archives(username)
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"User '{username}' not found on Chess.com")
        
        if not archives:
            return {
                "new_games": 0,
                "total_games": 0,
                "message": "No games found on Chess.com"
            }
        
        # Parse archive URLs to get (year, month) tuples
        # Archive URL format: https://api.chess.com/pub/player/{username}/games/2024/01
        available_months = []
        for archive_url in archives:
            parts = archive_url.rstrip('/').split('/')
            if len(parts) >= 2:
                try:
                    year = int(parts[-2])
                    month = int(parts[-1])
                    available_months.append((year, month))
                except ValueError:
                    continue
        
        if not available_months:
            return {
                "new_games": 0,
                "total_games": 0,
                "message": "Could not parse archive dates"
            }
        
        # Get already cached months
        cached_months = cache.get_cached_months(username)
        
        # Determine which months to fetch:
        # 1. All months not yet cached
        # 2. Always re-fetch current month (new games may exist)
        months_to_fetch = []
        for year, month in available_months:
            is_current_month = (year == current_year and month == current_month)
            is_cached = (year, month) in cached_months
            
            if not is_cached or is_current_month:
                months_to_fetch.append((year, month))
        
        # Fetch games for each month
        new_games_count = 0
        for year, month in months_to_fetch:
            try:
                games = await client.get_all_games_for_month(username, year, month)
                if games:
                    cache.save_games(username, games, year, month)
                    new_games_count += len(games)
            except Exception as e:
                # Log but continue with other months
                print(f"Error fetching {year}/{month} for {username}: {e}")
                continue
    
    # Update sync status
    cache.update_sync_status(username, current_year, current_month)
    
    total_games = cache.count_games(username)
    
    return {
        "new_games": new_games_count,
        "total_games": total_games,
        "months_synced": len(months_to_fetch),
        "message": f"Synced {new_games_count} games from {len(months_to_fetch)} months"
    }


@app.get("/api/chess-com/cached-games/{username}")
async def get_cached_games(
    username: str,
    time_classes: list[str] = Query(None),
    rated: bool = Query(None),
    color: str = Query(None),
    from_year: int = Query(None),
    from_month: int = Query(None),
    to_year: int = Query(None),
    to_month: int = Query(None),
):
    """Get cached games for a user with optional filters."""
    cache = get_game_cache()
    
    games = cache.get_cached_games(
        username=username,
        time_classes=time_classes,
        rated=rated,
        color=color,
        from_year=from_year,
        from_month=from_month,
        to_year=to_year,
        to_month=to_month,
    )
    
    # Remove internal fields before returning
    for game in games:
        game.pop("fetched_at", None)
    
    return {
        "games": games,
        "total": len(games),
    }


@app.delete("/api/chess-com/cache/{username}")
async def clear_cache(username: str):
    """Clear cached games for a user."""
    cache = get_game_cache()
    cache.clear_user_cache(username)
    return {"message": f"Cache cleared for {username}"}


# Serve frontend static files in production
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
