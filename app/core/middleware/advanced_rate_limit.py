"""
Middleware de limitation du taux de requêtes avancé avec algorithmes multiples.
"""

import time
import asyncio
import logging
from typing import Dict, Any, Optional, List
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class RateLimitAlgorithm(Enum):
    """Algorithmes de rate limiting disponibles."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Configuration pour le rate limiting."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    whitelist_ips: List[str] = None
    endpoint_specific_limits: Dict[str, int] = None


class TokenBucket:
    """Implémentation de l'algorithme Token Bucket."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.tokens = capacity
        self.refill_rate = refill_rate
        self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> bool:
        """Consomme des tokens du bucket."""
        now = time.time()
        # Ajouter des tokens basés sur le temps écoulé
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False


class SlidingWindowCounter:
    """Implémentation de l'algorithme Sliding Window."""
    
    def __init__(self, window_size: int, max_requests: int):
        self.window_size = window_size
        self.max_requests = max_requests
        self.requests = deque()
    
    def is_allowed(self) -> bool:
        """Vérifie si la requête est autorisée."""
        now = time.time()
        # Supprimer les requêtes anciennes
        while self.requests and now - self.requests[0] > self.window_size:
            self.requests.popleft()
        
        if len(self.requests) < self.max_requests:
            self.requests.append(now)
            return True
        return False


class LeakyBucket:
    """Implémentation de l'algorithme Leaky Bucket."""
    
    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.current_volume = 0
        self.leak_rate = leak_rate
        self.last_leak = time.time()
    
    def add_request(self) -> bool:
        """Ajoute une requête au bucket."""
        now = time.time()
        # Faire fuir le bucket
        elapsed = now - self.last_leak
        leaked = elapsed * self.leak_rate
        self.current_volume = max(0, self.current_volume - leaked)
        self.last_leak = now
        
        if self.current_volume < self.capacity:
            self.current_volume += 1
            return True
        return False


