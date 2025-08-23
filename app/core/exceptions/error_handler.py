"""
Gestionnaire d'erreurs global pour l'application VTC.
Centralise la gestion des exceptions et la sécurisation des réponses.
"""

import logging
import traceback
from typing import Dict, Any, Optional
from datetime import datetime

from fastapi import Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from sqlalchemy.exc import SQLAlchemyError
from pydantic import ValidationError

from .security_exceptions import (
    SecureException, ErrorContext, create_error_context,
    handle_database_error, sanitize_error_message
)

logger = logging.getLogger(__name__)


class GlobalErrorHandler:
    """Gestionnaire d'erreurs global sécurisé."""
    
    def __init__(self, app):
        self.app = app
        self._setup_handlers()
    
    def _setup_handlers(self):
        """Configure les gestionnaires d'erreurs."""
        
        @self.app.exception_handler(SecureException)
        async def secure_exception_handler(request: Request, exc: SecureException):
            """Gestionnaire pour les exceptions sécurisées."""
            return JSONResponse(
                status_code=exc.to_http_exception().status_code,
                content=exc.to_http_exception().detail
            )
        
        @self.app.exception_handler(HTTPException)
        async def http_exception_handler(request: Request, exc: HTTPException):
            """Gestionnaire pour les exceptions HTTP FastAPI."""
            context = create_error_context(request)
            
            # Log selon le code de statut
            if exc.status_code >= 500:
                logger.error(
                    f"HTTP {exc.status_code}: {exc.detail}",
                    extra={
                        "status_code": exc.status_code,
                        "endpoint": context.endpoint,
                        "method": context.method,
                        "ip_address": context.ip_address
                    }
                )
            elif exc.status_code >= 400:
                logger.warning(
                    f"HTTP {exc.status_code}: {exc.detail}",
                    extra={
                        "status_code": exc.status_code,
                        "endpoint": context.endpoint,
                        "method": context.method,
                        "ip_address": context.ip_address
                    }
                )
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "message": exc.detail if isinstance(exc.detail, str) else exc.detail.get("message", "Erreur"),
                    "error_code": "HTTP_ERROR",
                    "status_code": exc.status_code
                }
            )
        
        @self.app.exception_handler(StarletteHTTPException)
        async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
            """Gestionnaire pour les exceptions HTTP Starlette."""
            context = create_error_context(request)
            
            logger.warning(
                f"Starlette HTTP {exc.status_code}: {exc.detail}",
                extra={
                    "status_code": exc.status_code,
                    "endpoint": context.endpoint,
                    "method": context.method,
                    "ip_address": context.ip_address
                }
            )
            
            return JSONResponse(
                status_code=exc.status_code,
                content={
                    "message": exc.detail,
                    "error_code": "HTTP_ERROR",
                    "status_code": exc.status_code
                }
            )
        
        @self.app.exception_handler(RequestValidationError)
        async def validation_exception_handler(request: Request, exc: RequestValidationError):
            """Gestionnaire pour les erreurs de validation Pydantic."""
            context = create_error_context(request)
            
            # Nettoyer les erreurs de validation
            cleaned_errors = []
            for error in exc.errors():
                cleaned_error = {
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                }
                cleaned_errors.append(cleaned_error)
            
            logger.info(
                f"Validation error: {len(cleaned_errors)} errors",
                extra={
                    "endpoint": context.endpoint,
                    "method": context.method,
                    "ip_address": context.ip_address,
                    "validation_errors": cleaned_errors
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "message": "Données de requête invalides",
                    "error_code": "VALIDATION_ERROR",
                    "validation_errors": cleaned_errors
                }
            )
        
        @self.app.exception_handler(ValidationError)
        async def pydantic_validation_handler(request: Request, exc: ValidationError):
            """Gestionnaire pour les erreurs de validation Pydantic directes."""
            context = create_error_context(request)
            
            cleaned_errors = []
            for error in exc.errors():
                cleaned_error = {
                    "field": ".".join(str(loc) for loc in error["loc"]),
                    "message": error["msg"],
                    "type": error["type"]
                }
                cleaned_errors.append(cleaned_error)
            
            logger.info(
                f"Pydantic validation error: {len(cleaned_errors)} errors",
                extra={
                    "endpoint": context.endpoint,
                    "method": context.method,
                    "ip_address": context.ip_address,
                    "validation_errors": cleaned_errors
                }
            )
            
            return JSONResponse(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                content={
                    "message": "Erreur de validation des données",
                    "error_code": "PYDANTIC_VALIDATION_ERROR",
                    "validation_errors": cleaned_errors
                }
            )
        
        @self.app.exception_handler(SQLAlchemyError)
        async def database_exception_handler(request: Request, exc: SQLAlchemyError):
            """Gestionnaire pour les erreurs de base de données."""
            context = create_error_context(request)
            
            # Convertir en exception sécurisée
            secure_exc = handle_database_error(exc, context)
            
            logger.error(
                f"Database error: {sanitize_error_message(str(exc))}",
                extra={
                    "endpoint": context.endpoint,
                    "method": context.method,
                    "ip_address": context.ip_address,
                    "error_type": type(exc).__name__
                }
            )
            
            return JSONResponse(
                status_code=secure_exc.to_http_exception().status_code,
                content=secure_exc.to_http_exception().detail
            )
        
        @self.app.exception_handler(Exception)
        async def general_exception_handler(request: Request, exc: Exception):
            """Gestionnaire pour toutes les autres exceptions."""
            context = create_error_context(request)
            
            # Log complet pour les erreurs non gérées
            logger.critical(
                f"Unhandled exception: {sanitize_error_message(str(exc))}",
                extra={
                    "endpoint": context.endpoint,
                    "method": context.method,
                    "ip_address": context.ip_address,
                    "error_type": type(exc).__name__,
                    "stack_trace": traceback.format_exc()
                }
            )
            
            # Réponse générique pour éviter l'exposition d'informations
            return JSONResponse(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                content={
                    "message": "Une erreur interne s'est produite",
                    "error_code": "INTERNAL_SERVER_ERROR",
                    "timestamp": datetime.utcnow().isoformat()
                }
            )


