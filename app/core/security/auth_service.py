"""
Service d'authentification JWT avec métriques de performance.
"""

import jwt
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

from ..config.settings import get_settings
from ..exceptions.base import AuthenticationError, ValidationError
from ...services.metrics_service import get_metrics_collector
from ...models.metrics import MetricType, MetricCategory
from ..monitoring.decorators import monitor_function, monitor_business_operation

settings = get_settings()


class AuthService:
    """Service d'authentification JWT avec monitoring intégré."""
    
    def __init__(self):
        self.algorithm = settings.jwt_algorithm
        self.access_token_expire_minutes = settings.access_token_expire_minutes
        self.refresh_token_expire_days = settings.refresh_token_expire_days
        self._revoked_tokens = set()
        self.collector = get_metrics_collector()
    
    def _get_jwt_secret(self) -> str:
        """Récupère la clé secrète JWT."""
        return settings.jwt_secret_key.get_secret_value()
    
    @monitor_business_operation("token_creation", "auth")
    def create_access_token(self, user_id: str, role: str, session_id: str) -> str:
        """Crée un token d'accès JWT."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(minutes=self.access_token_expire_minutes)
        
        payload = {
            "sub": user_id,
            "role": role,
            "session_id": session_id,
            "type": "access",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "jti": str(uuid.uuid4())
        }
        
        token = jwt.encode(payload, self._get_jwt_secret(), algorithm=self.algorithm)
        
        # Métriques spécifiques
        self.collector.record_metric(
            name="auth_access_tokens_created",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={"user_role": role, "token_type": "access"},
            user_id=user_id,
            description="Token d'accès créé"
        )
        
        return token
    
    @monitor_business_operation("token_creation", "auth")
    def create_refresh_token(self, user_id: str, session_id: str) -> str:
        """Crée un token de rafraîchissement."""
        now = datetime.now(timezone.utc)
        expire = now + timedelta(days=self.refresh_token_expire_days)
        
        payload = {
            "sub": user_id,
            "session_id": session_id,
            "type": "refresh",
            "iat": int(now.timestamp()),
            "exp": int(expire.timestamp()),
            "jti": str(uuid.uuid4())
        }
        
        token = jwt.encode(payload, self._get_jwt_secret(), algorithm=self.algorithm)
        
        # Métriques spécifiques
        self.collector.record_metric(
            name="auth_refresh_tokens_created",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={"token_type": "refresh"},
            user_id=user_id,
            description="Token de rafraîchissement créé"
        )
        
        return token
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def verify_token(self, token: str, expected_type: Optional[str] = None) -> Dict[str, Any]:
        """Vérifie et décode un token JWT."""
        if token in self._revoked_tokens:
            # Métrique de token révoqué
            self.collector.record_metric(
                name="auth_token_revoked_attempts",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={"token_type": expected_type or "unknown"},
                description="Tentative d'utilisation de token révoqué"
            )
            raise AuthenticationError("Token révoqué")
        
        try:
            payload = jwt.decode(
                token,
                self._get_jwt_secret(),
                algorithms=[self.algorithm]
            )
            
            if expected_type and payload.get("type") != expected_type:
                # Métrique de type de token invalide
                self.collector.record_metric(
                    name="auth_token_type_mismatch",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels={
                        "expected_type": expected_type,
                        "actual_type": payload.get("type", "unknown")
                    },
                    user_id=payload.get("sub"),
                    description="Type de token invalide"
                )
                raise AuthenticationError(f"Type de token invalide")
            
            # Métrique de vérification réussie
            self.collector.record_metric(
                name="auth_token_verified_success",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={
                    "token_type": payload.get("type", "unknown"),
                    "user_role": payload.get("role", "unknown")
                },
                user_id=payload.get("sub"),
                description="Token vérifié avec succès"
            )
            
            return payload
            
        except jwt.ExpiredSignatureError:
            # Métrique de token expiré
            self.collector.record_metric(
                name="auth_token_expired",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={"token_type": expected_type or "unknown"},
                description="Token expiré"
            )
            raise AuthenticationError("Token expiré")
        except jwt.InvalidTokenError:
            # Métrique de token invalide
            self.collector.record_metric(
                name="auth_token_invalid",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={"token_type": expected_type or "unknown"},
                description="Token invalide"
            )
            raise AuthenticationError("Token invalide")
    
    def verify_access_token(self, token: str) -> Dict[str, Any]:
        """Vérifie un token d'accès."""
        return self.verify_token(token, expected_type="access")
    
    def verify_refresh_token(self, token: str) -> Dict[str, Any]:
        """Vérifie un token de rafraîchissement."""
        return self.verify_token(token, expected_type="refresh")
    
    @monitor_business_operation("token_revocation", "auth")
    def revoke_token(self, token: str) -> bool:
        """Révoque un token."""
        self._revoked_tokens.add(token)
        
        # Métrique de révocation
        self.collector.record_metric(
            name="auth_tokens_revoked",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            description="Token révoqué"
        )
        
        return True
    
    def generate_session_id(self) -> str:
        """Génère un ID de session."""
        session_id = str(uuid.uuid4())
        
        # Métrique de session créée
        self.collector.record_metric(
            name="auth_sessions_created",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            description="Session créée"
        )
        
        return session_id

