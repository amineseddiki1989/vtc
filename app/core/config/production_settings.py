"""
Configuration production avancée avec optimisations et sécurité renforcée.
"""

import os
import secrets
from typing import List, Optional, Dict, Any
from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class DatabaseSettings(BaseModel):
    """Configuration de base de données optimisée."""
    
    # PostgreSQL principal
    host: str = Field(default="localhost")
    port: int = Field(default=5432, ge=1, le=65535)
    name: str = Field(default="uber_api_prod")
    user: str = Field(default="uber_api")
    password: SecretStr = Field(default_factory=lambda: SecretStr(os.getenv("DATABASE_PASSWORD", "")))
    
    # Pool de connexions
    pool_size: int = Field(default=20, ge=5, le=100)
    max_overflow: int = Field(default=30, ge=5, le=200)
    pool_timeout: int = Field(default=30, ge=5, le=300)
    pool_recycle: int = Field(default=3600, ge=300, le=86400)
    
    # AsyncPG settings
    asyncpg_min_size: int = Field(default=10, ge=1, le=50)
    asyncpg_max_size: int = Field(default=50, ge=10, le=200)
    asyncpg_command_timeout: int = Field(default=60, ge=5, le=300)
    
    # Options avancées
    echo: bool = Field(default=False)
    ssl_mode: str = Field(default="prefer")
    connect_timeout: int = Field(default=10, ge=1, le=60)
    
    @property
    def url(self) -> str:
        """URL de connexion PostgreSQL."""
        return (
            f"postgresql://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.ssl_mode}&connect_timeout={self.connect_timeout}"
        )
    
    @property
    def async_url(self) -> str:
        """URL de connexion PostgreSQL asynchrone."""
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
            f"?sslmode={self.ssl_mode}&connect_timeout={self.connect_timeout}"
        )


class RedisSettings(BaseModel):
    """Configuration Redis optimisée."""
    
    host: str = Field(default="localhost")
    port: int = Field(default=6379, ge=1, le=65535)
    db: int = Field(default=0, ge=0, le=15)
    password: Optional[SecretStr] = Field(default=None)
    
    # Pool de connexions
    max_connections: int = Field(default=50, ge=5, le=200)
    socket_timeout: int = Field(default=5, ge=1, le=30)
    connect_timeout: int = Field(default=5, ge=1, le=30)
    
    # SSL
    ssl: bool = Field(default=False)
    ssl_cert_reqs: str = Field(default="required")
    
    @property
    def url(self) -> str:
        """URL de connexion Redis."""
        auth = f":{self.password.get_secret_value()}@" if self.password else ""
        protocol = "rediss" if self.ssl else "redis"
        return f"{protocol}://{auth}{self.host}:{self.port}/{self.db}"


class SecuritySettings(BaseModel):
    """Configuration de sécurité avancée."""
    
    # JWT
    secret_key: SecretStr = Field(default_factory=lambda: SecretStr(secrets.token_urlsafe(64)))
    algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    
    # Mots de passe
    password_min_length: int = Field(default=12, ge=8, le=128)
    password_require_uppercase: bool = Field(default=True)
    password_require_lowercase: bool = Field(default=True)
    password_require_numbers: bool = Field(default=True)
    password_require_symbols: bool = Field(default=True)
    bcrypt_rounds: int = Field(default=14, ge=12, le=16)
    
    # Sessions et tentatives
    max_login_attempts: int = Field(default=5, ge=3, le=10)
    lockout_duration_minutes: int = Field(default=30, ge=5, le=1440)
    session_timeout_minutes: int = Field(default=60, ge=15, le=480)
    
    # Rate limiting
    rate_limit_requests: int = Field(default=100, ge=10, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=60, le=3600)
    rate_limit_burst: int = Field(default=20, ge=5, le=100)
    
    # Headers de sécurité
    enable_security_headers: bool = Field(default=True)
    content_security_policy: str = Field(
        default="default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
    )
    
    # CORS
    cors_allowed_origins: List[str] = Field(default=["https://yourdomain.com"])
    cors_allowed_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_allowed_headers: List[str] = Field(default=["*"])
    cors_allow_credentials: bool = Field(default=True)
    cors_max_age: int = Field(default=86400)


