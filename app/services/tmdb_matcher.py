# app/services/tmdb_matcher.py

import httpx
import re
import logging
from typing import Optional, Dict, Any, List, Tuple
from datetime import datetime
from difflib import SequenceMatcher

from app.core.config import settings

logger = logging.getLogger(__name__)

class TMDBMatcher:
    """Smart TMDB matcher with fuzzy matching, normalization, and year-based filtering."""
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.base_url = settings.TMDB_BASE_URL
        self.api_key = settings.TMDB_API_KEY
        self.current_year = datetime.now().year
        
    def normalize_title(self, title: str) -> str:
        """Normalize title for better matching."""
        # Remove special characters and extra spaces
        title = re.sub(r'[^\w\s\-\']', ' ', title)
        # Remove common suffixes
        title = re.sub(r'\s+(Season\s+\d+|Part\s+\d+|Vol\s+\d+)$', '', title, flags=re.IGNORECASE)
        # Remove year in parentheses
        title = re.sub(r'\s*\(\d{4}\)\s*', ' ', title)
        # Normalize whitespace
        title = ' '.join(title.split())
        return title.strip()
    
    def calculate_similarity(self, str1: str, str2: str) -> float:
        """Calculate similarity between two strings (0-1)."""
        return SequenceMatcher(None, str1.lower(), str2.lower()).ratio()
    
    def calculate_year_score(self, result_year: Optional[int]) -> float:
        """
        Calculate year relevance score (0-1).
        Prioritizes recent releases, with score decreasing as years go back.
        """
        if not result_year:
            return 0.5  # Neutral score if no year
        
        year_diff = abs(self.current_year - result_year)
        
        # Perfect score for current year and last year
        if year_diff <= 1:
            return 1.0
        # High score for last 3 years
        elif year_diff <= 3:
            return 0.9
        # Good score for last 5 years
        elif year_diff <= 5:
            return 0.8
        # Decent score for last 10 years
        elif year_diff <= 10:
            return 0.7
        # Lower score for older content
        else:
            return max(0.3, 1.0 - (year_diff / 50))
    
    def extract_year_from_title(self, title: str) -> Tuple[str, Optional[int]]:
        """Extract year from title if present."""
        match = re.search(r'\((\d{4})\)', title)
        if match:
            year = int(match.group(1))
            clean_title = title.replace(match.group(0), '').strip()
            return clean_title, year
        return title, None
    
    async def search_tmdb(self, query: str, media_type: str) -> Optional[List[Dict[str, Any]]]:
        """Search TMDB API."""
        if not self.api_key:
            logger.warning("TMDB API key not configured")
            return None
        
        try:
            endpoint = f"{self.base_url}/search/{media_type}"
            params = {
                "api_key": self.api_key,
                "query": query,
                "language": "en-US",
                "page": 1,
                "include_adult": False
            }
            
            response = await self.client.get(endpoint, params=params, timeout=10.0)
            response.raise_for_status()
            data = response.json()
            return data.get("results", [])
        except Exception as e:
            logger.error(f"TMDB search failed for '{query}': {e}")
            return None
    
    def score_result(self, result: Dict[str, Any], normalized_query: str, extracted_year: Optional[int]) -> float:
        """
        Calculate comprehensive match score for a TMDB result.
        Combines title similarity and year relevance.
        """
        # Get title from result
        title = result.get("title") or result.get("name", "")
        original_title = result.get("original_title") or result.get("original_name", "")
        
        # Calculate title similarity (primary and original)
        primary_similarity = self.calculate_similarity(normalized_query, title)
        original_similarity = self.calculate_similarity(normalized_query, original_title)
        title_score = max(primary_similarity, original_similarity)
        
        # Get year from result
        release_date = result.get("release_date") or result.get("first_air_date")
        result_year = None
        if release_date:
            try:
                result_year = int(release_date.split("-")[0])
            except (ValueError, IndexError):
                pass
        
        # Calculate year score
        if extracted_year:
            # If title had explicit year, prioritize exact match
            if result_year == extracted_year:
                year_score = 1.0
            else:
                year_score = max(0.3, 1.0 - abs(extracted_year - result_year) / 20) if result_year else 0.5
        else:
            # Use recency-based scoring
            year_score = self.calculate_year_score(result_year)
        
        # Weighted combination: 70% title similarity, 30% year relevance
        final_score = (title_score * 0.7) + (year_score * 0.3)
        
        # Boost score for exact matches
        if title.lower() == normalized_query.lower() or original_title.lower() == normalized_query.lower():
            final_score = min(1.0, final_score + 0.1)
        
        # Boost score for popular content (higher vote count)
        vote_count = result.get("vote_count", 0)
        if vote_count > 1000:
            final_score = min(1.0, final_score + 0.05)
        
        return final_score
    
    async def match_title(self, title: str, category: str) -> Optional[Dict[str, Any]]:
        """
        Match a title to TMDB with intelligent fuzzy matching and year filtering.
        
        Args:
            title: Raw title from FlixPatrol
            category: "movies", "tv-shows", or "overall"
        
        Returns:
            Dict with tmdb_id, media_type, year, confidence, poster_path
        """
        if not self.api_key:
            return None
        
        # Extract year if present in title
        clean_title, extracted_year = self.extract_year_from_title(title)
        normalized_title = self.normalize_title(clean_title)
        
        logger.info(f"Matching title: '{title}' -> normalized: '{normalized_title}', year: {extracted_year}")
        
        # Determine media types to search
        if category == "movies":
            media_types = ["movie"]
        elif category == "tv-shows":
            media_types = ["tv"]
        else:  # overall
            media_types = ["movie", "tv"]
        
        best_match = None
        best_score = 0.0
        
        for media_type in media_types:
            results = await self.search_tmdb(normalized_title, media_type)
            
            if not results:
                continue
            
            # Score all results
            for result in results[:10]:  # Check top 10 results
                score = self.score_result(result, normalized_title, extracted_year)
                
                if score > best_score:
                    best_score = score
                    
                    # Get year
                    release_date = result.get("release_date") or result.get("first_air_date")
                    year = None
                    if release_date:
                        try:
                            year = int(release_date.split("-")[0])
                        except (ValueError, IndexError):
                            pass
                    
                    best_match = {
                        "tmdb_id": result.get("id"),
                        "media_type": media_type,
                        "year": year,
                        "match_confidence": round(score, 3),
                        "poster_path": result.get("poster_path"),
                        "matched_title": result.get("title") or result.get("name")
                    }
        
        # Only return matches with confidence > 0.6
        if best_match and best_match["match_confidence"] >= 0.6:
            logger.info(f"✅ Matched '{title}' -> '{best_match['matched_title']}' "
                       f"(ID: {best_match['tmdb_id']}, confidence: {best_match['match_confidence']})")
            return best_match
        else:
            logger.warning(f"❌ No confident match for '{title}' (best score: {best_score:.3f})")
            return None
