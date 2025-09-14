from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "FlixPatrol India Scraper API"
    CONTACT_EMAIL: str
    
    REDIS_HOST: str = "localhost"
    REDIS_PORT: int = 6379
    CACHE_EXPIRATION_SECONDS: int = 14400 # 4 hours

    @property
    def USER_AGENT(self) -> str:
        return f"{self.APP_NAME}/1.0 (Contact: {self.CONTACT_EMAIL})"

    class Config:
        env_file = ".env"

settings = Settings()
