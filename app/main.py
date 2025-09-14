import httpx
import redis.asyncio as redis
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends

from app.core.config import settings
from app.services.scraper import FlixPatrolScraper

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Shared application state
app_state = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown events."""
    # Startup: Initialize resources
    try:
        app_state["redis_pool"] = redis.ConnectionPool.from_url(
            f"redis://{settings.REDIS_HOST}:{settings.REDIS_PORT}/0", 
            decode_responses=True,
            max_connections=20,
            retry_on_timeout=True
        )
        app_state["httpx_client"] = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=50)
        )
        logging.info("Application resources initialized successfully")
        yield
    except Exception as e:
        logging.error(f"Error during startup: {e}")
        raise
    finally:
        # Shutdown: Clean up resources
        try:
            if "httpx_client" in app_state:
                await app_state["httpx_client"].aclose()
            if "redis_pool" in app_state:
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
    """Dependency to get a Redis client from the connection pool."""
    if "redis_pool" not in app_state:
        raise RuntimeError("Redis pool not initialized")
    return redis.Redis(connection_pool=app_state["redis_pool"])

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
