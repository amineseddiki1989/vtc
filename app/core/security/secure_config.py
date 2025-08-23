"""
Gestionnaire de configuration sécurisé pour l'application VTC.
Élimine les secrets hardcodés et centralise la gestion des variables sensibles.
"""

import os
import secrets
from typing import Optional, Dict, Any
from pydantic_settings import BaseSettings
from pydantic import SecretStr, Field, validator
from pathlib import Path


class SecureConfig(BaseSettings):
    """Configuration sécurisée avec gestion des secrets via variables d'environnement."""
    
    # === SECRETS CRITIQUES ===
    reset_password_token: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("RESET_PASSWORD_TOKEN", secrets.token_urlsafe(32)))
    )
    jwt_secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("JWT_SECRET_KEY", secrets.token_urlsafe(64)))
    )
    jwt_refresh_secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("JWT_REFRESH_SECRET_KEY", secrets.token_urlsafe(64)))
    )
    
    # === BASE DE DONNÉES ===
    database_password: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("DATABASE_PASSWORD", ""))
    )
    database_url: str = Field(
        default=os.getenv("DATABASE_URL", "postgresql://user:password@localhost/vtc_db")
    )
    
    # === CHIFFREMENT ===
    encryption_password: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("ENCRYPTION_PASSWORD", secrets.token_urlsafe(32)))
    )
    encryption_salt: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("ENCRYPTION_SALT", secrets.token_urlsafe(16)))
    )
    
    # === PAIEMENTS ===
    stripe_secret_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("STRIPE_SECRET_KEY", ""))
    )
    stripe_publishable_key: str = Field(
        default=os.getenv("STRIPE_PUBLISHABLE_KEY", "")
    )
    stripe_webhook_secret: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("STRIPE_WEBHOOK_SECRET", ""))
    )
    
    # === SERVICES EXTERNES ===
    google_maps_api_key: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("GOOGLE_MAPS_API_KEY", ""))
    )
    mapbox_access_token: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("MAPBOX_ACCESS_TOKEN", ""))
    )
    
    # === EMAIL ===
    smtp_password: SecretStr = Field(
        default_factory=lambda: SecretStr(os.getenv("SMTP_PASSWORD", ""))
    )
    smtp_host: str = Field(default=os.getenv("SMTP_HOST", "localhost"))
    smtp_port: int = Field(default=int(os.getenv("SMTP_PORT", "587")))
    smtp_username: str = Field(default=os.getenv("SMTP_USERNAME", ""))
    
    # === SÉCURITÉ ===
    allowed_hosts: str = Field(default=os.getenv("ALLOWED_HOSTS", "localhost,127.0.0.1"))
    cors_origins: str = Field(default=os.getenv("CORS_ORIGINS", "http://localhost:3000"))
    rate_limit_per_minute: int = Field(default=int(os.getenv("RATE_LIMIT_PER_MINUTE", "60")))
    
    # === ENVIRONNEMENT ===
    environment: str = Field(default=os.getenv("ENVIRONMENT", "development"))
    debug: bool = Field(default=os.getenv("DEBUG", "false").lower() == "true")
    log_level: str = Field(default=os.getenv("LOG_LEVEL", "INFO"))
    
    @validator('jwt_secret_key', 'jwt_refresh_secret_key')
    def validate_jwt_keys(cls, v):
        """Valide que les clés JWT sont suffisamment longues."""
        secret_value = v.get_secret_value()
        if len(secret_value) < 32:
            raise ValueError("Les clés JWT doivent faire au moins 32 caractères")
        return v
    
    @validator('environment')
    def validate_environment(cls, v):
        """Valide l'environnement."""
        valid_envs = ['development', 'testing', 'staging', 'production']
        if v not in valid_envs:
            raise ValueError(f"Environnement invalide. Doit être: {', '.join(valid_envs)}")
        return v
    
    @validator('debug')
    def validate_debug_in_production(cls, v, values):
        """S'assure que debug est désactivé en production."""
        if values.get('environment') == 'production' and v:
            raise ValueError("Debug ne peut pas être activé en production")
        return v
    
    def get_allowed_hosts_list(self) -> list:
        """Retourne la liste des hôtes autorisés."""
        return [host.strip() for host in self.allowed_hosts.split(',')]
    
    def get_cors_origins_list(self) -> list:
        """Retourne la liste des origines CORS autorisées."""
        return [origin.strip() for origin in self.cors_origins.split(',')]
    
    def is_production(self) -> bool:
        """Vérifie si on est en environnement de production."""
        return self.environment == 'production'
    
    def is_development(self) -> bool:
        """Vérifie si on est en environnement de développement."""
        return self.environment == 'development'
    
    def get_database_url_with_password(self) -> str:
        """Retourne l'URL de base de données avec le mot de passe."""
        if self.database_password.get_secret_value():
            # Remplacer le mot de passe dans l'URL
            url_parts = self.database_url.split('@')
            if len(url_parts) == 2:
                user_part = url_parts[0].split('://')[1].split(':')[0]
                return f"postgresql://{user_part}:{self.database_password.get_secret_value()}@{url_parts[1]}"
        return self.database_url
    
    def validate_required_secrets(self) -> Dict[str, bool]:
        """Valide que tous les secrets requis sont configurés."""
        required_secrets = {
            'jwt_secret_key': bool(self.jwt_secret_key.get_secret_value()),
            'database_password': bool(self.database_password.get_secret_value()),
            'encryption_password': bool(self.encryption_password.get_secret_value()),
        }
        
        if self.is_production():
            required_secrets.update({
                'stripe_secret_key': bool(self.stripe_secret_key.get_secret_value()),
                'google_maps_api_key': bool(self.google_maps_api_key.get_secret_value()),
                'smtp_password': bool(self.smtp_password.get_secret_value()),
            })
        
        return required_secrets
    
    def get_missing_secrets(self) -> list:
        """Retourne la liste des secrets manquants."""
        validation = self.validate_required_secrets()
        return [secret for secret, is_valid in validation.items() if not is_valid]
    
    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = False
        validate_assignment = True
        extra = "allow"  # Permet les champs supplémentaires du .env


# Instance globale de configuration sécurisée
secure_config = SecureConfig()


def get_secure_config() -> SecureConfig:
    """Retourne l'instance de configuration sécurisée."""
    return secure_config


def validate_configuration() -> bool:
    """Valide la configuration et affiche les erreurs."""
    try:
        missing_secrets = secure_config.get_missing_secrets()
        if missing_secrets:
            print(f"⚠️ Secrets manquants: {', '.join(missing_secrets)}")
            return False
        
        print("✅ Configuration sécurisée validée avec succès")
        return True
    
    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
        return False

