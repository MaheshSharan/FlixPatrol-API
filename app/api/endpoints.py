# app/api/endpoints.py

import json
import asyncio
import logging
from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException

from app.core.config import settings
from app.models.streaming import (
    TopTenItem, FetchAllResponse, ResponseSummary, PlatformStatus,
    NetflixData, AmazonPrimeData, AppleTVData, iTunesData, GoogleData, Zee5Data
)
from app.services.scraper import FlixPatrolScraper
from app.main import get_scraper_service, get_redis_client

logger = logging.getLogger(__name__)
router = APIRouter()

# Clean platform configuration - only supported combinations
PLATFORM_CONFIG = {
    "netflix": ["TOP 10 Movies", "TOP 10 TV Shows"],
    "amazon-prime": ["TOP 10 Movies", "TOP 10 TV Shows", "TOP 10 Overall"],
    "apple-tv": ["TOP 10 Movies", "TOP 10 TV Shows"],
    "itunes": ["TOP 10 Movies"],  # iTunes only has movies
    "google": ["TOP 10 Movies"],  # Google Play only has movies
    "zee5": ["TOP 10 Overall"],   # Zee5 only has overall category
}

# Maps API category keys to FlixPatrol section titles
CATEGORY_MAP = {
    "movies": "TOP 10 Movies",
    "tv-shows": "TOP 10 TV Shows", 
    "overall": "TOP 10 Overall"
}

# Maps platform slugs to model field names (clean, no unused platforms)
PLATFORM_SLUG_TO_MODEL_KEY = {
    "netflix": "netflix",
    "amazon-prime": "amazon_prime", 
    "apple-tv": "apple_tv",
    "itunes": "itunes",
    "google": "google",
    "zee5": "zee5"
}

async def get_cached_or_scrape(
    platform_slug: str,
    category_key: str,
    scraper: FlixPatrolScraper,
    redis_client
) -> Optional[List[TopTenItem]]:
    """Helper function to check cache first, then scrape if needed."""
    cache_key = f"india:{platform_slug}:{category_key}"
    
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            cached_data = json.loads(cached)
            return [TopTenItem(**item) for item in cached_data]
    except Exception as e:
        logger.warning(f"Cache read error for {cache_key}: {e}")

    # Map category key to section title
    section_title = CATEGORY_MAP.get(category_key)
    if not section_title:
        logger.error(f"Invalid category key: {category_key}")
        return None

    # Scrape the data
    data = await scraper.get_top_10_for_category(platform_slug, section_title)
    
    # Cache the results if successful
    if data:
        try:
            data_to_cache = [item.model_dump() for item in data]
            await redis_client.setex(
                cache_key, 
                settings.CACHE_EXPIRATION_SECONDS, 
                json.dumps(data_to_cache)
            )
        except Exception as e:
            logger.warning(f"Cache write error for {cache_key}: {e}")
    
    return data

@router.get(
    "/{platform}/{category}",
    response_model=List[TopTenItem],
    summary="Get Top 10 for a specific platform and category"
)
async def get_single_category(
    platform: str,
    category: str,
    scraper: FlixPatrolScraper = Depends(get_scraper_service),
    redis_client = Depends(get_redis_client)
):
    """
    Get the Top 10 list for a specific streaming platform and category in India.
    
    **Supported Platforms & Categories:**
    - **netflix**: movies, tv-shows
    - **amazon-prime**: movies, tv-shows, overall
    - **apple-tv**: movies, tv-shows
    - **itunes**: movies
    - **google**: movies
    - **zee5**: overall
    
    Args:
        platform: Platform slug (netflix, amazon-prime, apple-tv, itunes, google, zee5)
        category: Category key (movies, tv-shows, overall)
    
    Returns:
        List of TopTenItem objects
    """
    if platform not in PLATFORM_CONFIG:
        available_platforms = ', '.join(list(PLATFORM_CONFIG.keys()))
        raise HTTPException(
            status_code=404, 
            detail=f"Platform '{platform}' not supported. Available platforms: {available_platforms}"
        )
    
    if category not in CATEGORY_MAP:
        available_categories = ', '.join(list(CATEGORY_MAP.keys()))
        raise HTTPException(
            status_code=404,
            detail=f"Category '{category}' not supported. Available categories: {available_categories}"
        )
    
    # Check if the platform supports this category
    section_title = CATEGORY_MAP[category]
    if section_title not in PLATFORM_CONFIG[platform]:
        supported_categories = []
        for section in PLATFORM_CONFIG[platform]:
            category_key = next((k for k, v in CATEGORY_MAP.items() if v == section), None)
            if category_key:
                supported_categories.append(category_key)
        
        raise HTTPException(
            status_code=404,
            detail=f"Platform '{platform}' does not support category '{category}'. Supported categories for {platform}: {', '.join(supported_categories)}"
        )
    
    data = await get_cached_or_scrape(platform, category, scraper, redis_client)
    
    if data is None:
        raise HTTPException(
            status_code=503, 
            detail=f"Could not retrieve data for {platform} {category}. The service may be temporarily unavailable."
        )
        
    return data

