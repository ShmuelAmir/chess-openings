"""
Lichess API Client
"""
import httpx
from typing import Optional


class LichessClient:
    """Client for Lichess API with OAuth support."""
    
    BASE_URL = "https://lichess.org"
    
    def __init__(self, token: Optional[str] = None):
        self.token = token
        self._client: Optional[httpx.AsyncClient] = None
    
    async def __aenter__(self):
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        self._client = httpx.AsyncClient(
            base_url=self.BASE_URL,
            headers=headers,
            timeout=30.0,
        )
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self._client:
            await self._client.aclose()
    
    async def exchange_token(
        self,
        code: str,
        code_verifier: str,
        redirect_uri: str,
        client_id: str,
    ) -> dict:
        """Exchange authorization code for access token."""
        response = await self._client.post(
            "/api/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "client_id": client_id,
                "code_verifier": code_verifier,
            },
        )
        response.raise_for_status()
        return response.json()
    
    async def get_account(self) -> dict:
        """Get current user's account info."""
        response = await self._client.get("/api/account")
        response.raise_for_status()
        return response.json()
    
    async def get_user_studies(self, username: str) -> list[dict]:
        """Get list of studies for a user (returns ndjson)."""
        studies = []
        async with self._client.stream(
            "GET",
            f"/api/study/by/{username}",
            headers={"Accept": "application/x-ndjson"},
        ) as response:
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    import json
                    studies.append(json.loads(line))
        return studies
    
    async def get_study_pgn(self, study_id: str) -> str:
        """Get PGN content of a study."""
        response = await self._client.get(
            f"/api/study/{study_id}.pgn",
            headers={"Accept": "application/x-chess-pgn"},
        )
        response.raise_for_status()
        return response.text
