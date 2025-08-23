"""
Middleware de limitation du taux de requêtes.
"""

import time
import logging
from typing import Dict, Any
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware de limitation du taux de requêtes en mémoire."""
    
    def __init__(self, app):
        super().__init__(app)
        self.requests_limit = settings.rate_limit_requests
        self.window_seconds = settings.rate_limit_window_seconds
        self.client_requests: Dict[str, list] = {}
    
    def get_client_identifier(self, request: Request) -> str:
        """Génère un identifiant unique pour le client."""
        return request.client.host if request.client else "unknown"
    
    async def dispatch(self, request: Request, call_next):
        """Traite la requête avec limitation de taux."""
        client_id = self.get_client_identifier(request)
        current_time = time.time()
        
        # Nettoyer les anciennes requêtes
        if client_id in self.client_requests:
            self.client_requests[client_id] = [
                req_time for req_time in self.client_requests[client_id]
                if current_time - req_time < self.window_seconds
            ]
        else:
            self.client_requests[client_id] = []
        
        # Vérifier la limite
        if len(self.client_requests[client_id]) >= self.requests_limit:
            logger.warning(f"Rate limit dépassé pour {client_id}")
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Trop de requêtes"
            )
        
        # Ajouter la requête actuelle
        self.client_requests[client_id].append(current_time)
        
        response = await call_next(request)
        return response

