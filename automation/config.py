"""
Configuration management for ParfumVault Data Auto-Population Module.

Environment variables with sensible defaults for Docker deployment.
"""

import os
import logging
from dataclasses import dataclass
from typing import Optional


@dataclass
class DatabaseConfig:
    """Database connection configuration."""
    host: str
    user: str
    password: str
    database: str
    port: int = 3306
    charset: str = "utf8mb4"
    
    @property
    def connection_url(self) -> str:
        """Generate SQLAlchemy connection URL."""
        return (
            f"mysql+mysqldb://{self.user}:{self.password}"
            f"@{self.host}:{self.port}/{self.database}"
            f"?charset={self.charset}"
        )


@dataclass
class ScraperConfig:
    """Web scraper configuration."""
    delay_seconds: float = 10.0
    max_retries: int = 3
    timeout_seconds: int = 60
    enable_user_agent_rotation: bool = True
    cache_enabled: bool = True
    cache_ttl_hours: int = 24


@dataclass
class AppConfig:
    """Main application configuration."""
    db: DatabaseConfig
    scraper: ScraperConfig
    owner_id: str
    log_level: str
    data_dir: str
    
    @classmethod
    def from_environment(cls) -> "AppConfig":
        """Load configuration from environment variables."""
        db_config = DatabaseConfig(
            host=os.getenv("DB_HOST", "localhost"),
            user=os.getenv("DB_USER", "pvault"),
            password=os.getenv("DB_PASS", "pvault"),
            database=os.getenv("DB_NAME", "pvault"),
            port=int(os.getenv("DB_PORT", "3306")),
        )
        
        scraper_config = ScraperConfig(
            delay_seconds=float(os.getenv("SCRAPER_DELAY", "10.0")),
            max_retries=int(os.getenv("SCRAPER_MAX_RETRIES", "3")),
            timeout_seconds=int(os.getenv("SCRAPER_TIMEOUT", "60")),
            enable_user_agent_rotation=os.getenv("USER_AGENT_ROTATION", "true").lower() == "true",
            cache_enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
            cache_ttl_hours=int(os.getenv("CACHE_TTL_HOURS", "24")),
        )
        
        return cls(
            db=db_config,
            scraper=scraper_config,
            owner_id=os.getenv("OWNER_ID", "1"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            data_dir=os.getenv("DATA_DIR", "/app/data"),
        )


def setup_logging(level: str = "INFO") -> logging.Logger:
    """Configure logging for Docker stdout output."""
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    logging.basicConfig(
        level=log_level,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        handlers=[logging.StreamHandler()],
    )
    
    logger = logging.getLogger("parfum_automation")
    logger.setLevel(log_level)
    
    return logger


# Global configuration instance
_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """Get or create the global configuration instance."""
    global _config
    if _config is None:
        _config = AppConfig.from_environment()
    return _config


def get_logger() -> logging.Logger:
    """Get the configured logger instance."""
    config = get_config()
    return setup_logging(config.log_level)
