"""
Système d'authentification avancé avec sécurité renforcée.
JWT, sessions, MFA, et protection contre les attaques.
"""

import time
import hashlib
import secrets
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional, Dict, Any, List, Union
from enum import Enum

import jwt
import bcrypt
from fastapi import HTTPException, status, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, Field

from ..config.production_settings import get_settings
from ..cache.redis_manager import get_redis, RedisManager

logger = logging.getLogger(__name__)

class TokenType(str, Enum):
    """Types de tokens supportés."""
    ACCESS = "access"
    REFRESH = "refresh"
    RESET_PASSWORD = "reset_password"
    EMAIL_VERIFICATION = "email_verification"
    MFA = "mfa"

class SessionStatus(str, Enum):
    """Statuts de session."""
    ACTIVE = "active"
    EXPIRED = "expired"
    REVOKED = "revoked"
    SUSPICIOUS = "suspicious"

class AuthAttempt(BaseModel):
    """Modèle pour les tentatives d'authentification."""
    ip_address: str
    user_agent: str
    timestamp: datetime
    success: bool
    failure_reason: Optional[str] = None
    location: Optional[Dict[str, Any]] = None

class SecurityEvent(BaseModel):
    """Modèle pour les événements de sécurité."""
    event_type: str
    user_id: Optional[str] = None
    ip_address: str
    user_agent: str
    timestamp: datetime
    details: Dict[str, Any] = Field(default_factory=dict)
    risk_score: int = Field(ge=0, le=100)

class AdvancedPasswordValidator:
    """Validateur de mot de passe avancé."""
    
    def __init__(self):
        self.settings = get_settings()
        
        # Mots de passe communs à bannir
        self.common_passwords = {
            "password", "123456", "password123", "admin", "qwerty",
            "letmein", "welcome", "monkey", "dragon", "master",
            "123456789", "12345678", "12345", "1234567", "1234567890"
        }
        
        # Patterns dangereux
        self.dangerous_patterns = [
            r"(.)\1{3,}",  # Caractères répétés
            r"123456",     # Séquences numériques
            r"abcdef",     # Séquences alphabétiques
            r"qwerty",     # Patterns clavier
        ]
    
    def validate_password(self, password: str, user_data: Optional[Dict] = None) -> Dict[str, Any]:
        """Valide un mot de passe selon les critères de sécurité."""
        errors = []
        score = 0
        
        # Longueur minimale
        if len(password) < self.settings.security.password_min_length:
            errors.append(f"Le mot de passe doit contenir au moins {self.settings.security.password_min_length} caractères")
        else:
            score += min(20, len(password) * 2)
        
        # Complexité
        has_upper = any(c.isupper() for c in password)
        has_lower = any(c.islower() for c in password)
        has_digit = any(c.isdigit() for c in password)
        has_symbol = any(not c.isalnum() for c in password)
        
        if self.settings.security.password_require_uppercase and not has_upper:
            errors.append("Le mot de passe doit contenir au moins une majuscule")
        elif has_upper:
            score += 15
            
        if self.settings.security.password_require_lowercase and not has_lower:
            errors.append("Le mot de passe doit contenir au moins une minuscule")
        elif has_lower:
            score += 15
            
        if self.settings.security.password_require_numbers and not has_digit:
            errors.append("Le mot de passe doit contenir au moins un chiffre")
        elif has_digit:
            score += 15
            
        if self.settings.security.password_require_symbols and not has_symbol:
            errors.append("Le mot de passe doit contenir au moins un caractère spécial")
        elif has_symbol:
            score += 20
        
        # Vérifier les mots de passe communs
        if password.lower() in self.common_passwords:
            errors.append("Ce mot de passe est trop commun")
            score = max(0, score - 30)
        
        # Vérifier les données utilisateur
        if user_data:
            user_info = " ".join([
                user_data.get("email", ""),
                user_data.get("first_name", ""),
                user_data.get("last_name", ""),
                user_data.get("phone_number", "")
            ]).lower()
            
            if any(part in password.lower() for part in user_info.split() if len(part) > 2):
                errors.append("Le mot de passe ne doit pas contenir d'informations personnelles")
                score = max(0, score - 25)
        
        # Entropie et diversité
        unique_chars = len(set(password))
        if unique_chars < len(password) * 0.6:
            score = max(0, score - 10)
        
        # Score final
        strength = "très faible"
        if score >= 80:
            strength = "très fort"
        elif score >= 60:
            strength = "fort"
        elif score >= 40:
            strength = "moyen"
        elif score >= 20:
            strength = "faible"
        
        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "score": score,
            "strength": strength,
            "requirements_met": {
                "length": len(password) >= self.settings.security.password_min_length,
                "uppercase": has_upper,
                "lowercase": has_lower,
                "numbers": has_digit,
                "symbols": has_symbol
            }
        }

