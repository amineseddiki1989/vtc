"""
Module de gestion des exceptions sécurisées.
"""

from .security_exceptions import (
    SecureException,
    AuthenticationException,
    AuthorizationException,
    ValidationException,
    BusinessLogicException,
    ExternalServiceException,
    SecurityException,
    RateLimitException,
    DataIntegrityException,
    VTCLicenseException,
    TripStateException,
    PaymentException,
    ErrorContext,
    ErrorCategory,
    SecurityLevel,
    create_error_context,
    handle_database_error,
    sanitize_error_message
)

from .error_handler import (
    GlobalErrorHandler,
    RequestLoggingMiddleware,
    setup_error_handlers,
    safe_execute,
    safe_execute_async
)

__all__ = [
    # Exceptions
    "SecureException",
    "AuthenticationException", 
    "AuthorizationException",
    "ValidationException",
    "BusinessLogicException",
    "ExternalServiceException",
    "SecurityException",
    "RateLimitException",
    "DataIntegrityException",
    "VTCLicenseException",
    "TripStateException",
    "PaymentException",
    
    # Enums et modèles
    "ErrorContext",
    "ErrorCategory",
    "SecurityLevel",
    
    # Utilitaires
    "create_error_context",
    "handle_database_error",
    "sanitize_error_message",
    
    # Gestionnaires
    "GlobalErrorHandler",
    "RequestLoggingMiddleware", 
    "setup_error_handlers",
    "safe_execute",
    "safe_execute_async"
]

