"""
Lichess API Client
"""
import asyncio
import httpx
from typing import Optional
from opening_normalizer import OpeningNormalizer


class LichessRateLimitError(Exception):
    """Raised when Lichess rate-limits us (HTTP 429)."""

    def __init__(self, retry_after: int = 60):
        self.retry_after = retry_after
        super().__init__(
            f"Lichess rate limit reached. Retry in {retry_after} seconds."
        )


def _retry_after_seconds(response: httpx.Response, default: int = 60) -> int:
    """Parse the Retry-After header, falling back to a sane default."""
    raw = response.headers.get("Retry-After")
    if raw is None:
        return default
    try:
        return max(1, int(float(raw)))
    except ValueError:
        return default


class LichessClient:
    """Client for Lichess API with OAuth support."""

    BASE_URL = "https://lichess.org"

    # Lichess asks clients to back off for a while on 429. We only wait
    # inline for short backoffs; anything longer is surfaced to the caller.
    MAX_INLINE_RETRY_WAIT = 5

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
    
    async def _get(self, url: str, **kwargs) -> httpx.Response:
        """GET with a single short retry when Lichess rate-limits us."""
        response = await self._client.get(url, **kwargs)
        if response.status_code == 429:
            wait = _retry_after_seconds(response)
            if wait > self.MAX_INLINE_RETRY_WAIT:
                raise LichessRateLimitError(wait)
            await asyncio.sleep(wait)
            response = await self._client.get(url, **kwargs)
            if response.status_code == 429:
                raise LichessRateLimitError(_retry_after_seconds(response))
        return response

    async def get_account(self) -> dict:
        """Get current user's account info."""
        response = await self._get("/api/account")
        response.raise_for_status()
        return response.json()

    async def get_user_studies(self, username: str) -> list[dict]:
        """Get list of studies for a user (returns ndjson)."""
        import json

        studies = []
        async with self._client.stream(
            "GET",
            f"/api/study/by/{username}",
            headers={"Accept": "application/x-ndjson"},
        ) as response:
            if response.status_code == 429:
                await response.aread()
                raise LichessRateLimitError(_retry_after_seconds(response))
            response.raise_for_status()
            async for line in response.aiter_lines():
                if line.strip():
                    studies.append(json.loads(line))
        return studies

    async def get_study_pgn(self, study_id: str) -> str:
        """Get PGN content of a study, with each chapter's Orientation header."""
        response = await self._get(
            f"/api/study/{study_id}.pgn",
            params={"orientation": "true"},
            headers={"Accept": "application/x-chess-pgn"},
        )
        if response.status_code == 403:
            raise httpx.HTTPStatusError(
                f"Access denied to study {study_id}. The study may be private or you may not have permission to access it. "
                f"Make sure the study is either public, unlisted, or you are the owner.",
                request=response.request,
                response=response,
            )
        response.raise_for_status()
        return response.text

    async def get_study_pgn_with_normalized_name(
        self,
        study_id: str,
        study_name: str,
    ) -> tuple[str, str]:
        """
        Fetch study PGN and return with normalized opening name.
        
        Deepens the client by handling opening name normalization internally
        instead of delegating to callers.
        
        Args:
            study_id: Lichess study ID
            study_name: Study name (e.g., "Sicilian Defense" or "Vienna: Accepted")
        
        Returns:
            Tuple of (pgn_content, normalized_opening_name)
            
        Example:
            pgn, opening_name = await client.get_study_pgn_with_normalized_name(
                study_id="ABC12345",
                study_name="Sicilian Defense: Najdorf"
            )
            # Returns: (pgn_string, "Najdorf")
        """
        pgn = await self.get_study_pgn(study_id)
        normalized_opening = OpeningNormalizer.normalize(study_name)
        return pgn, normalized_opening
