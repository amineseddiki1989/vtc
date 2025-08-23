"""
Configuration système production-ready sécurisée pour l'API Uber.
Version corrigée et fonctionnelle.
"""

import os
import secrets
from typing import List, Optional
from functools import lru_cache

from pydantic import BaseModel, Field, SecretStr, field_validator, ConfigDict
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Configuration principale de l'application."""
    
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = Field(default="Uber API")
    app_version: str = Field(default="2.0.0")
    debug: bool = Field(default=False)
    environment: str = Field(default="development")
    
    # Serveur - Bind sur toutes les interfaces pour permettre l'accès externe (Docker/déploiement)
    host: str = Field(default="0.0.0.0")  # nosec B104 - Nécessaire pour déploiement
    port: int = Field(default=8000, ge=1, le=65535)
    
    # Sécurité - Clés générées aléatoirement
    secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(64))
    )
    jwt_secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(secrets.token_urlsafe(64))
    )
    jwt_algorithm: str = Field(default="HS256")
    access_token_expire_minutes: int = Field(default=15, ge=5, le=60)
    refresh_token_expire_days: int = Field(default=7, ge=1, le=30)
    
    # Mots de passe
    password_min_length: int = Field(default=8, ge=6, le=128)
    bcrypt_rounds: int = Field(default=12, ge=10, le=16)
    
    # Sessions
    max_login_attempts: int = Field(default=5, ge=3, le=10)
    lockout_duration_minutes: int = Field(default=30, ge=5, le=1440)
    
    # Rate limiting
    rate_limit_requests: int = Field(default=100, ge=10, le=1000)
    rate_limit_window_seconds: int = Field(default=60, ge=60, le=3600)
    
    # Base de données
    database_url: str = Field(default="sqlite:///./uber_api.db")
    database_echo: bool = Field(default=False)
    
    # Redis
    redis_url: str = Field(default="redis://localhost:6379/0")
    redis_max_connections: int = Field(default=20, ge=5, le=100)
    
    # CORS - Configuration sécurisée
    cors_allowed_origins: List[str] = Field(default=["http://localhost:3000", "http://localhost:8080"])
    cors_allowed_methods: List[str] = Field(default=["GET", "POST", "PUT", "DELETE", "OPTIONS"])
    cors_allowed_headers: List[str] = Field(default=["Authorization", "Content-Type", "Accept"])
    cors_allow_credentials: bool = Field(default=True)
    
    # Logging
    log_level: str = Field(default="INFO")
    log_format: str = Field(default="text")
    
    # Monitoring
    enable_metrics: bool = Field(default=True)
    
    @property
    def is_production(self) -> bool:
        """Vérifie si on est en production."""
        return self.environment.lower() == "production"
    
    @property
    def is_development(self) -> bool:
        """Vérifie si on est en développement."""
        return self.environment.lower() == "development"
    
    @field_validator('environment')
    @classmethod
    def validate_environment(cls, v):
        """Valide l'environnement."""
        allowed_envs = ["development", "staging", "production"]
        if v.lower() not in allowed_envs:
            raise ValueError(f"Environnement doit être un de: {allowed_envs}")
        return v.lower()
    
    @field_validator('debug')
    @classmethod
    def validate_debug_in_production(cls, v, info):
        """Interdit le debug en production."""
        # Vérification sécurisée de l'environnement
        is_production = False
        if info and hasattr(info, 'data'):
            data = info.data
            if isinstance(data, dict) and data.get('environment') == 'production':
                is_production = True
        
        if is_production and v:
            raise ValueError("Debug mode interdit en production")
        return v


@lru_cache()
def get_settings() -> Settings:
    """Récupère la configuration de l'application (avec cache)."""
    return Settings()


def validate_production_config():
    """Valide la configuration pour la production."""
    settings = get_settings()
    
    if settings.is_production:
        if settings.debug:
            raise RuntimeError("Debug mode activé en production")
        
        if settings.log_level.upper() == "DEBUG":
            raise RuntimeError("Log level DEBUG en production")
        
        # Vérifier que les clés ne sont pas des valeurs par défaut
        secret_key = settings.secret_key.get_secret_value()
        if len(secret_key) < 32:
            raise RuntimeError("Clé secrète trop courte en production")

