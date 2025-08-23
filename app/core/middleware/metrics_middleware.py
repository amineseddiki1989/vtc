"""
Middleware de monitoring des métriques pour FastAPI.
"""

import time
import uuid
from typing import Callable
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from ...models.metrics import MetricType, MetricCategory
from ...services.metrics_service import get_metrics_collector

logger = logging.getLogger(__name__)


class MetricsMiddleware(BaseHTTPMiddleware):
    """Middleware pour collecter automatiquement les métriques des requêtes HTTP."""
    
    def __init__(self, app: ASGIApp, exclude_paths: list = None):
        super().__init__(app)
        self.collector = get_metrics_collector()
        self.exclude_paths = exclude_paths or ["/docs", "/redoc", "/openapi.json", "/favicon.ico"]
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Traite chaque requête et collecte les métriques."""
        
        # Ignorer certains endpoints
        if any(request.url.path.startswith(path) for path in self.exclude_paths):
            return await call_next(request)
        
        # Générer un ID unique pour la requête
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id
        
        # Informations de base sur la requête
        method = request.method
        path = request.url.path
        client_ip = getattr(request.client, 'host', 'unknown') if request.client else 'unknown'
        user_agent = request.headers.get('user-agent', 'unknown')
        
        # Extraire l'ID utilisateur si disponible
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = getattr(request.state.user, 'id', None)
        
        # Labels pour les métriques
        labels = {
            "method": method,
            "endpoint": path,
            "client_ip": client_ip,
            "user_agent": user_agent[:100]  # Limiter la taille
        }
        
        # Démarrer le timer
        start_time = time.time()
        
        # Métriques de début de requête
        self.collector.record_metric(
            name="http_requests_total",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.SYSTEM,
            labels=labels,
            user_id=user_id,
            request_id=request_id,
            description=f"Requête {method} {path}"
        )
        
        # Métriques de requêtes actives
        self.collector.record_metric(
            name="http_requests_active",
            value=1,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.SYSTEM,
            labels=labels,
            user_id=user_id,
            request_id=request_id
        )
        
        response = None
        error_occurred = False
        
        try:
            # Traiter la requête
            response = await call_next(request)
            
        except Exception as e:
            error_occurred = True
            logger.error(f"Erreur dans la requête {request_id}: {str(e)}")
            
            # Métrique d'erreur
            error_labels = labels.copy()
            error_labels.update({
                "error_type": type(e).__name__,
                "error_message": str(e)[:200]
            })
            
            self.collector.record_metric(
                name="http_requests_errors",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.SYSTEM,
                labels=error_labels,
                user_id=user_id,
                request_id=request_id,
                description=f"Erreur {type(e).__name__} sur {method} {path}"
            )
            
            # Retourner une réponse d'erreur
            response = JSONResponse(
                status_code=500,
                content={
                    "error": {
                        "code": "INTERNAL_SERVER_ERROR",
                        "message": "Une erreur interne s'est produite",
                        "request_id": request_id
                    }
                }
            )
        
        finally:
            # Calculer le temps de réponse
            duration = time.time() - start_time
            
            # Ajouter le status code aux labels
            status_code = getattr(response, 'status_code', 500) if response else 500
            final_labels = labels.copy()
            final_labels.update({
                "status_code": str(status_code),
                "status_class": f"{status_code // 100}xx"
            })
            
            # Métriques de fin de requête
            self.collector.record_metric(
                name="http_request_duration_seconds",
                value=duration,
                metric_type=MetricType.TIMER,
                category=MetricCategory.PERFORMANCE,
                labels=final_labels,
                user_id=user_id,
                request_id=request_id,
                description=f"Durée de {method} {path}"
            )
            
            # Métrique de réponse par status code
            self.collector.record_metric(
                name=f"http_responses_{status_code}",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.SYSTEM,
                labels=final_labels,
                user_id=user_id,
                request_id=request_id
            )
            
            # Décrémenter les requêtes actives
            self.collector.record_metric(
                name="http_requests_active",
                value=-1,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.SYSTEM,
                labels=labels,
                user_id=user_id,
                request_id=request_id
            )
            
            # Métriques spécifiques selon le status code
            if status_code >= 400:
                self.collector.record_metric(
                    name="http_requests_failed",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.SYSTEM,
                    labels=final_labels,
                    user_id=user_id,
                    request_id=request_id
                )
            else:
                self.collector.record_metric(
                    name="http_requests_successful",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.SYSTEM,
                    labels=final_labels,
                    user_id=user_id,
                    request_id=request_id
                )
            
            # Métriques de performance selon la durée
            if duration > 5.0:  # Requêtes très lentes
                self.collector.record_metric(
                    name="http_requests_very_slow",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.PERFORMANCE,
                    labels=final_labels,
                    user_id=user_id,
                    request_id=request_id
                )
            elif duration > 1.0:  # Requêtes lentes
                self.collector.record_metric(
                    name="http_requests_slow",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.PERFORMANCE,
                    labels=final_labels,
                    user_id=user_id,
                    request_id=request_id
                )
        
        return response


class BusinessMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware pour collecter les métriques métier spécifiques."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.collector = get_metrics_collector()
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """Collecte les métriques métier selon l'endpoint."""
        
        response = await call_next(request)
        
        # Extraire les informations utilisateur
        user_id = None
        user_role = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = getattr(request.state.user, 'id', None)
            user_role = getattr(request.state.user, 'role', None)
        
        request_id = getattr(request.state, 'request_id', None)
        path = request.url.path
        method = request.method
        status_code = response.status_code
        
        # Métriques spécifiques par endpoint
        if path.startswith('/api/v1/auth/'):
            await self._collect_auth_metrics(path, method, status_code, user_id, user_role, request_id)
        elif path.startswith('/api/v1/trips/'):
            await self._collect_trip_metrics(path, method, status_code, user_id, user_role, request_id)
        
        return response
    
    async def _collect_auth_metrics(self, path: str, method: str, status_code: int, user_id: str, user_role: str, request_id: str):
        """Collecte les métriques d'authentification."""
        labels = {
            "endpoint": path,
            "method": method,
            "status_code": str(status_code),
            "user_role": user_role or "unknown"
        }
        
        if path.endswith('/login'):
            if status_code == 200:
                self.collector.record_metric(
                    name="auth_login_success",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels=labels,
                    user_id=user_id,
                    request_id=request_id,
                    description="Connexion réussie"
                )
            else:
                self.collector.record_metric(
                    name="auth_login_failed",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels=labels,
                    user_id=user_id,
                    request_id=request_id,
                    description="Échec de connexion"
                )
        
        elif path.endswith('/register'):
            if status_code == 201:
                self.collector.record_metric(
                    name="auth_register_success",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels=labels,
                    user_id=user_id,
                    request_id=request_id,
                    description="Inscription réussie"
                )
            else:
                self.collector.record_metric(
                    name="auth_register_failed",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels=labels,
                    user_id=user_id,
                    request_id=request_id,
                    description="Échec d'inscription"
                )
    
    async def _collect_trip_metrics(self, path: str, method: str, status_code: int, user_id: str, user_role: str, request_id: str):
        """Collecte les métriques de courses."""
        labels = {
            "endpoint": path,
            "method": method,
            "status_code": str(status_code),
            "user_role": user_role or "unknown"
        }
        
        if method == "POST":
            if path.endswith('/trips') or path.endswith('/trips/'):
                # Création de course
                if status_code == 201:
                    self.collector.record_metric(
                        name="trips_created",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.BUSINESS,
                        labels=labels,
                        user_id=user_id,
                        request_id=request_id,
                        description="Course créée"
                    )
            elif '/accept' in path:
                # Acceptation de course
                if status_code == 200:
                    self.collector.record_metric(
                        name="trips_accepted",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.BUSINESS,
                        labels=labels,
                        user_id=user_id,
                        request_id=request_id,
                        description="Course acceptée"
                    )
            elif '/start' in path:
                # Démarrage de course
                if status_code == 200:
                    self.collector.record_metric(
                        name="trips_started",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.BUSINESS,
                        labels=labels,
                        user_id=user_id,
                        request_id=request_id,
                        description="Course démarrée"
                    )
            elif '/complete' in path:
                # Fin de course
                if status_code == 200:
                    self.collector.record_metric(
                        name="trips_completed",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.BUSINESS,
                        labels=labels,
                        user_id=user_id,
                        request_id=request_id,
                        description="Course terminée"
                    )
            elif '/cancel' in path:
                # Annulation de course
                if status_code == 200:
                    self.collector.record_metric(
                        name="trips_cancelled",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.BUSINESS,
                        labels=labels,
                        user_id=user_id,
                        request_id=request_id,
                        description="Course annulée"
                    )
        
        elif method == "GET" and path.endswith('/estimate'):
            # Estimation de course
            if status_code == 200:
                self.collector.record_metric(
                    name="trips_estimated",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels=labels,
                    user_id=user_id,
                    request_id=request_id,
                    description="Course estimée"
                )

