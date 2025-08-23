"""
Exceptions personnalisées pour l'API Uber.
"""

from datetime import datetime
from typing import Optional, Any, Dict


class UberAPIException(Exception):
    """Exception de base pour l'API Uber."""
    
    def __init__(
        self,
        message: str,
        code: str = "GENERIC_ERROR",
        details: Optional[Dict[str, Any]] = None
    ):
        self.message = message
        self.code = code
        self.details = details or {}
        self.timestamp = datetime.utcnow()
        super().__init__(self.message)


class ValidationError(UberAPIException):
    """Erreur de validation des données."""
    
    def __init__(self, message: str, details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "VALIDATION_ERROR", details)


class AuthenticationError(UberAPIException):
    """Erreur d'authentification."""
    
    def __init__(self, message: str = "Authentification échouée", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHENTICATION_ERROR", details)


class AuthorizationError(UberAPIException):
    """Erreur d'autorisation."""
    
    def __init__(self, message: str = "Accès non autorisé", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "AUTHORIZATION_ERROR", details)


class NotFoundError(UberAPIException):
    """Erreur de ressource non trouvée."""
    
    def __init__(self, message: str = "Ressource non trouvée", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "NOT_FOUND_ERROR", details)


class ConflictError(UberAPIException):
    """Erreur de conflit."""
    
    def __init__(self, message: str = "Conflit détecté", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "CONFLICT_ERROR", details)


class DatabaseError(UberAPIException):
    """Erreur de base de données."""
    
    def __init__(self, message: str = "Erreur de base de données", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "DATABASE_ERROR", details)


class RateLimitError(UberAPIException):
    """Erreur de limitation de taux."""
    
    def __init__(self, message: str = "Limite de taux dépassée", details: Optional[Dict[str, Any]] = None):
        super().__init__(message, "RATE_LIMIT_ERROR", details)

