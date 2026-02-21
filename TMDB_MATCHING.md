# TMDB Smart Matching System

## Overview

The FlixPatrol scraper now includes an intelligent TMDB matching system that automatically enriches scraped titles with TMDB metadata. This provides accurate movie/TV show identification with confidence scoring.

## How It Works

### 1. Title Normalization
```python
"The Shawshank Redemption (1994)" 
→ "The Shawshank Redemption"
→ normalized: "shawshank redemption"
```

Removes:
- Special characters (except hyphens and apostrophes)
- Year in parentheses
- Common suffixes (Season X, Part X, Vol X)
- Extra whitespace

### 2. Fuzzy String Matching
Uses Python's `SequenceMatcher` to calculate similarity between:
- Scraped title vs TMDB primary title
- Scraped title vs TMDB original title

Returns best match with similarity score 0-1.

### 3. Year-Based Relevance Scoring

Prioritizes recent releases with decreasing scores for older content:

| Year Difference | Score | Example (Current: 2026) |
|----------------|-------|------------------------|
| 0-1 years | 1.0 | 2025-2026 |
| 2-3 years | 0.9 | 2023-2024 |
| 4-5 years | 0.8 | 2021-2022 |
| 6-10 years | 0.7 | 2016-2020 |
| 11+ years | 0.3-0.7 | 2015 and older |

**Special Case:** If title contains explicit year (e.g., "Movie (2020)"), exact year match gets score 1.0.

### 4. Weighted Scoring Formula

```
Final Score = (Title Similarity × 0.7) + (Year Relevance × 0.3)
```

**Bonuses:**
- +0.1 for exact title match
- +0.05 for popular content (vote_count > 1000)

**Threshold:** Only returns matches with confidence ≥ 0.6

### 5. Multi-Type Search

For "overall" category, searches both:
1. Movies (`/search/movie`)
2. TV Shows (`/search/tv`)

Returns best match across both types.

## Example Matching Process

### Input: "Jawan"
```
1. Normalize: "jawan"
2. Search TMDB: /search/movie?query=jawan
3. Results:
   - "Jawan" (2023) - ID: 945729
     • Title similarity: 1.0 (exact match)
     • Year score: 1.0 (2023, recent)
     • Popularity bonus: +0.05 (vote_count: 2500)
     • Final: (1.0 × 0.7) + (1.0 × 0.3) + 0.1 + 0.05 = 1.0 ✅
   
   - "Jawaan" (2017) - ID: 123456
     • Title similarity: 0.9 (close match)
     • Year score: 0.7 (9 years old)
     • Final: (0.9 × 0.7) + (0.7 × 0.3) = 0.84
     
4. Best Match: "Jawan" (2023) with confidence 1.0
```

### Input: "The Shawshank Redemption (1994)"
```
1. Extract year: 1994
2. Normalize: "shawshank redemption"
3. Search TMDB: /search/movie?query=shawshank redemption
4. Results:
   - "The Shawshank Redemption" (1994) - ID: 278
     • Title similarity: 0.95
     • Year match: 1.0 (exact year match)
     • Popularity bonus: +0.05 (vote_count: 25000)
     • Final: (0.95 × 0.7) + (1.0 × 0.3) + 0.05 = 1.0 ✅
```

### Input: "Scam 1992" (TV Show)
```
1. Normalize: "scam 1992"
2. Search TMDB: /search/tv?query=scam 1992
3. Results:
   - "Scam 1992: The Harshad Mehta Story" (2020) - ID: 115036
     • Title similarity: 0.75 (partial match)
     • Year score: 0.8 (6 years old)
     • Final: (0.75 × 0.7) + (0.8 × 0.3) = 0.765 ✅
```

## API Response Format

### With TMDB Match
```json
{
  "rank": 1,
  "title": "Jawan",
  "days_in_top_10": "7 days",
  "tmdb_id": 945729,
  "media_type": "movie",
  "year": 2023,
  "match_confidence": 0.95,
  "poster_path": "/xvk8qWkLLQKH6vimRYWgbVnYYaR.jpg"
}
```

### Without TMDB Match
```json
{
  "rank": 1,
  "title": "Unknown Movie",
  "days_in_top_10": "3 days",
  "tmdb_id": null,
  "media_type": null,
  "year": null,
  "match_confidence": null,
  "poster_path": null
}
```

## Configuration

Add to `.env`:
```bash
TMDB_API_KEY=your_api_key_here
TMDB_BASE_URL=https://api.themoviedb.org/3
```

Get API key: https://www.themoviedb.org/settings/api

## Performance

- Concurrent matching for all items in a list
- Typical match time: 100-300ms per title
- Cached results: 4 hours (same as FlixPatrol data)
- Graceful degradation: Returns raw data if TMDB unavailable

## Logging

```
INFO: Matching title: 'Jawan' -> normalized: 'jawan', year: None
INFO: ✅ Matched 'Jawan' -> 'Jawan' (ID: 945729, confidence: 0.95)
WARNING: ❌ No confident match for 'Unknown Movie' (best score: 0.45)
```

## Edge Cases Handled

1. **Title with year**: "Movie (2020)" → Extracts year, prioritizes exact match
2. **International titles**: Checks both primary and original titles
3. **Remakes**: Year scoring helps select correct version
4. **Sequels**: "Movie 2" vs "Movie II" → Fuzzy matching handles variations
5. **No match**: Returns null fields, doesn't break response
6. **API failure**: Logs error, returns raw scraped data

## Future Enhancements

- [ ] Cache TMDB matches separately (longer TTL)
- [ ] Support for alternative titles/aliases
- [ ] Region-specific title matching
- [ ] Manual override/correction system
- [ ] Match quality metrics dashboard
