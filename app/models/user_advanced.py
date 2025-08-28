"""
Gestion avancée des utilisateurs - Fonctionnalités étendues
Module complémentaire pour la gestion fine des profils utilisateurs
"""

from typing import Optional, Dict, List, Any
from datetime import datetime, timedelta
from pydantic import BaseModel, Field, validator
from sqlalchemy import Column, Integer, String, DateTime, Boolean, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from app.utils.production_logger import ProductionLogger
import bcrypt
import json

Base = declarative_base()
logger = ProductionLogger(__name__)

class UserAdvanced(Base):
    """
    Modèle avancé d'utilisateur avec fonctionnalités étendues
    """
    __tablename__ = "users_advanced"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, index=True, nullable=False)  # Référence vers users de base

    # Préférences utilisateur
    preferences = Column(JSON, default=dict)

    # Paramètres de sécurité avancés
    two_factor_enabled = Column(Boolean, default=False)
    two_factor_secret = Column(String(255), nullable=True)

    # Historique des connexions
    last_login_ip = Column(String(45), nullable=True)  # Support IPv6
    last_login_device = Column(String(255), nullable=True)
    login_attempts = Column(Integer, default=0)
    locked_until = Column(DateTime, nullable=True)

    # Données de profil étendues
    profile_data = Column(JSON, default=dict)
    notification_settings = Column(JSON, default=dict)

    # Audit
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

class UserPreferences(BaseModel):
    """Schema pour les préférences utilisateur"""
    language: str = Field(default="fr", description="Langue préférée")
    theme: str = Field(default="light", description="Thème de l'interface")
    timezone: str = Field(default="Europe/Paris", description="Fuseau horaire")
    notifications_email: bool = Field(default=True, description="Notifications par email")
    notifications_sms: bool = Field(default=False, description="Notifications par SMS")

    @validator('language')
    def validate_language(cls, v):
        allowed_languages = ['fr', 'en', 'es', 'de', 'it']
        if v not in allowed_languages:
            raise ValueError(f"Langue non supportée: {v}")
        return v

    @validator('theme')
    def validate_theme(cls, v):
        allowed_themes = ['light', 'dark', 'auto']
        if v not in allowed_themes:
            raise ValueError(f"Thème non supporté: {v}")
        return v

class NotificationSettings(BaseModel):
    """Configuration des notifications"""
    booking_confirmation: bool = Field(default=True)
    booking_reminder: bool = Field(default=True)
    driver_arrival: bool = Field(default=True)
    trip_completion: bool = Field(default=True)
    promotions: bool = Field(default=False)
    security_alerts: bool = Field(default=True)

    # Horaires de notification
    quiet_hours_start: Optional[str] = Field(default="22:00", description="Début heures silencieuses")
    quiet_hours_end: Optional[str] = Field(default="08:00", description="Fin heures silencieuses")

