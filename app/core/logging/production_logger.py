"""
Système de logging production avec structuration JSON et monitoring.
Optimisé pour l'observabilité et le debugging en production.
Version sécurisée avec gestion des chemins.
"""

import os
import sys
import json
import time
import logging
import logging.handlers
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Union
from contextvars import ContextVar
from functools import wraps

import structlog
from pythonjsonlogger import jsonlogger

from ..config.production_settings import get_settings
from ..security.secure_file_handler import SecureFileHandler

# Context variables pour le tracing
request_id_var: ContextVar[Optional[str]] = ContextVar('request_id', default=None)
user_id_var: ContextVar[Optional[str]] = ContextVar('user_id', default=None)
correlation_id_var: ContextVar[Optional[str]] = ContextVar('correlation_id', default=None)

class ProductionFormatter(jsonlogger.JsonFormatter):
    """Formateur JSON personnalisé pour la production."""
    
    def add_fields(self, log_record: Dict[str, Any], record: logging.LogRecord, message_dict: Dict[str, Any]) -> None:
        """Ajoute des champs personnalisés au log."""
        super().add_fields(log_record, record, message_dict)
        
        # Timestamp ISO 8601 avec timezone
        log_record['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        # Informations de base
        log_record['level'] = record.levelname
        log_record['logger'] = record.name
        log_record['module'] = record.module
        log_record['function'] = record.funcName
        log_record['line'] = record.lineno
        
        # Context variables
        log_record['request_id'] = request_id_var.get()
        log_record['user_id'] = user_id_var.get()
        log_record['correlation_id'] = correlation_id_var.get()
        
        # Informations système
        log_record['process_id'] = os.getpid()
        log_record['thread_id'] = record.thread
        
        # Environnement
        settings = get_settings()
        log_record['environment'] = settings.environment
        log_record['service'] = settings.app_name
        log_record['version'] = settings.app_version

class SecurityLogFilter(logging.Filter):
    """Filtre pour les logs de sécurité."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Filtre et enrichit les logs de sécurité."""
        # Marquer les logs de sécurité
        if hasattr(record, 'security_event'):
            record.security = True
            record.alert_level = getattr(record, 'alert_level', 'medium')
        
        # Masquer les données sensibles
        if hasattr(record, 'msg'):
            sensitive_patterns = [
                'password', 'token', 'secret', 'key', 'authorization',
                'credit_card', 'ssn', 'social_security'
            ]
            
            msg = str(record.msg).lower()
            for pattern in sensitive_patterns:
                if pattern in msg:
                    record.contains_sensitive_data = True
                    break
        
        return True

class PerformanceLogFilter(logging.Filter):
    """Filtre pour les logs de performance."""
    
    def filter(self, record: logging.LogRecord) -> bool:
        """Enrichit les logs avec des métriques de performance."""
        if hasattr(record, 'duration'):
            # Catégoriser la performance
            duration = record.duration
            if duration > 5.0:
                record.performance_category = 'slow'
                record.alert_level = 'high'
            elif duration > 1.0:
                record.performance_category = 'medium'
                record.alert_level = 'medium'
            else:
                record.performance_category = 'fast'
                record.alert_level = 'low'
        
        return True

class ProductionLoggerManager:
    """Gestionnaire de logging pour la production."""
    
    def __init__(self):
        self.settings = get_settings()
        self._configured = False
        
    def configure_logging(self) -> None:
        """Configure le système de logging pour la production."""
        if self._configured:
            return
            
        # Configuration de base
        logging.basicConfig(level=logging.NOTSET, handlers=[])
        
        # Logger racine
        root_logger = logging.getLogger()
        root_logger.setLevel(getattr(logging, self.settings.monitoring.log_level.upper()))
        
        # Supprimer les handlers existants
        for handler in root_logger.handlers[:]:
            root_logger.removeHandler(handler)
        
        # Créer les handlers
        handlers = []
        
        # Handler console (stdout)
        console_handler = self._create_console_handler()
        handlers.append(console_handler)
        
        # Handler fichier si configuré
        if self.settings.monitoring.log_file:
            file_handler = self._create_file_handler()
            handlers.append(file_handler)
        
        # Handler erreurs (stderr)
        error_handler = self._create_error_handler()
        handlers.append(error_handler)
        
        # Handler sécurité
        security_handler = self._create_security_handler()
        handlers.append(security_handler)
        
        # Ajouter tous les handlers
        for handler in handlers:
            root_logger.addHandler(handler)
        
        # Configuration des loggers spécifiques
        self._configure_specific_loggers()
        
        # Configuration structlog
        self._configure_structlog()
        
        self._configured = True
        
        # Log de démarrage
        logger = logging.getLogger(__name__)
        logger.info("Système de logging production configuré", extra={
            "log_level": self.settings.monitoring.log_level,
            "handlers_count": len(handlers),
            "environment": self.settings.environment
        })
    
    def _create_console_handler(self) -> logging.StreamHandler:
        """Crée le handler pour la console."""
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        
        if self.settings.monitoring.log_format == "json":
            formatter = ProductionFormatter(
                fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
            )
        else:
            formatter = logging.Formatter(
                fmt='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
        
        handler.setFormatter(formatter)
        handler.addFilter(PerformanceLogFilter())
        
        return handler
    
    def _create_file_handler(self) -> logging.handlers.RotatingFileHandler:
        """Crée le handler pour les fichiers de manière sécurisée."""
        try:
            # Utilisation du gestionnaire de fichiers sécurisé
            log_filename = os.path.basename(self.settings.monitoring.log_file)
            secure_path = SecureFileHandler.secure_path_join('logs', log_filename)
            
            # Créer le répertoire parent de manière sécurisée
            secure_path.parent.mkdir(parents=True, exist_ok=True)
            
            handler = logging.handlers.RotatingFileHandler(
                filename=str(secure_path),
                maxBytes=50 * 1024 * 1024,  # 50MB
                backupCount=10,
                encoding='utf-8'
            )
            handler.setLevel(logging.DEBUG)
        except Exception as e:
            # Fallback vers un handler console en cas d'erreur
            logging.error(f"Impossible de créer le handler de fichier: {e}")
            return self._create_console_handler()
        
        formatter = ProductionFormatter(
            fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
        )
        handler.setFormatter(formatter)
        handler.addFilter(PerformanceLogFilter())
        
        return handler
    
    def _create_error_handler(self) -> logging.StreamHandler:
        """Crée le handler pour les erreurs."""
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.ERROR)
        
        formatter = ProductionFormatter(
            fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
        )
        handler.setFormatter(formatter)
        
        return handler
    
    def _create_security_handler(self) -> logging.handlers.RotatingFileHandler:
        """Crée le handler pour les logs de sécurité de manière sécurisée."""
        if not self.settings.monitoring.log_file:
            return None
        
        try:
            # Utilisation du gestionnaire de fichiers sécurisé
            secure_path = SecureFileHandler.secure_path_join('logs', 'security.log')
            
            # Créer le répertoire parent de manière sécurisée
            secure_path.parent.mkdir(parents=True, exist_ok=True)
            
            handler = logging.handlers.RotatingFileHandler(
                filename=str(secure_path),
                maxBytes=10 * 1024 * 1024,  # 10MB
                backupCount=20,
                encoding='utf-8'
            )
            handler.setLevel(logging.WARNING)
            
            formatter = ProductionFormatter(
                fmt='%(timestamp)s %(level)s %(logger)s %(message)s'
            )
            handler.setFormatter(formatter)
        except Exception as e:
            # Fallback vers None en cas d'erreur
            logging.error(f"Impossible de créer le handler de sécurité: {e}")
            return None
        handler.addFilter(SecurityLogFilter())
        
        # Filtrer seulement les logs de sécurité
        class SecurityOnlyFilter(logging.Filter):
            def filter(self, record):
                return hasattr(record, 'security') or record.name == 'security'
        
        handler.addFilter(SecurityOnlyFilter())
        
        return handler
    
    def _configure_specific_loggers(self) -> None:
        """Configure des loggers spécifiques."""
        # Logger pour les requêtes HTTP
        access_logger = logging.getLogger("uvicorn.access")
        access_logger.setLevel(logging.INFO)
        
        # Logger pour les erreurs d'application
        app_logger = logging.getLogger("app")
        app_logger.setLevel(logging.DEBUG if not self.settings.is_production else logging.INFO)
        
        # Logger pour la sécurité
        security_logger = logging.getLogger("security")
        security_logger.setLevel(logging.WARNING)
        
        # Logger pour les performances
        perf_logger = logging.getLogger("performance")
        perf_logger.setLevel(logging.INFO)
        
        # Réduire le niveau des loggers tiers
        logging.getLogger("urllib3").setLevel(logging.WARNING)
        logging.getLogger("requests").setLevel(logging.WARNING)
        logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    def _configure_structlog(self) -> None:
        """Configure structlog pour les logs structurés."""
        structlog.configure(
            processors=[
                structlog.contextvars.merge_contextvars,
                structlog.processors.add_log_level,
                structlog.processors.StackInfoRenderer(),
                structlog.dev.set_exc_info,
                structlog.processors.JSONRenderer()
            ],
            wrapper_class=structlog.make_filtering_bound_logger(
                getattr(logging, self.settings.monitoring.log_level.upper())
            ),
            logger_factory=structlog.PrintLoggerFactory(),
            cache_logger_on_first_use=True,
        )

class RequestLoggingMiddleware:
    """Middleware pour logger les requêtes HTTP."""
    
    def __init__(self, app):
        self.app = app
        self.logger = logging.getLogger("access")
    
    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        
        # Générer un ID de requête unique
        import uuid
        request_id = str(uuid.uuid4())
        request_id_var.set(request_id)
        
        start_time = time.time()
        
        # Informations de la requête
        method = scope["method"]
        path = scope["path"]
        query_string = scope.get("query_string", b"").decode()
        client_ip = scope.get("client", ["unknown", None])[0]
        
        # Headers
        headers = dict(scope.get("headers", []))
        user_agent = headers.get(b"user-agent", b"").decode()
        
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                # Log de la réponse
                status_code = message["status"]
                duration = time.time() - start_time
                
                # Déterminer le niveau de log
                if status_code >= 500:
                    log_level = logging.ERROR
                elif status_code >= 400:
                    log_level = logging.WARNING
                else:
                    log_level = logging.INFO
                
                self.logger.log(log_level, "HTTP Request", extra={
                    "request_id": request_id,
                    "method": method,
                    "path": path,
                    "query_string": query_string,
                    "status_code": status_code,
                    "duration": duration,
                    "client_ip": client_ip,
                    "user_agent": user_agent,
                    "response_size": message.get("headers", {}).get("content-length", 0)
                })
            
            await send(message)
        
        await self.app(scope, receive, send_wrapper)

def log_performance(operation_name: str):
    """Décorateur pour logger les performances d'une opération."""
    def decorator(func):
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = logging.getLogger("performance")
            start_time = time.time()
            
            try:
                result = await func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(f"Operation completed: {operation_name}", extra={
                    "operation": operation_name,
                    "duration": duration,
                    "success": True
                })
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(f"Operation failed: {operation_name}", extra={
                    "operation": operation_name,
                    "duration": duration,
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                
                raise
        
        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = logging.getLogger("performance")
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time
                
                logger.info(f"Operation completed: {operation_name}", extra={
                    "operation": operation_name,
                    "duration": duration,
                    "success": True
                })
                
                return result
                
            except Exception as e:
                duration = time.time() - start_time
                
                logger.error(f"Operation failed: {operation_name}", extra={
                    "operation": operation_name,
                    "duration": duration,
                    "success": False,
                    "error": str(e),
                    "error_type": type(e).__name__
                })
                
                raise
        
        # Retourner le bon wrapper selon le type de fonction
        import asyncio
        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper
    
    return decorator

def log_security_event(
    event_type: str,
    details: Dict[str, Any],
    risk_score: int = 50,
    user_id: Optional[str] = None
):
    """Log un événement de sécurité."""
    logger = logging.getLogger("security")
    
    logger.warning(f"Security event: {event_type}", extra={
        "security_event": True,
        "event_type": event_type,
        "risk_score": risk_score,
        "user_id": user_id or user_id_var.get(),
        "details": details,
        "alert_level": "high" if risk_score > 70 else "medium" if risk_score > 40 else "low"
    })

# Instance globale
logger_manager = ProductionLoggerManager()

def setup_logging():
    """Configure le logging pour l'application."""
    logger_manager.configure_logging()

def get_logger(name: str) -> logging.Logger:
    """Obtient un logger configuré."""
    return logging.getLogger(name)