@router.get("/fetchall", response_model=FetchAllResponse, summary="Get all Top 10 lists for India with summary")
async def fetch_all(
    scraper: FlixPatrolScraper = Depends(get_scraper_service),
    redis_client = Depends(get_redis_client)
):
    """
    Aggregates and returns all available Top 10 lists from all platforms in India.
    Includes a comprehensive summary with status indicators and clean data without nulls.
    """
    cache_key = "india:fetchall"
    
    # Check cache first
    try:
        cached = await redis_client.get(cache_key)
        if cached:
            return FetchAllResponse.model_validate_json(cached)
    except Exception as e:
        logger.warning(f"Cache read error for fetchall: {e}")

    # Build scraping tasks
    tasks = []
    task_mapping = []
    
    for platform_slug, sections in PLATFORM_CONFIG.items():
        for section_title in sections:
            # Find the category key for this section
            category_key = next(
                (k for k, v in CATEGORY_MAP.items() if v == section_title), 
                None
            )
            
            if category_key:
                task = get_cached_or_scrape(platform_slug, category_key, scraper, redis_client)
                tasks.append(task)
                task_mapping.append({
                    'platform': platform_slug,
                    'category': category_key
                })

    # Execute all tasks concurrently
    results = await asyncio.gather(*tasks, return_exceptions=True)
    
    # Build response data and summary
    response_data = {}
    platform_summary = {}
    successful_requests = 0
    total_requests = len(tasks)
    
    for i, result in enumerate(results):
        mapping = task_mapping[i]
        platform_slug = mapping['platform']
        category_key = mapping['category']
        
        # Initialize platform summary if needed
        if platform_slug not in platform_summary:
            platform_summary[platform_slug] = {}
        
        if isinstance(result, Exception):
            logger.error(f"Task {i} failed: {result}")
            platform_summary[platform_slug][category_key] = PlatformStatus(
                available=False,
                count=0,
                status="❌ Error"
            )
            continue
            
        if result and len(result) > 0:  # Successful result with data
            model_platform_key = PLATFORM_SLUG_TO_MODEL_KEY.get(platform_slug, platform_slug)
            model_category_field = category_key.replace('-', '_')
            
            if model_platform_key not in response_data:
                response_data[model_platform_key] = {}
                
            response_data[model_platform_key][model_category_field] = result
            successful_requests += 1
            
            platform_summary[platform_slug][category_key] = PlatformStatus(
                available=True,
                count=len(result),
                status=f"✅ Success ({len(result)} items)"
            )
        else:
            # No data returned
            platform_summary[platform_slug][category_key] = PlatformStatus(
                available=False,
                count=0,
                status="❌ No data"
            )

    # Create summary
    summary = ResponseSummary(
        timestamp=datetime.utcnow().isoformat() + "Z",
        total_platforms=len(PLATFORM_CONFIG),
        successful_platforms=len(response_data),
        total_requests=total_requests,
        successful_requests=successful_requests,
        cache_hit_rate="0%",  # We could track this properly with Redis stats
        platforms=platform_summary
    )
    
    final_response = FetchAllResponse(
        summary=summary,
        data=response_data
    )
    
    # Cache the result
    try:
        await redis_client.setex(
            cache_key, 
            settings.CACHE_EXPIRATION_SECONDS, 
            final_response.model_dump_json()
        )
    except Exception as e:
        logger.warning(f"Cache write error for fetchall: {e}")
    
    logger.info(f"Fetchall completed: {successful_requests}/{total_requests} successful requests")
    return final_response