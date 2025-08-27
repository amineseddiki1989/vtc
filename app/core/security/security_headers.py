"""
Middleware pour ajouter les headers de sécurité.
"""

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from typing import Callable


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Middleware pour ajouter les headers de sécurité essentiels."""
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        response = await call_next(request)
        
        # Headers de sécurité
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        
        # Content Security Policy
        csp = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'none';"
        )
        response.headers["Content-Security-Policy"] = csp
        
        # HSTS pour HTTPS (en production)
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        
        return response




class RateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware pour implémenter le rate limiting."""

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Implémentation simplifiée du rate limiting
        # Pour une implémentation complète, utiliser des bibliothèques comme `fastapi-limiter`
        # ou un service externe comme Redis pour stocker les compteurs de requêtes.
        
        # Exemple: Limiter à 10 requêtes par seconde par IP
        client_ip = request.client.host
        # Ici, vous implémenteriez la logique de comptage et de vérification
        # Pour l'instant, on laisse passer toutes les requêtes pour ne pas bloquer les tests
        
        response = await call_next(request)
        return response


