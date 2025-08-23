"""
Middleware de métriques sécurisé pour l'application VTC.
Remplace le middleware original avec des accès sécurisés aux attributs.
"""

import time
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from ..security.safe_attribute_access import safe_getattr, safe_hasattr
from ..cache.redis_manager import get_redis

logger = logging.getLogger(__name__)


class SecureMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware de métriques sécurisé."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.redis = get_redis()
    
    async def dispatch(self, request: Request, call_next):
        """Traite la requête et collecte les métriques de manière sécurisée."""
        start_time = time.time()
        
        # Collecte sécurisée des informations de requête
        request_info = self._collect_request_info_safely(request)
        
        # Traitement de la requête
        try:
            response = await call_next(request)
            
            # Collecte sécurisée des informations de réponse
            response_info = self._collect_response_info_safely(response)
            
            # Calcul du temps de traitement
            processing_time = time.time() - start_time
            
            # Enregistrement des métriques
            await self._record_metrics_safely(request_info, response_info, processing_time)
            
            return response
            
        except Exception as e:
            # Gestion sécurisée des erreurs
            processing_time = time.time() - start_time
            await self._record_error_metrics_safely(request_info, str(e), processing_time)
            raise
    
    def _collect_request_info_safely(self, request: Request) -> Dict[str, Any]:
        """Collecte les informations de requête de manière sécurisée."""
        info = {
            "method": request.method,
            "path": request.url.path,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        # Accès sécurisé au client
        client = safe_getattr(request, 'client', None, 'request')
        if client:
            info["client_ip"] = safe_getattr(client, 'host', 'unknown', 'client')
        else:
            info["client_ip"] = 'unknown'
        
        # Accès sécurisé au state
        if safe_hasattr(request, 'state', 'request'):
            state = safe_getattr(request, 'state', None, 'request')
            if state:
                # Accès sécurisé à l'utilisateur
                if safe_hasattr(state, 'user', 'state'):
                    user = safe_getattr(state, 'user', None, 'state')
                    if user:
                        info["user_id"] = safe_getattr(user, 'id', None, 'user')
                        info["user_role"] = safe_getattr(user, 'role', None, 'user')
                
                # Accès sécurisé au request_id
                info["request_id"] = safe_getattr(state, 'request_id', None, 'state')
        
        return info
    
    def _collect_response_info_safely(self, response: Response) -> Dict[str, Any]:
        """Collecte les informations de réponse de manière sécurisée."""
        info = {}
        
        # Accès sécurisé au status_code
        if response:
            info["status_code"] = safe_getattr(response, 'status_code', 500, 'response')
        else:
            info["status_code"] = 500
        
        return info
    
    async def _record_metrics_safely(self, request_info: Dict[str, Any], 
                                   response_info: Dict[str, Any], 
                                   processing_time: float):
        """Enregistre les métriques de manière sécurisée."""
        try:
            metrics_data = {
                **request_info,
                **response_info,
                "processing_time": processing_time,
                "success": True
            }
            
            # Enregistrement sécurisé dans Redis
            if self.redis:
                key = f"metrics:{request_info.get('timestamp', 'unknown')}"
                await self.redis.setex(key, 3600, str(metrics_data))  # Expire après 1h
            
            # Log sécurisé
            logger.info(
                f"Request processed: {request_info.get('method')} {request_info.get('path')} "
                f"- {response_info.get('status_code')} - {processing_time:.3f}s"
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement des métriques: {e}")
    
    async def _record_error_metrics_safely(self, request_info: Dict[str, Any], 
                                         error: str, processing_time: float):
        """Enregistre les métriques d'erreur de manière sécurisée."""
        try:
            metrics_data = {
                **request_info,
                "status_code": 500,
                "processing_time": processing_time,
                "success": False,
                "error": error[:100]  # Limiter la taille de l'erreur
            }
            
            # Enregistrement sécurisé dans Redis
            if self.redis:
                key = f"error_metrics:{request_info.get('timestamp', 'unknown')}"
                await self.redis.setex(key, 3600, str(metrics_data))
            
            # Log sécurisé
            logger.error(
                f"Request failed: {request_info.get('method')} {request_info.get('path')} "
                f"- {processing_time:.3f}s - Error: {error[:50]}"
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement des métriques d'erreur: {e}")


class SecureBusinessMetricsMiddleware(BaseHTTPMiddleware):
    """Middleware de métriques métier sécurisé."""
    
    def __init__(self, app: ASGIApp):
        super().__init__(app)
        self.redis = get_redis()
    
    async def dispatch(self, request: Request, call_next):
        """Traite la requête et collecte les métriques métier de manière sécurisée."""
        start_time = time.time()
        
        # Identifier le type d'opération métier
        business_operation = self._identify_business_operation_safely(request)
        
        try:
            response = await call_next(request)
            
            # Enregistrer les métriques métier
            if business_operation:
                await self._record_business_metrics_safely(
                    request, response, business_operation, time.time() - start_time
                )
            
            return response
            
        except Exception as e:
            # Enregistrer les erreurs métier
            if business_operation:
                await self._record_business_error_safely(
                    request, business_operation, str(e), time.time() - start_time
                )
            raise
    
    def _identify_business_operation_safely(self, request: Request) -> Optional[str]:
        """Identifie le type d'opération métier de manière sécurisée."""
        path = request.url.path
        method = request.method
        
        # Mapping sécurisé des opérations métier
        business_operations = {
            ("/api/v1/trips", "POST"): "trip_creation",
            ("/api/v1/trips", "GET"): "trip_listing",
            ("/api/v1/auth/login", "POST"): "user_login",
            ("/api/v1/auth/register", "POST"): "user_registration",
            ("/api/v1/payments", "POST"): "payment_processing"
        }
        
        # Vérification des patterns dynamiques
        if "/api/v1/trips/" in path and method == "PUT":
            return "trip_update"
        elif "/api/v1/trips/" in path and method == "DELETE":
            return "trip_cancellation"
        
        return business_operations.get((path, method))
    
    async def _record_business_metrics_safely(self, request: Request, response: Response,
                                            operation: str, processing_time: float):
        """Enregistre les métriques métier de manière sécurisée."""
        try:
            # Collecte sécurisée des informations utilisateur
            user_info = {}
            if safe_hasattr(request, 'state', 'request'):
                state = safe_getattr(request, 'state', None, 'request')
                if state and safe_hasattr(state, 'user', 'state'):
                    user = safe_getattr(state, 'user', None, 'state')
                    if user:
                        user_info["user_id"] = safe_getattr(user, 'id', None, 'user')
                        user_info["user_role"] = safe_getattr(user, 'role', None, 'user')
            
            # Collecte sécurisée des informations de réponse
            status_code = safe_getattr(response, 'status_code', 500, 'response') if response else 500
            
            metrics_data = {
                "operation": operation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "processing_time": processing_time,
                "status_code": status_code,
                "success": 200 <= status_code < 400,
                **user_info
            }
            
            # Enregistrement sécurisé
            if self.redis:
                key = f"business_metrics:{operation}:{metrics_data['timestamp']}"
                await self.redis.setex(key, 86400, str(metrics_data))  # Expire après 24h
            
            logger.info(f"Business operation: {operation} - {status_code} - {processing_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement des métriques métier: {e}")
    
    async def _record_business_error_safely(self, request: Request, operation: str,
                                          error: str, processing_time: float):
        """Enregistre les erreurs métier de manière sécurisée."""
        try:
            # Collecte sécurisée des informations utilisateur
            user_info = {}
            if safe_hasattr(request, 'state', 'request'):
                state = safe_getattr(request, 'state', None, 'request')
                if state and safe_hasattr(state, 'user', 'state'):
                    user = safe_getattr(state, 'user', None, 'state')
                    if user:
                        user_info["user_id"] = safe_getattr(user, 'id', None, 'user')
            
            error_data = {
                "operation": operation,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "processing_time": processing_time,
                "success": False,
                "error": error[:100],  # Limiter la taille
                **user_info
            }
            
            # Enregistrement sécurisé
            if self.redis:
                key = f"business_errors:{operation}:{error_data['timestamp']}"
                await self.redis.setex(key, 86400, str(error_data))
            
            logger.error(f"Business operation failed: {operation} - {error[:50]} - {processing_time:.3f}s")
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement des erreurs métier: {e}")


# Alias pour compatibilité
MetricsMiddleware = SecureMetricsMiddleware
BusinessMetricsMiddleware = SecureBusinessMetricsMiddleware

