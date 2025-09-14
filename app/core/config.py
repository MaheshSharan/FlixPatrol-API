from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "FlixPatrol India Scraper API"
    CONTACT_EMAIL: str
    
    # Redis settings - will be overridden by environment variables in production
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CACHE_EXPIRATION_SECONDS: int = 14400 # 4 hours

    @property
    def USER_AGENT(self) -> str:
        return f"{self.APP_NAME}/1.0 (Contact: {self.CONTACT_EMAIL})"

    class Config:
        env_file = ".env"
        # Environment variables take precedence over .env file
        env_file_encoding = 'utf-8'

settings = Settings()
