# FlixPatrol  Scraper API

A production-ready FastAPI service that scrapes Top 10 streaming data from FlixPatrol (INDIA). The service uses Redis caching for performance optimization and is containerized for easy deployment.

> **Note:** This is an experimental, proof-of-concept API. It worked when originally developed but is no longer actively maintained, so it may not function reliably today. The project demonstrates the FlixPatrol scraping approach (currently configured for India) and can be adapted to other regions with modest code changes — however, scrapers are brittle and may require updates if the source site changes.my dump api **

## Features

- High-performance Redis caching with 4-hour expiration
- Concurrent async processing for optimal response times  
- Production-ready Docker containerization
- Real-time response summaries with platform status indicators
- Comprehensive error handling and logging
- Auto-generated OpenAPI documentation
- Respectful scraping with proper rate limiting

## Supported Platforms

| Platform | Movies | TV Shows | Overall | URL Slug |
|----------|--------|----------|---------|----------|
| Netflix | ✅ | ✅ | ❌ | `netflix` |
| Amazon Prime | ✅ | ✅ | ✅ | `amazon-prime` |
| Apple TV | ✅ | ✅ | ❌ | `apple-tv` |
| iTunes | ✅ | ❌ | ❌ | `itunes` |
| Google Play | ✅ | ❌ | ❌ | `google` |
| Zee5 | ❌ | ❌ | ✅ | `zee5` |

The scraper identifies itself with User-Agent: `FlixPatrol India Scraper API/1.0 (Contact: maheshsharan28@gmail.com)`

## Quick Start

### Prerequisites
- Docker
- Docker Compose

### Running the Service

1. Clone the repository and update env file using example.env
2. Build and start the services:
   ```bash
   docker-compose up --build
   ```

The Docker setup automatically:
- Installs all Python dependencies
- Configures Redis caching
- Starts the API server on port 8000
- Sets up proper networking between services

### Access Points
- API Base: http://localhost:8000
- Health Check: http://localhost:8000/health
- Interactive Documentation: http://localhost:8000/docs
- ReDoc Documentation: http://localhost:8000/redoc

## API Endpoints

All endpoints are prefixed with `/api/v1/india` and return JSON responses.

### Complete Endpoint Reference

| Method | Endpoint | Description | Cache TTL |
|--------|----------|-------------|-----------|
| `GET` | `/health` | Service health check | None |
| `GET` | `/api/v1/india/{platform}/{category}` | Get specific platform category | 4 hours |
| `GET` | `/api/v1/india/fetchall` | Get all available data with summary | 4 hours |

### Platform-Category Matrix

| Platform | Movies | TV Shows | Overall |
|----------|--------|----------|---------|
| Netflix | `GET /api/v1/india/netflix/movies` | `GET /api/v1/india/netflix/tv-shows` | ❌ |
| Amazon Prime | `GET /api/v1/india/amazon-prime/movies` | `GET /api/v1/india/amazon-prime/tv-shows` | `GET /api/v1/india/amazon-prime/overall` |
| Apple TV | `GET /api/v1/india/apple-tv/movies` | `GET /api/v1/india/apple-tv/tv-shows` | ❌ |
| iTunes | `GET /api/v1/india/itunes/movies` | ❌ | ❌ |
| Google Play | `GET /api/v1/india/google/movies` | ❌ | ❌ |
| Zee5 | ❌ | ❌ | `GET /api/v1/india/zee5/overall` |

### Example Requests

```bash
curl http://localhost:8000/api/v1/india/netflix/movies
curl http://localhost:8000/api/v1/india/amazon-prime/tv-shows  
curl http://localhost:8000/api/v1/india/fetchall
curl http://localhost:8000/health
```

## Response Format

### Single Category Response
```json
[
  {
    "rank": 1,
    "title": "Jawan",
    "days_in_top_10": "7 days"
  },
  {
    "rank": 2,
    "title": "Pathaan", 
    "days_in_top_10": "14 days"
  }
]
```

### Fetch All Response
The `/fetchall` endpoint returns aggregated data from all platforms with a summary section:

```json
{
  "summary": {
    "timestamp": "2024-01-15T10:30:00Z",
    "total_platforms": 6,
    "successful_platforms": 5,
    "total_requests": 9,
    "successful_requests": 8,
    "cache_hit_rate": "75%",
    "platforms": {
      "netflix": {
        "movies": {"available": true, "count": 10, "status": "✅ Success"},
        "tv_shows": {"available": true, "count": 10, "status": "✅ Success"}
      },
      "amazon_prime": {
        "movies": {"available": true, "count": 10, "status": "✅ Success"},
        "tv_shows": {"available": false, "count": 0, "status": "❌ Failed"},
        "overall": {"available": true, "count": 10, "status": "✅ Success"}
      }
    }
  },
  "netflix": {
    "movies": [{"rank": 1, "title": "Jawan", "days_in_top_10": "7 days"}],
    "tv_shows": [{"rank": 1, "title": "Scam 1992", "days_in_top_10": "14 days"}]
  },
  "amazon_prime": {
    "movies": [{"rank": 1, "title": "The Family Man", "days_in_top_10": "21 days"}],
    "overall": [{"rank": 1, "title": "Made in Heaven", "days_in_top_10": "35 days"}]
  }
}
```

## Configuration

### Environment Variables
| Variable | Default | Description |
|----------|---------|-------------|
| `APP_NAME` | `"FlixPatrol India Scraper API"` | Application name |
| `CONTACT_EMAIL` | `"maheshsharan28@gmail.com"` | Contact email for User-Agent |
| `REDIS_HOST` | `redis` | Redis server hostname |
| `REDIS_PORT` | `6379` | Redis server port |
| `CACHE_EXPIRATION_SECONDS` | `14400` | Cache TTL (4 hours) |

### Caching
- All responses are cached in Redis for 4 hours
- Cache keys: `india:{platform}:{category}`
- Fetchall cache key: `india:fetchall`
- Cache improves response time from ~2-5s to ~5ms

## Error Handling

| HTTP Code | Description |
|-----------|-------------|
| `200` | Success |
| `404` | Platform or category not found |
| `422` | Invalid parameters |
| `503` | Service temporarily unavailable |
| `500` | Internal server error |

## Monitoring

Check service health:
```bash
curl http://localhost:8000/health
```

View logs:
```bash
docker-compose logs -f api
```

## Support

- **Email**: maheshsharan28@gmail.com
- **Documentation**: http://localhost:8000/docs