class UserAdvancedService:
    """Service de gestion avancée des utilisateurs"""

    @staticmethod
    async def create_advanced_profile(user_id: int, preferences: Optional[Dict] = None) -> Dict:
        """Crée un profil avancé pour un utilisateur"""
        try:
            default_preferences = UserPreferences().dict()
            default_notifications = NotificationSettings().dict()

            # Merge avec les préférences fournies
            if preferences:
                default_preferences.update(preferences)

            profile_data = {
                "preferences": default_preferences,
                "notification_settings": default_notifications,
                "security_settings": {
                    "password_last_changed": datetime.utcnow().isoformat(),
                    "login_history": []
                }
            }

            logger.info(f"Profil avancé créé pour l'utilisateur {user_id}")
            return profile_data

        except Exception as e:
            logger.error(f"Erreur lors de la création du profil avancé: {e}", user_id=user_id)
            raise

    @staticmethod
    async def update_preferences(user_id: int, preferences: Dict) -> bool:
        """Met à jour les préférences utilisateur"""
        try:
            # Validation des préférences
            validated_prefs = UserPreferences(**preferences)

            # Simulation de mise à jour en base
            logger.info(f"Préférences mises à jour pour l'utilisateur {user_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des préférences: {e}", user_id=user_id)
            return False

    @staticmethod
    async def update_notification_settings(user_id: int, settings: Dict) -> bool:
        """Met à jour les paramètres de notification"""
        try:
            # Validation des paramètres
            validated_settings = NotificationSettings(**settings)

            # Simulation de mise à jour en base
            logger.info(f"Paramètres de notification mis à jour pour l'utilisateur {user_id}")
            return True

        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour des notifications: {e}", user_id=user_id)
            return False

    @staticmethod
    async def log_login_attempt(user_id: int, ip_address: str, device_info: str, success: bool) -> None:
        """Enregistre une tentative de connexion"""
        try:
            login_data = {
                "timestamp": datetime.utcnow().isoformat(),
                "ip_address": ip_address,
                "device": device_info,
                "success": success
            }

            if success:
                logger.info(f"Connexion réussie pour l'utilisateur {user_id}", **login_data)
            else:
                logger.warning(f"Tentative de connexion échouée pour l'utilisateur {user_id}", **login_data)

        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement de la tentative de connexion: {e}")

    @staticmethod
    async def check_account_lockout(user_id: int, max_attempts: int = 5) -> Dict:
        """Vérifie si le compte doit être verrouillé"""
        try:
            # Simulation de vérification des tentatives
            # En production, ceci interrogerait la base de données

            current_attempts = 0  # À remplacer par une vraie requête

            if current_attempts >= max_attempts:
                lockout_until = datetime.utcnow() + timedelta(minutes=15)
                logger.warning(f"Compte verrouillé pour l'utilisateur {user_id}", 
                             attempts=current_attempts, 
                             lockout_until=lockout_until.isoformat())

                return {
                    "locked": True,
                    "lockout_until": lockout_until,
                    "remaining_time": 15 * 60  # 15 minutes en secondes
                }

            return {
                "locked": False,
                "attempts_remaining": max_attempts - current_attempts
            }

        except Exception as e:
            logger.error(f"Erreur lors de la vérification du verrouillage: {e}", user_id=user_id)
            return {"locked": False, "error": str(e)}

    @staticmethod
    async def enable_two_factor(user_id: int) -> Dict:
        """Active l'authentification à deux facteurs"""
        try:
            import pyotp

            # Génération du secret TOTP
            secret = pyotp.random_base32()

            # Génération de l'URL pour le QR code
            totp = pyotp.TOTP(secret)
            provisioning_uri = totp.provisioning_uri(
                name=f"user_{user_id}",
                issuer_name="VTC Management"
            )

            logger.info(f"2FA activé pour l'utilisateur {user_id}")

            return {
                "secret": secret,
                "qr_uri": provisioning_uri,
                "backup_codes": [pyotp.random_base32()[:8] for _ in range(10)]
            }

        except ImportError:
            logger.error("PyOTP non installé pour l'activation 2FA")
            return {"error": "2FA non disponible"}
        except Exception as e:
            logger.error(f"Erreur lors de l'activation 2FA: {e}", user_id=user_id)
            return {"error": str(e)}

    @staticmethod
    async def verify_two_factor(user_id: int, secret: str, token: str) -> bool:
        """Vérifie un token 2FA"""
        try:
            import pyotp

            totp = pyotp.TOTP(secret)
            is_valid = totp.verify(token)

            if is_valid:
                logger.info(f"Token 2FA valide pour l'utilisateur {user_id}")
            else:
                logger.warning(f"Token 2FA invalide pour l'utilisateur {user_id}")

            return is_valid

        except ImportError:
            logger.error("PyOTP non installé pour la vérification 2FA")
            return False
        except Exception as e:
            logger.error(f"Erreur lors de la vérification 2FA: {e}", user_id=user_id)
            return False

# Fonctions utilitaires
async def get_user_preferences(user_id: int) -> Dict:
    """Récupère les préférences d'un utilisateur"""
    service = UserAdvancedService()
    # En production, ceci ferait une requête en base
    return UserPreferences().dict()

async def update_user_preferences(user_id: int, preferences: Dict) -> bool:
    """Met à jour les préférences d'un utilisateur"""
    service = UserAdvancedService()
    return await service.update_preferences(user_id, preferences)