class AdvancedRateLimitMiddleware(BaseHTTPMiddleware):
    """Middleware de rate limiting avancé avec algorithmes multiples."""
    
    def __init__(self, app, config: RateLimitConfig = None):
        super().__init__(app)
        self.config = config or RateLimitConfig()
        self.client_buckets: Dict[str, TokenBucket] = {}
        self.client_windows: Dict[str, SlidingWindowCounter] = {}
        self.client_leaky_buckets: Dict[str, LeakyBucket] = {}
        self.client_fixed_windows: Dict[str, Dict[str, int]] = defaultdict(dict)
        self.blocked_ips: Dict[str, float] = {}
        self.suspicious_activity: Dict[str, List[float]] = defaultdict(list)
        
        # Configuration des limites par endpoint
        self.endpoint_limits = self.config.endpoint_specific_limits or {
            "/api/v1/auth/login": 5,  # 5 tentatives par minute
            "/api/v1/auth/register": 3,  # 3 inscriptions par minute
            "/api/v1/trips/request": 10,  # 10 demandes par minute
            "/api/v1/emergency/sos": 2,  # 2 SOS par minute (sécurité)
        }
    
    def get_client_identifier(self, request: Request) -> str:
        """Génère un identifiant unique pour le client."""
        # Priorité : X-Forwarded-For > X-Real-IP > client.host
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip
        
        return request.client.host if request.client else "unknown"
    
    def is_whitelisted(self, client_id: str) -> bool:
        """Vérifie si l'IP est dans la whitelist."""
        if not self.config.whitelist_ips:
            return False
        return client_id in self.config.whitelist_ips
    
    def is_blocked(self, client_id: str) -> bool:
        """Vérifie si l'IP est temporairement bloquée."""
        if client_id in self.blocked_ips:
            if time.time() - self.blocked_ips[client_id] > 3600:  # Débloquer après 1h
                del self.blocked_ips[client_id]
                return False
            return True
        return False
    
    def detect_suspicious_activity(self, client_id: str) -> bool:
        """Détecte une activité suspecte."""
        now = time.time()
        self.suspicious_activity[client_id].append(now)
        
        # Garder seulement les 5 dernières minutes
        self.suspicious_activity[client_id] = [
            t for t in self.suspicious_activity[client_id] 
            if now - t < 300
        ]
        
        # Si plus de 100 requêtes en 5 minutes, c'est suspect
        if len(self.suspicious_activity[client_id]) > 100:
            self.blocked_ips[client_id] = now
            logger.warning(f"Activité suspecte détectée pour {client_id} - IP bloquée")
            return True
        
        return False
    
    def get_endpoint_limit(self, path: str) -> int:
        """Récupère la limite spécifique pour un endpoint."""
        for endpoint, limit in self.endpoint_limits.items():
            if path.startswith(endpoint):
                return limit
        return self.config.requests_per_minute
    
    def check_token_bucket(self, client_id: str, endpoint_limit: int) -> bool:
        """Vérifie avec l'algorithme Token Bucket."""
        if client_id not in self.client_buckets:
            self.client_buckets[client_id] = TokenBucket(
                capacity=self.config.burst_limit,
                refill_rate=endpoint_limit / 60.0  # tokens par seconde
            )
        
        return self.client_buckets[client_id].consume()
    
    def check_sliding_window(self, client_id: str, endpoint_limit: int) -> bool:
        """Vérifie avec l'algorithme Sliding Window."""
        if client_id not in self.client_windows:
            self.client_windows[client_id] = SlidingWindowCounter(
                window_size=60,  # 1 minute
                max_requests=endpoint_limit
            )
        
        return self.client_windows[client_id].is_allowed()
    
    def check_leaky_bucket(self, client_id: str, endpoint_limit: int) -> bool:
        """Vérifie avec l'algorithme Leaky Bucket."""
        if client_id not in self.client_leaky_buckets:
            self.client_leaky_buckets[client_id] = LeakyBucket(
                capacity=self.config.burst_limit,
                leak_rate=endpoint_limit / 60.0  # requêtes par seconde
            )
        
        return self.client_leaky_buckets[client_id].add_request()
    
    def check_fixed_window(self, client_id: str, endpoint_limit: int) -> bool:
        """Vérifie avec l'algorithme Fixed Window."""
        now = time.time()
        window = int(now // 60)  # Fenêtre d'1 minute
        
        if window not in self.client_fixed_windows[client_id]:
            self.client_fixed_windows[client_id][window] = 0
        
        # Nettoyer les anciennes fenêtres
        old_windows = [w for w in self.client_fixed_windows[client_id] if w < window - 1]
        for old_window in old_windows:
            del self.client_fixed_windows[client_id][old_window]
        
        if self.client_fixed_windows[client_id][window] < endpoint_limit:
            self.client_fixed_windows[client_id][window] += 1
            return True
        
        return False
    
    def create_rate_limit_response(self, client_id: str, endpoint: str, retry_after: int = 60) -> JSONResponse:
        """Crée une réponse de rate limit avec headers informatifs."""
        headers = {
            "X-RateLimit-Limit": str(self.get_endpoint_limit(endpoint)),
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Reset": str(int(time.time()) + retry_after),
            "Retry-After": str(retry_after)
        }
        
        return JSONResponse(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            content={
                "error": "Rate limit exceeded",
                "message": f"Trop de requêtes pour l'endpoint {endpoint}",
                "retry_after": retry_after,
                "client_id": client_id[:8] + "..." if len(client_id) > 8 else client_id
            },
            headers=headers
        )
    
    async def dispatch(self, request: Request, call_next):
        """Traite la requête avec rate limiting avancé."""
        client_id = self.get_client_identifier(request)
        endpoint = request.url.path
        
        # Vérifier la whitelist
        if self.is_whitelisted(client_id):
            return await call_next(request)
        
        # Vérifier si l'IP est bloquée
        if self.is_blocked(client_id):
            logger.warning(f"Requête bloquée pour IP suspecte: {client_id}")
            return self.create_rate_limit_response(client_id, endpoint, 3600)
        
        # Détecter l'activité suspecte
        if self.detect_suspicious_activity(client_id):
            return self.create_rate_limit_response(client_id, endpoint, 3600)
        
        # Obtenir la limite pour cet endpoint
        endpoint_limit = self.get_endpoint_limit(endpoint)
        
        # Appliquer l'algorithme de rate limiting choisi
        allowed = False
        
        if self.config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
            allowed = self.check_token_bucket(client_id, endpoint_limit)
        elif self.config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
            allowed = self.check_sliding_window(client_id, endpoint_limit)
        elif self.config.algorithm == RateLimitAlgorithm.LEAKY_BUCKET:
            allowed = self.check_leaky_bucket(client_id, endpoint_limit)
        elif self.config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
            allowed = self.check_fixed_window(client_id, endpoint_limit)
        
        if not allowed:
            logger.warning(f"Rate limit dépassé pour {client_id} sur {endpoint}")
            return self.create_rate_limit_response(client_id, endpoint)
        
        # Ajouter des headers informatifs à la réponse
        response = await call_next(request)
        
        # Calculer les requêtes restantes (approximatif)
        remaining = max(0, endpoint_limit - 1)
        response.headers["X-RateLimit-Limit"] = str(endpoint_limit)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Reset"] = str(int(time.time()) + 60)
        
        return response

