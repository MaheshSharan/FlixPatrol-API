from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "FlixPatrol India Scraper API"
    CONTACT_EMAIL: str
    
    # Redis configuration - flexible for different deployment types
    REDIS_TYPE: str = "local"  # "local" for Docker Redis, "upstash" for Upstash Redis
    
    # Local Redis settings (Docker/VPS deployment)
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    
    # Upstash Redis settings (Render/serverless deployment)
    UPSTASH_REDIS_REST_URL: str = ""
    UPSTASH_REDIS_REST_TOKEN: str = ""
    
    CACHE_EXPIRATION_SECONDS: int = 14400 # 4 hours

    @property
    def USER_AGENT(self) -> str:
        return f"{self.APP_NAME}/1.0 (Contact: {self.CONTACT_EMAIL})"

    @property 
    def is_upstash_redis(self) -> bool:
        """Check if using Upstash Redis"""
        return self.REDIS_TYPE.lower() == "upstash"

    @property
    def is_local_redis(self) -> bool:
        """Check if using local Redis (Docker/VPS)"""
        return self.REDIS_TYPE.lower() == "local"

    class Config:
        env_file = ".env"
        # Environment variables take precedence over .env file
        env_file_encoding = 'utf-8'

settings = Settings()