class MonitoringSettings(BaseModel):
    """Configuration de monitoring et observabilité."""
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="json")
    log_file: Optional[str] = Field(default="./logs/app.log")
    log_rotation: str = Field(default="1 day")
    log_retention: str = Field(default="30 days")
    
    # Métriques
    enable_metrics: bool = Field(default=True)
    metrics_port: int = Field(default=9090, ge=1024, le=65535)
    metrics_path: str = Field(default="/metrics")
    
    # Health checks
    health_check_interval: int = Field(default=30, ge=5, le=300)
    health_check_timeout: int = Field(default=5, ge=1, le=30)
    
    # Tracing
    enable_tracing: bool = Field(default=True)
    jaeger_endpoint: Optional[str] = Field(default=None)
    trace_sample_rate: float = Field(default=0.1, ge=0.0, le=1.0)


class PerformanceSettings(BaseModel):
    """Configuration de performance."""
    
    # Serveur
    workers: int = Field(default=4, ge=1, le=32)
    worker_class: str = Field(default="uvicorn.workers.UvicornWorker")
    max_requests: int = Field(default=1000, ge=100, le=10000)
    max_requests_jitter: int = Field(default=100, ge=10, le=1000)
    timeout: int = Field(default=30, ge=5, le=300)
    keepalive: int = Field(default=5, ge=1, le=30)
    
    # Cache
    cache_default_ttl: int = Field(default=300, ge=60, le=3600)
    cache_max_size: int = Field(default=1000, ge=100, le=10000)
    
    # Limites
    max_request_size: int = Field(default=16 * 1024 * 1024)  # 16MB
    max_file_size: int = Field(default=10 * 1024 * 1024)    # 10MB
    request_timeout: int = Field(default=30, ge=5, le=300)


class ProductionSettings(BaseSettings):
    """Configuration principale pour la production."""
    
    model_config = ConfigDict(
        env_file=".env.production",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
        env_nested_delimiter="__"
    )
    
    # Application
    app_name: str = Field(default="Uber API")
    app_version: str = Field(default="2.0.0")
    environment: str = Field(default="production")
    debug: bool = Field(default=False)
    
    # Serveur
    host: str = Field(default="0.0.0.0")
    port: int = Field(default=8000, ge=1024, le=65535)
    
    # Configurations spécialisées
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    monitoring: MonitoringSettings = Field(default_factory=MonitoringSettings)
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    
    # Services externes
    stripe_secret_key: Optional[SecretStr] = Field(default=None)
    stripe_webhook_secret: Optional[SecretStr] = Field(default=None)
    sendgrid_api_key: Optional[SecretStr] = Field(default=None)
    twilio_account_sid: Optional[str] = Field(default=None)
    twilio_auth_token: Optional[SecretStr] = Field(default=None)
    firebase_credentials: Optional[str] = Field(default=None)
    google_maps_api_key: Optional[SecretStr] = Field(default=None)
    
    @property
    def is_production(self) -> bool:
        """Vérifie si on est en production."""
        return self.environment.lower() == "production"
    
    @property
    def database_url(self) -> str:
        """URL de base de données."""
        return self.database.url
    
    @property
    def async_database_url(self) -> str:
        """URL de base de données asynchrone."""
        return self.database.async_url
    
    @property
    def redis_url(self) -> str:
        """URL Redis."""
        return self.redis.url
    
    # Propriétés de compatibilité avec l'ancienne configuration
    @property
    def secret_key(self) -> str:
        return self.security.secret_key.get_secret_value()
    
    @property
    def algorithm(self) -> str:
        return self.security.algorithm
    
    @property
    def db_pool_size(self) -> int:
        return self.database.pool_size
    
    @property
    def db_max_overflow(self) -> int:
        return self.database.max_overflow
    
    @property
    def db_pool_timeout(self) -> int:
        return self.database.pool_timeout
    
    @property
    def db_pool_recycle(self) -> int:
        return self.database.pool_recycle
    
    @property
    def database_echo(self) -> bool:
        return self.database.echo
    
    @property
    def redis_max_connections(self) -> int:
        return self.redis.max_connections
    
    @property
    def redis_socket_timeout(self) -> int:
        return self.redis.socket_timeout
    
    @property
    def redis_connect_timeout(self) -> int:
        return self.redis.connect_timeout
    
    @property
    def asyncpg_min_size(self) -> int:
        return self.database.asyncpg_min_size
    
    @property
    def asyncpg_max_size(self) -> int:
        return self.database.asyncpg_max_size
    
    @property
    def asyncpg_command_timeout(self) -> int:
        return self.database.asyncpg_command_timeout


@lru_cache()
def get_production_settings() -> ProductionSettings:
    """Retourne la configuration production (cached)."""
    return ProductionSettings()


# Fonction de compatibilité
def get_settings() -> ProductionSettings:
    """Alias pour la compatibilité."""
    return get_production_settings()

