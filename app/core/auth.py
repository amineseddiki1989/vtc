"""
Gestionnaire d'authentification JWT
Module de gestion des tokens et authentification sécurisée
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any
from jose import JWTError, jwt
from passlib.context import CryptContext
from fastapi import HTTPException, status
from config.secure_config import get_config
from app.utils.production_logger import ProductionLogger
import secrets

logger = ProductionLogger(__name__)
config = get_config()

class AuthManager:
    """Gestionnaire d'authentification et de tokens JWT"""

    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.secret_key = config.jwt_secret_key
        self.algorithm = config.jwt_algorithm
        self.expire_minutes = config.jwt_expire_minutes

    def hash_password(self, password: str) -> str:
        """Hache un mot de passe"""
        return self.pwd_context.hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Vérifie un mot de passe"""
        return self.pwd_context.verify(plain_password, hashed_password)

    def create_access_token(self, data: Dict[str, Any], expires_delta: Optional[timedelta] = None) -> str:
        """Crée un token d'accès JWT"""
        to_encode = data.copy()

        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=self.expire_minutes)

        to_encode.update({
            "exp": expire,
            "iat": datetime.utcnow(),
            "jti": secrets.token_urlsafe(16)  # JWT ID unique
        })

        try:
            encoded_jwt = jwt.encode(to_encode, self.secret_key, algorithm=self.algorithm)
            logger.info(f"Token créé pour l'utilisateur {data.get('sub')}")
            return encoded_jwt
        except Exception as e:
            logger.error(f"Erreur lors de la création du token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la génération du token"
            )

    def verify_token(self, token: str) -> Dict[str, Any]:
        """Vérifie et décode un token JWT"""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])

            # Vérifier l'expiration
            exp = payload.get("exp")
            if exp is None:
                raise JWTError("Token sans date d'expiration")

            if datetime.utcnow() > datetime.fromtimestamp(exp):
                raise JWTError("Token expiré")

            return payload

        except JWTError as e:
            logger.warning(f"Token invalide: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide ou expiré",
                headers={"WWW-Authenticate": "Bearer"},
            )
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du token: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur interne du serveur"
            )

    def refresh_token(self, token: str) -> str:
        """Rafraîchit un token existant"""
        try:
            payload = self.verify_token(token)

            # Créer un nouveau token avec les mêmes données
            new_payload = {
                "sub": payload.get("sub"),
                "user_id": payload.get("user_id"),
                "role": payload.get("role")
            }

            return self.create_access_token(new_payload)

        except Exception as e:
            logger.error(f"Erreur lors du rafraîchissement du token: {e}")
            raise

    def generate_password_reset_token(self, user_email: str) -> str:
        """Génère un token de réinitialisation de mot de passe"""
        data = {
            "sub": user_email,
            "type": "password_reset"
        }

        # Token de courte durée (15 minutes)
        expire_delta = timedelta(minutes=15)
        return self.create_access_token(data, expire_delta)

    def verify_password_reset_token(self, token: str) -> Optional[str]:
        """Vérifie un token de réinitialisation de mot de passe"""
        try:
            payload = self.verify_token(token)

            if payload.get("type") != "password_reset":
                return None

            return payload.get("sub")  # Email de l'utilisateur

        except HTTPException:
            return None

# Instance globale
auth_manager = AuthManager()
