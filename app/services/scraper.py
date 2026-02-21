# app/services/scraper.py

import httpx
from bs4 import BeautifulSoup
from typing import List, Optional
import logging
import asyncio

from app.core.config import settings
from app.models.streaming import TopTenItem
from app.services.tmdb_matcher import TMDBMatcher

logger = logging.getLogger(__name__)

class FlixPatrolScraper:
    BASE_URL = "https://flixpatrol.com/top10"
    
    def __init__(self, client: httpx.AsyncClient):
        self.client = client
        self.headers = {
            'User-Agent': settings.USER_AGENT,
            'Cookie': '_nss=1'  # Cookie to bypass potential bot checks
        }
        self.tmdb_matcher = TMDBMatcher(client)

    async def _fetch_and_parse(self, url: str) -> Optional[BeautifulSoup]:
        """Fetches a URL and returns a BeautifulSoup object, or None on failure."""
        try:
            response = await self.client.get(
                url, 
                headers=self.headers, 
                follow_redirects=True, 
                timeout=30.0
            )
            response.raise_for_status()
            return BeautifulSoup(response.content, 'html.parser')
        except (httpx.RequestError, httpx.HTTPStatusError) as e:
            logger.error(f"Request failed for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while fetching {url}: {e}")
            return None

    def _parse_table_data(self, section_header, category: str) -> Optional[List[TopTenItem]]:
        """Parse table data from a section header using the proven working approach."""
        try:
            # Find the parent container and then the table
            block_container = section_header.find_parent('div', class_='grid')
            if block_container:
                block_container = block_container.find_parent('div')
            
            if not block_container:
                logger.warning("Could not find block container")
                return None

            table_body = block_container.find("tbody")
            if not table_body:
                logger.warning("Could not find table body")
                return None

            rows = table_body.find_all("tr")
            results = []
            
            for row in rows:
                try:
                    rank_cell = row.find("td", class_="table-td")
                    title_anchor = row.find("a")

                    if rank_cell and title_anchor:
                        rank_text = rank_cell.get_text(strip=True).rstrip(".")
                        if rank_text.isdigit():
                            title = title_anchor.get_text(strip=True)
                            
                            # Get days in top 10 (last cell)
                            all_cells = row.find_all("td", class_="table-td")
                            days = all_cells[-1].get_text(strip=True) if len(all_cells) > 1 else "N/A"
                            
                            results.append({
                                "rank": int(rank_text),
                                "title": title,
                                "days_in_top_10": days,
                                "category": category
                            })
                except (ValueError, AttributeError, IndexError) as e:
                    logger.debug(f"Error parsing row: {e}")
                    continue

            logger.info(f"Successfully parsed {len(results)} items from table")
            return results if results else None
            
        except Exception as e:
            logger.error(f"Error parsing table data: {e}")
            return None

    async def _enrich_with_tmdb(self, items: List[dict], category: str) -> List[TopTenItem]:
        """Enrich scraped items with TMDB data using smart matching."""
        if not settings.TMDB_API_KEY:
            logger.warning("TMDB API key not configured, skipping enrichment")
            return [TopTenItem(**item) for item in items]
        
        # Match all titles concurrently
        match_tasks = [
            self.tmdb_matcher.match_title(item["title"], category)
            for item in items
        ]
        
        matches = await asyncio.gather(*match_tasks, return_exceptions=True)
        
        enriched_items = []
        for item, match in zip(items, matches):
            if isinstance(match, Exception):
                logger.error(f"Error matching '{item['title']}': {match}")
                enriched_items.append(TopTenItem(**item))
            elif match:
                enriched_items.append(TopTenItem(
                    **item,
                    tmdb_id=match["tmdb_id"],
                    media_type=match["media_type"],
                    year=match["year"],
                    match_confidence=match["match_confidence"],
                    poster_path=match["poster_path"]
                ))
            else:
                enriched_items.append(TopTenItem(**item))
        
        return enriched_items

    async def get_top_10_for_category(self, platform_slug: str, section_title: str, category: str) -> Optional[List[TopTenItem]]:
        """
        Fetches and parses the Top 10 list for a given platform and section.
        
        Args:
            platform_slug: e.g., 'netflix', 'amazon-prime', 'apple-tv'
            section_title: The exact section title, e.g., 'TOP 10 Movies', 'TOP 10 TV Shows'
            category: Category key for TMDB matching (movies, tv-shows, overall)
        """
        url = f"{self.BASE_URL}/{platform_slug}/india/"
        logger.info(f"Fetching data from: {url}")
        
        soup = await self._fetch_and_parse(url)
        if not soup:
            return None

        # Find the section header directly using the exact title
        section_header = soup.find("h3", string=section_title)
        if not section_header:
            logger.warning(f"Could not find section header '{section_title}' on {url}")
            return None

        logger.info(f"Found section header for '{section_title}'")
        raw_items = self._parse_table_data(section_header, category)
        
        if not raw_items:
            return None
        
        # Enrich with TMDB data
        return await self._enrich_with_tmdb(raw_items, category)