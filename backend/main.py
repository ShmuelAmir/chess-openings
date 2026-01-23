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

from lichess import LichessClient
from chess_com import ChessComClient
from repertoire import RepertoireBuilder
from analyzer import DeviationAnalyzer

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


@app.get("/api/chess-com/games/{username}")
async def get_chess_com_games(
    username: str,
    year: int = Query(...),
    month: int = Query(...),
    time_class: str = Query(None),  # bullet, blitz, rapid, daily
    rated: bool = Query(None),
):
    """Fetch games from Chess.com for a specific month."""
    async with ChessComClient() as client:
        games = await client.get_games(
            username=username,
            year=year,
            month=month,
            time_class=time_class,
            rated=rated,
        )
        return {"games": games}


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
            pgn = await lichess.get_study_pgn(study_id)
            study_name = next(
                (s["name"] for s in studies if s["id"] == study_id),
                "Unknown Opening"
            )
            collected_study_names.append(study_name)
            repertoire_builder.add_study(pgn, study_name, study_name)
    
    repertoire = repertoire_builder.build()
    
    # Use study names for pre-filtering Chess.com games by opening
    opening_filters = study_names if study_names else collected_study_names
    
    # Fetch Chess.com games for the date range (pre-filtered by opening name from eco URL)
    async with ChessComClient() as chess_com:
        games, total_games = await chess_com.get_games_for_range(
            username=chess_com_username,
            from_year=from_year,
            from_month=from_month,
            to_year=to_year,
            to_month=to_month,
            time_classes=time_classes,
            rated=rated,
            color=color,
            opening_filters=opening_filters,
        )
    
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


# Serve frontend static files in production
if os.path.exists("static"):
    app.mount("/", StaticFiles(directory="static", html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
