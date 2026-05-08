"""
Opening Name Normalizer - Centralized rules for cleaning and standardizing opening names.
"""
import re
from typing import Optional


class OpeningNormalizer:
    """
    Normalizes opening names from various sources into a canonical format.
    
    Handles transformations:
    - Hyphen to space conversion (Chess.com ECO URLs)
    - Removal of move numbers at the end
    - Removal of redundant prefixes (e.g., "Vienna: Accepted" -> "Accepted")
    """

    @staticmethod
    def normalize(name: str) -> str:
        """
        Normalize an opening name to canonical form.
        
        Applies all normalization rules in order:
        1. Remove redundant prefix before colon
        2. Replace hyphens with spaces
        3. Remove move numbers at the end
        4. Strip whitespace
        
        Args:
            name: Raw opening name from any source
        
        Returns:
            Normalized opening name
        """
        if not name:
            return ""

        # Rule 1: Remove redundant prefix before colon
        # E.g., "Vienna: Accepted" -> "Accepted"
        name = OpeningNormalizer._remove_redundant_prefix(name)

        # Rule 2: Replace hyphens with spaces
        # E.g., "Italian-Game-Two-Knights" -> "Italian Game Two Knights"
        name = name.replace("-", " ")

        # Rule 3: Remove move numbers at the end
        # E.g., "Italian Game-4.exd5" -> "Italian Game"
        name = re.sub(r"\s*-?\d+\..*$", "", name)

        # Rule 4: Clean up excessive whitespace
        name = " ".join(name.split())

        return name

    @staticmethod
    def _remove_redundant_prefix(name: str) -> str:
        """
        Remove redundant prefix before colon.
        
        In Lichess studies, chapter names often have format:
        "Vienna: Accepted" or "Sicilian: Main Line"
        
        We want to keep just the part after the colon (more specific).
        This is because the opening name is often already in the study name.
        
        Example:
            Study name: "Vienna Game"
            Chapter name: "Vienna: Accepted"
            After normalization: "Accepted" (avoids duplication)
        
        Args:
            name: Opening/chapter name possibly with prefix
        
        Returns:
            Name with prefix removed (or original if no colon)
        """
        if ":" in name:
            parts = name.split(":", 1)
            return parts[1].strip()
        return name

    @staticmethod
    def from_eco_url(eco_url: str) -> str:
        """
        Extract and normalize opening name from Chess.com ECO URL.
        
        Example:
            Input: "https://www.chess.com/openings/Italian-Game-Two-Knights-Defense"
            Output: "Italian Game Two Knights Defense"
        
        Args:
            eco_url: Full Chess.com ECO URL or slug
        
        Returns:
            Normalized opening name
        """
        if not eco_url:
            return ""

        # Extract the last part of the URL path
        match = re.search(r"/openings/([^/]+)$", eco_url)
        if not match:
            return ""

        opening_slug = match.group(1)
        # Normalize the slug
        return OpeningNormalizer.normalize(opening_slug)

    @staticmethod
    def from_study_chapter_pair(
        study_name: str,
        chapter_name: str,
    ) -> tuple[str, str]:
        """
        Normalize a study name and chapter name pair.
        
        In Lichess studies:
        - Study name is the opening (e.g., "Vienna Game")
        - Chapter name is often specific variation (e.g., "Vienna: Accepted")
        
        We normalize both and avoid redundancy.
        
        Args:
            study_name: Study name from Lichess
            chapter_name: Chapter name from PGN header
        
        Returns:
            Tuple of (normalized_opening_name, normalized_chapter_name)
        """
        norm_study = OpeningNormalizer.normalize(study_name)
        norm_chapter = OpeningNormalizer.normalize(chapter_name)

        # If chapter name starts with opening name, remove the prefix
        # E.g., ("Vienna Game", "Vienna Game - Accepted") -> ("Vienna Game", "Accepted")
        if norm_chapter.startswith(norm_study):
            remainder = norm_chapter[len(norm_study) :].strip()
            if remainder.startswith("-"):
                remainder = remainder[1:].strip()
            if remainder:
                norm_chapter = remainder

        return norm_study, norm_chapter
