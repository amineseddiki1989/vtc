"""
Exceptions de sécurité personnalisées pour l'application VTC.
Gestion sécurisée des erreurs sans exposition d'informations sensibles.
"""

import logging
import traceback
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

from fastapi import HTTPException, status
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class SecurityLevel(str, Enum):
    """Niveaux de sécurité pour les exceptions."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ErrorCategory(str, Enum):
    """Catégories d'erreurs."""
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    VALIDATION = "validation"
    BUSINESS_LOGIC = "business_logic"
    EXTERNAL_SERVICE = "external_service"
    SYSTEM = "system"
    SECURITY = "security"


class ErrorContext(BaseModel):
    """Contexte d'erreur pour le logging."""
    user_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    request_id: Optional[str] = None
    timestamp: datetime = datetime.utcnow()
    additional_data: Dict[str, Any] = {}


class SecureException(Exception):
    """Exception de base sécurisée."""
    
    def __init__(
        self,
        message: str,
        user_message: Optional[str] = None,
        error_code: Optional[str] = None,
        category: ErrorCategory = ErrorCategory.SYSTEM,
        security_level: SecurityLevel = SecurityLevel.LOW,
        context: Optional[ErrorContext] = None,
        log_stack_trace: bool = False
    ):
        super().__init__(message)
        self.message = message
        self.user_message = user_message or "Une erreur s'est produite"
        self.error_code = error_code
        self.category = category
        self.security_level = security_level
        self.context = context or ErrorContext()
        self.log_stack_trace = log_stack_trace
        
        # Log automatique selon le niveau de sécurité
        self._log_error()
    
    def _log_error(self):
        """Log l'erreur selon son niveau de sécurité."""
        log_data = {
            "error_code": self.error_code,
            "category": self.category.value,
            "security_level": self.security_level.value,
            "user_id": self.context.user_id,
            "ip_address": self.context.ip_address,
            "endpoint": self.context.endpoint,
            "timestamp": self.context.timestamp.isoformat()
        }
        
        if self.security_level == SecurityLevel.CRITICAL:
            logger.critical(f"CRITICAL ERROR: {self.message}", extra=log_data)
            if self.log_stack_trace:
                logger.critical(f"Stack trace: {traceback.format_exc()}")
        elif self.security_level == SecurityLevel.HIGH:
            logger.error(f"HIGH SECURITY ERROR: {self.message}", extra=log_data)
            if self.log_stack_trace:
                logger.error(f"Stack trace: {traceback.format_exc()}")
        elif self.security_level == SecurityLevel.MEDIUM:
            logger.warning(f"MEDIUM SECURITY ERROR: {self.message}", extra=log_data)
        else:
            logger.info(f"LOW SECURITY ERROR: {self.message}", extra=log_data)
    
    def to_http_exception(self, status_code: int = status.HTTP_500_INTERNAL_SERVER_ERROR) -> HTTPException:
        """Convertit en HTTPException FastAPI."""
        return HTTPException(
            status_code=status_code,
            detail={
                "message": self.user_message,
                "error_code": self.error_code,
                "category": self.category.value
            }
        )


class AuthenticationException(SecureException):
    """Exception d'authentification."""
    
    def __init__(
        self,
        message: str,
        user_message: str = "Échec de l'authentification",
        error_code: str = "AUTH_FAILED",
        context: Optional[ErrorContext] = None
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.AUTHENTICATION,
            security_level=SecurityLevel.HIGH,
            context=context
        )
    
    def to_http_exception(self) -> HTTPException:
        return super().to_http_exception(status.HTTP_401_UNAUTHORIZED)


class AuthorizationException(SecureException):
    """Exception d'autorisation."""
    
    def __init__(
        self,
        message: str,
        user_message: str = "Accès non autorisé",
        error_code: str = "ACCESS_DENIED",
        context: Optional[ErrorContext] = None
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.AUTHORIZATION,
            security_level=SecurityLevel.HIGH,
            context=context
        )
    
    def to_http_exception(self) -> HTTPException:
        return super().to_http_exception(status.HTTP_403_FORBIDDEN)


