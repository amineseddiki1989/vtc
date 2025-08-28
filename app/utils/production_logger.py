"""
Production Logger - Fix AttributeError pour logging.handlers
Module de logging sécurisé pour l'environnement de production
"""

import logging
import logging.handlers  # Import explicite requis pour RotatingFileHandler
import sys
import os
from datetime import datetime
from pathlib import Path
import json

class ProductionLogger:
    """
    Logger de production avec rotation des fichiers et formatage sécurisé
    Fix: Import explicite de logging.handlers pour éviter l'AttributeError
    """

    def __init__(self, name: str = None, log_level: str = "INFO"):
        self.name = name or __name__
        self.log_level = getattr(logging, log_level.upper(), logging.INFO)
        self.logger = self._setup_logger()

    def _setup_logger(self):
        """Configuration du logger avec handlers multiples"""
        logger = logging.getLogger(self.name)

        # Éviter la duplication des handlers
        if logger.handlers:
            return logger

        logger.setLevel(self.log_level)

        # Format de base
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Handler console
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        # Handler fichier rotatif (si possible)
        try:
            log_dir = Path("/var/log/vtc")
            log_dir.mkdir(parents=True, exist_ok=True)

            # Fix AttributeError: Import explicite résolu le problème
            file_handler = logging.handlers.RotatingFileHandler(
                log_dir / "vtc_app.log",
                maxBytes=10*1024*1024,  # 10MB
                backupCount=5,
                encoding='utf-8'
            )
            file_handler.setFormatter(formatter)
            logger.addHandler(file_handler)

        except (PermissionError, OSError) as e:
            # Fallback vers /tmp si /var/log n'est pas accessible
            try:
                fallback_log = Path("/tmp/vtc_app.log")
                file_handler = logging.handlers.RotatingFileHandler(
                    fallback_log,
                    maxBytes=5*1024*1024,  # 5MB
                    backupCount=2,
                    encoding='utf-8'
                )
                file_handler.setFormatter(formatter)
                logger.addHandler(file_handler)
                logger.warning(f"Utilisation du répertoire de log fallback: {fallback_log}")
            except Exception as fallback_error:
                logger.warning(f"Impossible de configurer le logging fichier: {fallback_error}")

        return logger

    def _sanitize_message(self, message: str) -> str:
        """Sanitize les messages pour éviter l'injection de logs"""
        if not isinstance(message, str):
            message = str(message)

        # Remplacer les caractères de contrôle
        sanitized = message.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')

        # Limiter la longueur
        if len(sanitized) > 1000:
            sanitized = sanitized[:997] + "..."

        return sanitized

    def _format_context(self, **kwargs) -> str:
        """Formate le contexte supplémentaire"""
        if not kwargs:
            return ""

        try:
            context = json.dumps(kwargs, default=str, ensure_ascii=False)
            return f" | Context: {context}"
        except Exception:
            return f" | Context: {str(kwargs)}"

    def debug(self, message: str, **kwargs):
        """Log niveau DEBUG"""
        clean_msg = self._sanitize_message(message)
        context = self._format_context(**kwargs)
        self.logger.debug(f"{clean_msg}{context}")

    def info(self, message: str, **kwargs):
        """Log niveau INFO"""
        clean_msg = self._sanitize_message(message)
        context = self._format_context(**kwargs)
        self.logger.info(f"{clean_msg}{context}")

    def warning(self, message: str, **kwargs):
        """Log niveau WARNING"""
        clean_msg = self._sanitize_message(message)
        context = self._format_context(**kwargs)
        self.logger.warning(f"{clean_msg}{context}")

    def error(self, message: str, **kwargs):
        """Log niveau ERROR"""
        clean_msg = self._sanitize_message(message)
        context = self._format_context(**kwargs)
        self.logger.error(f"{clean_msg}{context}")

    def critical(self, message: str, **kwargs):
        """Log niveau CRITICAL"""
        clean_msg = self._sanitize_message(message)
        context = self._format_context(**kwargs)
        self.logger.critical(f"{clean_msg}{context}")

    def log_security_event(self, event_type: str, details: dict = None):
        """Log spécialisé pour les événements de sécurité"""
        security_msg = f"SECURITY_EVENT: {event_type}"
        if details:
            security_msg += f" - Details: {json.dumps(details, default=str)}"

        self.warning(security_msg)

    def log_performance(self, operation: str, duration: float, **context):
        """Log des métriques de performance"""
        perf_msg = f"PERFORMANCE: {operation} completed in {duration:.3f}s"
        self.info(perf_msg, **context)

# Instance globale pour faciliter l'utilisation
default_logger = ProductionLogger("vtc_app")

# Fonctions de convenance
def get_logger(name: str = None) -> ProductionLogger:
    """Obtient une instance de logger"""
    return ProductionLogger(name) if name else default_logger

def log_info(message: str, **kwargs):
    """Log info avec le logger par défaut"""
    default_logger.info(message, **kwargs)

def log_error(message: str, **kwargs):
    """Log erreur avec le logger par défaut"""
    default_logger.error(message, **kwargs)

def log_warning(message: str, **kwargs):
    """Log warning avec le logger par défaut"""
    default_logger.warning(message, **kwargs)
