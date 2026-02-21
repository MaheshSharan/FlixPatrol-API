from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime

class TopTenItem(BaseModel):
    rank: int = Field(..., description="Ranking position (1-10)")
    title: str = Field(..., description="Title of the movie/show") 
    days_in_top_10: str = Field(..., description="Number of days in top 10")
    tmdb_id: Optional[int] = Field(None, description="TMDB ID if matched")
    media_type: Optional[str] = Field(None, description="movie or tv")
    year: Optional[int] = Field(None, description="Release/first air year")
    match_confidence: Optional[float] = Field(None, description="Match confidence score (0-1)")
    poster_path: Optional[str] = Field(None, description="TMDB poster path")

class PlatformStatus(BaseModel):
    """Status information for a platform category"""
    available: bool = Field(..., description="Whether this category is available")
    count: int = Field(0, description="Number of items returned")
    status: str = Field(..., description="Status message")

class ResponseSummary(BaseModel):
    """Summary section for API responses"""
    timestamp: str = Field(..., description="Response generation timestamp")
    total_platforms: int = Field(..., description="Total platforms checked")
    successful_platforms: int = Field(..., description="Platforms with data")
    total_requests: int = Field(..., description="Total API requests made")
    successful_requests: int = Field(..., description="Successful API requests")
    cache_hit_rate: str = Field(..., description="Cache hit percentage")
    platforms: Dict[str, Dict[str, PlatformStatus]] = Field(..., description="Platform status breakdown")

# Platform-specific data models (only include supported categories)
class NetflixData(BaseModel):
    movies: Optional[List[TopTenItem]] = Field(None, description="Top 10 movies")
    tv_shows: Optional[List[TopTenItem]] = Field(None, description="Top 10 TV shows")

class AmazonPrimeData(BaseModel):
    movies: Optional[List[TopTenItem]] = Field(None, description="Top 10 movies")
    tv_shows: Optional[List[TopTenItem]] = Field(None, description="Top 10 TV shows")
    overall: Optional[List[TopTenItem]] = Field(None, description="Top 10 overall content")

class AppleTVData(BaseModel):
    movies: Optional[List[TopTenItem]] = Field(None, description="Top 10 movies")
    tv_shows: Optional[List[TopTenItem]] = Field(None, description="Top 10 TV shows")

class iTunesData(BaseModel):
    movies: Optional[List[TopTenItem]] = Field(None, description="Top 10 movies")

class GoogleData(BaseModel):
    movies: Optional[List[TopTenItem]] = Field(None, description="Top 10 movies")

class Zee5Data(BaseModel):
    overall: Optional[List[TopTenItem]] = Field(None, description="Top 10 overall content")

class FetchAllResponse(BaseModel):
    """Complete response structure with summary and clean data"""
    summary: ResponseSummary = Field(..., description="Response summary and status")
    data: Dict[str, Any] = Field(..., description="Platform data (only successful responses)")

    class Config:
        json_schema_extra = {
            "example": {
                "summary": {
                    "timestamp": "2025-09-15T01:30:00Z",
                    "total_platforms": 6,
                    "successful_platforms": 6,
                    "total_requests": 10,
                    "successful_requests": 10,
                    "cache_hit_rate": "80%",
                    "platforms": {
                        "netflix": {
                            "movies": {"available": True, "count": 10, "status": "✅ Success"},
                            "tv_shows": {"available": True, "count": 10, "status": "✅ Success"}
                        },
                        "amazon_prime": {
                            "movies": {"available": True, "count": 10, "status": "✅ Success"},
                            "tv_shows": {"available": True, "count": 10, "status": "✅ Success"},
                            "overall": {"available": True, "count": 10, "status": "✅ Success"}
                        }
                    }
                },
                "data": {
                    "netflix": {
                        "movies": [{"rank": 1, "title": "Sample Movie", "days_in_top_10": "7 d"}],
                        "tv_shows": [{"rank": 1, "title": "Sample Show", "days_in_top_10": "14 d"}]
                    },
                    "amazon_prime": {
                        "movies": [{"rank": 1, "title": "Another Movie", "days_in_top_10": "3 d"}],
                        "tv_shows": [{"rank": 1, "title": "Another Show", "days_in_top_10": "5 d"}],
                        "overall": [{"rank": 1, "title": "Top Content", "days_in_top_10": "12 d"}]
                    }
                }
            }
        }