class AdvancedAuthManager:
    """Gestionnaire d'authentification avancé."""
    
    def __init__(self):
        self.settings = get_settings()
        self.password_validator = AdvancedPasswordValidator()
        self.security_bearer = HTTPBearer(auto_error=False)
        
    async def hash_password(self, password: str) -> str:
        """Hash un mot de passe avec bcrypt et salt."""
        salt = bcrypt.gensalt(rounds=self.settings.security.bcrypt_rounds)
        return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
    
    async def verify_password(self, password: str, hashed: str) -> bool:
        """Vérifie un mot de passe contre son hash."""
        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du mot de passe: {e}")
            return False
    
    async def create_token(
        self,
        data: Dict[str, Any],
        token_type: TokenType,
        expires_delta: Optional[timedelta] = None,
        redis_manager: Optional[RedisManager] = None
    ) -> str:
        """Crée un token JWT sécurisé."""
        to_encode = data.copy()
        
        # Timestamps
        now = datetime.now(timezone.utc)
        to_encode["iat"] = now
        to_encode["type"] = token_type.value
        to_encode["jti"] = secrets.token_urlsafe(32)  # JWT ID unique
        
        # Expiration selon le type
        if expires_delta:
            expire = now + expires_delta
        elif token_type == TokenType.ACCESS:
            expire = now + timedelta(minutes=self.settings.security.access_token_expire_minutes)
        elif token_type == TokenType.REFRESH:
            expire = now + timedelta(days=self.settings.security.refresh_token_expire_days)
        elif token_type == TokenType.RESET_PASSWORD:
            expire = now + timedelta(hours=1)
        elif token_type == TokenType.EMAIL_VERIFICATION:
            expire = now + timedelta(days=7)
        elif token_type == TokenType.MFA:
            expire = now + timedelta(minutes=5)
        else:
            expire = now + timedelta(hours=1)
            
        to_encode["exp"] = expire
        
        # Encoder le token
        token = jwt.encode(
            to_encode,
            self.settings.security.secret_key.get_secret_value(),
            algorithm=self.settings.security.algorithm
        )
        
        # Stocker dans Redis pour révocation
        if redis_manager:
            await redis_manager.set(
                f"token:{to_encode['jti']}",
                {
                    "user_id": data.get("sub"),
                    "type": token_type.value,
                    "created_at": now.isoformat(),
                    "expires_at": expire.isoformat()
                },
                expire=int((expire - now).total_seconds())
            )
        
        return token
    
    async def verify_token(
        self,
        token: str,
        expected_type: Optional[TokenType] = None,
        redis_manager: Optional[RedisManager] = None
    ) -> Dict[str, Any]:
        """Vérifie et décode un token JWT."""
        try:
            # Décoder le token
            payload = jwt.decode(
                token,
                self.settings.security.secret_key.get_secret_value(),
                algorithms=[self.settings.security.algorithm]
            )
            
            # Vérifier le type si spécifié
            if expected_type and payload.get("type") != expected_type.value:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Type de token invalide"
                )
            
            # Vérifier si le token est révoqué
            if redis_manager and "jti" in payload:
                token_data = await redis_manager.get(f"token:{payload['jti']}")
                if not token_data:
                    raise HTTPException(
                        status_code=status.HTTP_401_UNAUTHORIZED,
                        detail="Token révoqué"
                    )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token expiré"
            )
        except jwt.JWTError as e:
            logger.warning(f"Erreur JWT: {e}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token invalide"
            )
    
    async def revoke_token(self, jti: str, redis_manager: RedisManager) -> bool:
        """Révoque un token en le supprimant de Redis."""
        return bool(await redis_manager.delete(f"token:{jti}"))
    
    async def revoke_all_user_tokens(self, user_id: str, redis_manager: RedisManager) -> int:
        """Révoque tous les tokens d'un utilisateur."""
        # Cette implémentation nécessiterait un scan Redis
        # Pour la production, il faudrait maintenir un index des tokens par utilisateur
        logger.info(f"Révocation de tous les tokens pour l'utilisateur {user_id}")
        return 0
    
    async def track_auth_attempt(
        self,
        request: Request,
        user_id: Optional[str],
        success: bool,
        failure_reason: Optional[str] = None,
        redis_manager: Optional[RedisManager] = None
    ) -> None:
        """Enregistre une tentative d'authentification."""
        attempt = AuthAttempt(
            ip_address=request.client.host if request.client else "unknown",
            user_agent=request.headers.get("User-Agent", "unknown"),
            timestamp=datetime.now(timezone.utc),
            success=success,
            failure_reason=failure_reason
        )
        
        # Stocker dans Redis pour analyse
        if redis_manager:
            key = f"auth_attempts:{attempt.ip_address}:{user_id or 'anonymous'}"
            attempts = await redis_manager.get(key, default=[])
            attempts.append(attempt.dict())
            
            # Garder seulement les 50 dernières tentatives
            attempts = attempts[-50:]
            
            await redis_manager.set(key, attempts, expire=86400)  # 24h
        
        # Log de sécurité
        if not success:
            logger.warning(
                f"Échec d'authentification: {failure_reason} - "
                f"IP: {attempt.ip_address} - User: {user_id or 'unknown'}"
            )
    
    async def check_brute_force(
        self,
        ip_address: str,
        user_id: Optional[str] = None,
        redis_manager: Optional[RedisManager] = None
    ) -> Dict[str, Any]:
        """Vérifie les tentatives de force brute."""
        if not redis_manager:
            return {"blocked": False, "attempts": 0}
        
        key = f"auth_attempts:{ip_address}:{user_id or 'anonymous'}"
        attempts = await redis_manager.get(key, default=[])
        
        # Compter les échecs récents (dernière heure)
        recent_failures = 0
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)
        
        for attempt in attempts:
            attempt_time = datetime.fromisoformat(attempt["timestamp"].replace("Z", "+00:00"))
            if attempt_time > cutoff_time and not attempt["success"]:
                recent_failures += 1
        
        # Vérifier si bloqué
        max_attempts = self.settings.security.max_login_attempts
        blocked = recent_failures >= max_attempts
        
        if blocked:
            # Enregistrer le blocage
            block_key = f"blocked:{ip_address}:{user_id or 'anonymous'}"
            await redis_manager.set(
                block_key,
                {"blocked_at": datetime.now(timezone.utc).isoformat()},
                expire=self.settings.security.lockout_duration_minutes * 60
            )
        
        return {
            "blocked": blocked,
            "attempts": recent_failures,
            "max_attempts": max_attempts,
            "lockout_duration": self.settings.security.lockout_duration_minutes
        }
    
    async def get_current_user(
        self,
        credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
        redis_manager: RedisManager = Depends(get_redis)
    ) -> Dict[str, Any]:
        """Dépendance FastAPI pour obtenir l'utilisateur actuel."""
        if not credentials:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token d'authentification requis",
                headers={"WWW-Authenticate": "Bearer"}
            )
        
        payload = await self.verify_token(
            credentials.credentials,
            TokenType.ACCESS,
            redis_manager
        )
        
        return payload

# Instance globale
auth_manager = AdvancedAuthManager()

# Dépendances FastAPI
async def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    redis_manager: RedisManager = Depends(get_redis)
) -> Dict[str, Any]:
    """Obtient l'utilisateur actuel depuis le token."""
    return await auth_manager.get_current_user(credentials, redis_manager)

async def get_current_active_user(
    current_user: Dict[str, Any] = Depends(get_current_user)
) -> Dict[str, Any]:
    """Obtient l'utilisateur actuel et vérifie qu'il est actif."""
    # Ici on pourrait ajouter des vérifications supplémentaires
    # comme vérifier si l'utilisateur est banni, suspendu, etc.
    return current_user

def require_roles(*required_roles: str):
    """Décorateur pour exiger certains rôles."""
    def role_checker(current_user: Dict[str, Any] = Depends(get_current_user)) -> Dict[str, Any]:
        user_role = current_user.get("role")
        if user_role not in required_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        return current_user
    return role_checker