def setup_error_handlers(app):
    """Configure les gestionnaires d'erreurs pour l'application."""
    return GlobalErrorHandler(app)


# Middleware de logging des requêtes
class RequestLoggingMiddleware:
    """Middleware pour logger les requêtes et réponses."""
    
    def __init__(self, app):
        self.app = app
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Informations de la requête
        request_info = {
            "method": scope["method"],
            "path": scope["path"],
            "query_string": scope["query_string"].decode(),
            "client": scope.get("client"),
            "headers": dict(scope.get("headers", []))
        }
        
        start_time = datetime.utcnow()
        
        # Wrapper pour capturer la réponse
        response_info = {"status_code": None, "headers": {}}
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                response_info["status_code"] = message["status"]
                response_info["headers"] = dict(message.get("headers", []))
            await send(message)
        
        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            logger.error(
                f"Request processing error: {sanitize_error_message(str(exc))}",
                extra={
                    "request": request_info,
                    "processing_time": (datetime.utcnow() - start_time).total_seconds(),
                    "error_type": type(exc).__name__
                }
            )
            raise
        finally:
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            # Log de la requête
            log_level = logging.INFO
            if response_info["status_code"] and response_info["status_code"] >= 400:
                log_level = logging.WARNING
            if response_info["status_code"] and response_info["status_code"] >= 500:
                log_level = logging.ERROR
            
            logger.log(
                log_level,
                f"{request_info['method']} {request_info['path']} - {response_info['status_code']}",
                extra={
                    "request": request_info,
                    "response": response_info,
                    "processing_time": processing_time
                }
            )


# Utilitaires pour la gestion d'erreurs dans les services
def safe_execute(func, *args, **kwargs):
    """Exécute une fonction de manière sécurisée avec gestion d'erreurs."""
    try:
        return func(*args, **kwargs)
    except SecureException:
        raise  # Re-raise les exceptions sécurisées
    except SQLAlchemyError as e:
        raise handle_database_error(e)
    except Exception as e:
        logger.error(f"Unexpected error in {func.__name__}: {sanitize_error_message(str(e))}")
        raise SecureException(
            message=f"Error in {func.__name__}: {str(e)}",
            user_message="Une erreur inattendue s'est produite",
            error_code="UNEXPECTED_ERROR"
        )


async def safe_execute_async(func, *args, **kwargs):
    """Version asynchrone de safe_execute."""
    try:
        return await func(*args, **kwargs)
    except SecureException:
        raise  # Re-raise les exceptions sécurisées
    except SQLAlchemyError as e:
        raise handle_database_error(e)
    except Exception as e:
        logger.error(f"Unexpected error in {func.__name__}: {sanitize_error_message(str(e))}")
        raise SecureException(
            message=f"Error in {func.__name__}: {str(e)}",
            user_message="Une erreur inattendue s'est produite",
            error_code="UNEXPECTED_ERROR"
        )

