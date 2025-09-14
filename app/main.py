import httpx
import redis.asyncio as redis
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends
from upstash_redis import Redis
from app.core.config import settings
from app.services.scraper import FlixPatrolScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Shared application state
app_state = {}

async def create_redis_client():
    """Create Redis client based on configuration type."""
    try:
        if settings.is_upstash_redis:
            # Use Upstash Redis (REST API)
            from upstash_redis.asyncio import Redis as UpstashRedis
            redis_client = UpstashRedis(
                url=settings.UPSTASH_REDIS_REST_URL,
                token=settings.UPSTASH_REDIS_REST_TOKEN
            )
            logging.info("Initialized Upstash Redis client")
            return redis_client
        else:
            # Use local Redis (Docker/VPS)
            redis_pool = redis.ConnectionPool.from_url(
                f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0", 
                decode_responses=True,
                max_connections=20,
                retry_on_timeout=True
            )
            redis_client = redis.Redis(connection_pool=redis_pool)
            logging.info(f"Initialized local Redis client at {settings.REDIS_HOST}:{settings.REDIS_PORT}")
            return redis_client, redis_pool
    except Exception as e:
        logging.error(f"Failed to create Redis client: {e}")
        raise

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup: Initialize resources
    try:
        # Initialize Redis client
        redis_result = await create_redis_client()
        if settings.is_upstash_redis:
            app_state["redis_client"] = redis_result
            app_state["redis_pool"] = None
        else:
            app_state["redis_client"], app_state["redis_pool"] = redis_result
        
        # Initialize HTTP client
        app_state["httpx_client"] = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
        )
        logging.info(f"Application resources initialized successfully (Redis type: {settings.REDIS_TYPE})")
        yield
    except Exception as e:
        logging.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown: Clean up resources
        try:
            if "httpx_client" in app_state:
                await app_state["httpx_client"].aclose()
            if "redis_pool" in app_state and app_state["redis_pool"]:
                await app_state["redis_pool"].disconnect()
            logging.info("Application resources cleaned up successfully")
        except Exception as e:
            logging.error(f"Error during shutdown: {e}")

app = FastAPI(
    title=settings.APP_NAME,
    lifespan=lifespan,
    description="A production-ready API to scrape Top 10 streaming data from FlixPatrol for India",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# Dependency injection functions
def get_redis_client():
    """Dependency to get a Redis client."""
    if "redis_client" not in app_state:
        raise RuntimeError("Redis client not initialized")
    return app_state["redis_client"]

def get_scraper_service() -> FlixPatrolScraper:
    """Dependency to get an instance of the scraper service."""
    if "httpx_client" not in app_state:
        raise RuntimeError("HTTP client not initialized")
    return FlixPatrolScraper(client=app_state["httpx_client"])

# Include API routes
from app.api.endpoints import router as api_router
app.include_router(api_router, prefix="/api/v1/india", tags=["Top 10 India"])

@app.get("/", tags=["Root"])
async def read_root():
    """Root endpoint with basic API information."""
    return {
        "message": f"Welcome to {settings.APP_NAME}",
        "version": "1.0.0",
        "documentation": "/docs",
        "redoc": "/redoc",
        "status": "operational"
    }

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": "1.0.0"
    }