class ValidationException(SecureException):
    """Exception de validation."""
    
    def __init__(
        self,
        message: str,
        user_message: str = "Données invalides",
        error_code: str = "VALIDATION_ERROR",
        validation_errors: Optional[List[Dict[str, Any]]] = None,
        context: Optional[ErrorContext] = None
    ):
        self.validation_errors = validation_errors or []
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.VALIDATION,
            security_level=SecurityLevel.LOW,
            context=context
        )
    
    def to_http_exception(self) -> HTTPException:
        detail = {
            "message": self.user_message,
            "error_code": self.error_code,
            "category": self.category.value
        }
        if self.validation_errors:
            detail["validation_errors"] = self.validation_errors
        
        return HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=detail
        )


class BusinessLogicException(SecureException):
    """Exception de logique métier."""
    
    def __init__(
        self,
        message: str,
        user_message: str = "Opération non autorisée",
        error_code: str = "BUSINESS_RULE_VIOLATION",
        context: Optional[ErrorContext] = None
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.BUSINESS_LOGIC,
            security_level=SecurityLevel.MEDIUM,
            context=context
        )
    
    def to_http_exception(self) -> HTTPException:
        return super().to_http_exception(status.HTTP_400_BAD_REQUEST)


class ExternalServiceException(SecureException):
    """Exception de service externe."""
    
    def __init__(
        self,
        message: str,
        service_name: str,
        user_message: str = "Service temporairement indisponible",
        error_code: str = "EXTERNAL_SERVICE_ERROR",
        context: Optional[ErrorContext] = None
    ):
        self.service_name = service_name
        super().__init__(
            message=f"{service_name}: {message}",
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.EXTERNAL_SERVICE,
            security_level=SecurityLevel.MEDIUM,
            context=context
        )
    
    def to_http_exception(self) -> HTTPException:
        return super().to_http_exception(status.HTTP_503_SERVICE_UNAVAILABLE)


class SecurityException(SecureException):
    """Exception de sécurité critique."""
    
    def __init__(
        self,
        message: str,
        user_message: str = "Violation de sécurité détectée",
        error_code: str = "SECURITY_VIOLATION",
        context: Optional[ErrorContext] = None,
        log_stack_trace: bool = True
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.SECURITY,
            security_level=SecurityLevel.CRITICAL,
            context=context,
            log_stack_trace=log_stack_trace
        )
    
    def to_http_exception(self) -> HTTPException:
        return super().to_http_exception(status.HTTP_403_FORBIDDEN)


class RateLimitException(SecureException):
    """Exception de limitation de taux."""
    
    def __init__(
        self,
        message: str,
        retry_after: Optional[int] = None,
        user_message: str = "Trop de requêtes, veuillez réessayer plus tard",
        error_code: str = "RATE_LIMIT_EXCEEDED",
        context: Optional[ErrorContext] = None
    ):
        self.retry_after = retry_after
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.SECURITY,
            security_level=SecurityLevel.HIGH,
            context=context
        )
    
    def to_http_exception(self) -> HTTPException:
        headers = {}
        if self.retry_after:
            headers["Retry-After"] = str(self.retry_after)
        
        return HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "message": self.user_message,
                "error_code": self.error_code,
                "retry_after": self.retry_after
            },
            headers=headers
        )


class DataIntegrityException(SecureException):
    """Exception d'intégrité des données."""
    
    def __init__(
        self,
        message: str,
        user_message: str = "Erreur de données",
        error_code: str = "DATA_INTEGRITY_ERROR",
        context: Optional[ErrorContext] = None
    ):
        super().__init__(
            message=message,
            user_message=user_message,
            error_code=error_code,
            category=ErrorCategory.SYSTEM,
            security_level=SecurityLevel.HIGH,
            context=context,
            log_stack_trace=True
        )
    
    def to_http_exception(self) -> HTTPException:
        return super().to_http_exception(status.HTTP_409_CONFLICT)


