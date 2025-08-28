"""
Configuration sécurisée - Fix ValidationInfo pour Pydantic V2
Module de gestion des configurations avec validation et sécurité renforcée
"""

import os
from typing import List, Optional, Any
from pydantic import BaseSettings, Field, validator
from pydantic import ValidationError  # Fix: Import correct pour Pydantic V2
import secrets
import logging
from pathlib import Path

class SecureConfig(BaseSettings):
    """
    Configuration sécurisée avec validation Pydantic V2
    Fix: Utilisation de ValidationError au lieu de ValidationInfo
    """

    # Configuration de base
    app_name: str = Field(default="VTC Management System", description="Nom de l'application")
    app_version: str = Field(default="1.0.0", description="Version de l'application")
    debug: bool = Field(default=False, description="Mode debug")

    # Configuration de la base de données
    database_url: str = Field(
        default="postgresql://vtc_user:vtc_password@localhost:5432/vtc_db",
        description="URL de connexion à la base de données",
        env="DATABASE_URL"
    )

    # Configuration JWT
    jwt_secret_key: str = Field(
        default_factory=lambda: secrets.token_urlsafe(32),
        description="Clé secrète pour JWT",
        env="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", description="Algorithme JWT")
    jwt_expire_minutes: int = Field(default=60, description="Durée d'expiration JWT en minutes")

    # Configuration CORS
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        description="Origins autorisées pour CORS",
        env="CORS_ORIGINS"
    )

    # Configuration Redis (optionnel)
    redis_url: Optional[str] = Field(
        default=None,
        description="URL de connexion Redis pour le cache",
        env="REDIS_URL"
    )

    # Configuration email
    smtp_server: Optional[str] = Field(default=None, env="SMTP_SERVER")
    smtp_port: int = Field(default=587, env="SMTP_PORT")
    smtp_username: Optional[str] = Field(default=None, env="SMTP_USERNAME")
    smtp_password: Optional[str] = Field(default=None, env="SMTP_PASSWORD")

    # Configuration de sécurité
    max_login_attempts: int = Field(default=5, description="Tentatives de connexion max")
    session_timeout: int = Field(default=3600, description="Timeout de session en secondes")

    # Configuration de l'API
    api_rate_limit: int = Field(default=100, description="Limite de requêtes par minute")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore les variables d'environnement non définies

    @validator('database_url')
    def validate_database_url(cls, v):
        """Validation de l'URL de base de données"""
        if not v or not v.startswith(('postgresql://', 'mysql://', 'sqlite://')):
            raise ValueError("URL de base de données invalide")
        return v

    @validator('jwt_secret_key')
    def validate_jwt_secret(cls, v):
        """Validation de la clé secrète JWT"""
        if not v or len(v) < 32:
            raise ValueError("La clé JWT doit faire au moins 32 caractères")
        return v

    @validator('cors_origins')
    def validate_cors_origins(cls, v):
        """Validation des origins CORS"""
        if isinstance(v, str):
            origins = [origin.strip() for origin in v.split(',')]
            for origin in origins:
                if not origin.startswith(('http://', 'https://')):
                    raise ValueError(f"Origin CORS invalide: {origin}")
        return v

    @validator('jwt_expire_minutes')
    def validate_jwt_expire(cls, v):
        """Validation de la durée d'expiration JWT"""
        if v <= 0 or v > 43200:  # Max 30 jours
            raise ValueError("Durée d'expiration JWT invalide (1-43200 minutes)")
        return v

    def get_cors_origins(self) -> List[str]:
        """Retourne la liste des origins CORS"""
        if isinstance(self.cors_origins, str):
            return [origin.strip() for origin in self.cors_origins.split(',')]
        return self.cors_origins or []

    def is_production(self) -> bool:
        """Vérifie si l'environnement est en production"""
        return not self.debug and os.getenv('ENVIRONMENT', '').lower() == 'production'

    def get_log_level(self) -> str:
        """Retourne le niveau de log approprié"""
        if self.debug:
            return "DEBUG"
        return os.getenv('LOG_LEVEL', 'INFO').upper()

    def mask_sensitive_data(self) -> dict:
        """Retourne la config avec les données sensibles masquées"""
        config_dict = self.dict()

        # Masquer les données sensibles
        sensitive_keys = ['jwt_secret_key', 'database_url', 'smtp_password', 'redis_url']

        for key in sensitive_keys:
            if key in config_dict and config_dict[key]:
                config_dict[key] = f"{'*' * (len(str(config_dict[key])) - 4)}{str(config_dict[key])[-4:]}"

        return config_dict

    @classmethod
    def load_from_env(cls, env_file: str = ".env"):
        """Charge la configuration depuis un fichier d'environnement"""
        try:
            if Path(env_file).exists():
                return cls(_env_file=env_file)
            else:
                logging.warning(f"Fichier {env_file} non trouvé, utilisation des valeurs par défaut")
                return cls()
        except ValidationError as e:  # Fix: Utilisation de ValidationError
            logging.error(f"Erreur de validation de configuration: {e}")
            raise
        except Exception as e:
            logging.error(f"Erreur lors du chargement de la configuration: {e}")
            raise

# Instance globale de configuration
try:
    config = SecureConfig.load_from_env()
    logging.info("✅ Configuration chargée avec succès")
except Exception as e:
    logging.error(f"❌ Erreur critique lors du chargement de la configuration: {e}")
    # Configuration par défaut en mode dégradé
    config = SecureConfig()
    logging.warning("⚠️ Utilisation de la configuration par défaut")

# Fonctions utilitaires
def get_config() -> SecureConfig:
    """Retourne l'instance de configuration globale"""
    return config

def reload_config(env_file: str = ".env") -> SecureConfig:
    """Recharge la configuration"""
    global config
    config = SecureConfig.load_from_env(env_file)
    return config

def validate_config() -> bool:
    """Valide la configuration actuelle"""
    try:
        # Vérifications supplémentaires
        if config.is_production() and config.jwt_secret_key.startswith('default'):
            logging.error("❌ Clé JWT par défaut détectée en production!")
            return False

        if config.debug and config.is_production():
            logging.warning("⚠️ Mode debug activé en production!")

        logging.info("✅ Configuration validée")
        return True

    except Exception as e:
        logging.error(f"❌ Erreur lors de la validation de la configuration: {e}")
        return False