# Exceptions spécifiques VTC
class VTCLicenseException(BusinessLogicException):
    """Exception de licence VTC."""
    
    def __init__(
        self,
        message: str,
        license_id: Optional[str] = None,
        user_message: str = "Licence VTC invalide ou expirée",
        context: Optional[ErrorContext] = None
    ):
        self.license_id = license_id
        super().__init__(
            message=message,
            user_message=user_message,
            error_code="VTC_LICENSE_INVALID",
            context=context
        )


class TripStateException(BusinessLogicException):
    """Exception d'état de course."""
    
    def __init__(
        self,
        message: str,
        trip_id: str,
        current_state: str,
        attempted_action: str,
        user_message: str = "Action non autorisée pour cette course",
        context: Optional[ErrorContext] = None
    ):
        self.trip_id = trip_id
        self.current_state = current_state
        self.attempted_action = attempted_action
        super().__init__(
            message=f"Trip {trip_id} in state {current_state}: {message}",
            user_message=user_message,
            error_code="TRIP_STATE_INVALID",
            context=context
        )


class PaymentException(ExternalServiceException):
    """Exception de paiement."""
    
    def __init__(
        self,
        message: str,
        payment_id: Optional[str] = None,
        user_message: str = "Erreur de paiement",
        context: Optional[ErrorContext] = None
    ):
        self.payment_id = payment_id
        super().__init__(
            message=message,
            service_name="Payment Service",
            user_message=user_message,
            error_code="PAYMENT_ERROR",
            context=context
        )


# Utilitaires pour la gestion d'erreurs
def create_error_context(
    request = None,
    user_id: Optional[str] = None,
    additional_data: Optional[Dict[str, Any]] = None
) -> ErrorContext:
    """Crée un contexte d'erreur à partir d'une requête FastAPI."""
    context = ErrorContext()
    
    if request:
        context.ip_address = getattr(request.client, 'host', None) if request.client else None
        context.user_agent = request.headers.get("User-Agent")
        context.endpoint = str(request.url.path) if request.url else None
        context.method = request.method
        context.request_id = request.headers.get("X-Request-ID")
    
    if user_id:
        context.user_id = user_id
    
    if additional_data:
        context.additional_data = additional_data
    
    return context


def handle_database_error(error: Exception, context: Optional[ErrorContext] = None) -> SecureException:
    """Convertit une erreur de base de données en exception sécurisée."""
    error_str = str(error).lower()
    
    if "unique constraint" in error_str or "duplicate" in error_str:
        return ValidationException(
            message=f"Database constraint violation: {error}",
            user_message="Cette donnée existe déjà",
            error_code="DUPLICATE_DATA",
            context=context
        )
    elif "foreign key" in error_str:
        return ValidationException(
            message=f"Foreign key constraint: {error}",
            user_message="Référence de données invalide",
            error_code="INVALID_REFERENCE",
            context=context
        )
    elif "not null" in error_str:
        return ValidationException(
            message=f"Not null constraint: {error}",
            user_message="Données requises manquantes",
            error_code="MISSING_REQUIRED_DATA",
            context=context
        )
    else:
        return DataIntegrityException(
            message=f"Database error: {error}",
            context=context
        )


def sanitize_error_message(message: str) -> str:
    """Nettoie un message d'erreur pour éviter l'exposition d'informations sensibles."""
    # Supprimer les chemins de fichiers
    import re
    message = re.sub(r'/[^\s]*', '[PATH]', message)
    
    # Supprimer les adresses IP
    message = re.sub(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b', '[IP]', message)
    
    # Supprimer les tokens/clés
    message = re.sub(r'[a-zA-Z0-9]{32,}', '[TOKEN]', message)
    
    return message

