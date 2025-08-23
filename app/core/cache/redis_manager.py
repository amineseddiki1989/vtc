"""
Gestionnaire Redis optimisé pour la production.
Cache, sessions, rate limiting et pub/sub.
"""

import json
import pickle
import logging
from typing import Any, Optional, Union, Dict, List
from datetime import timedelta, datetime
from contextlib import asynccontextmanager

import redis.asyncio as redis
from redis.asyncio import ConnectionPool, Redis
from redis.exceptions import RedisError, ConnectionError

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

class RedisManager:
    """Gestionnaire Redis asynchrone avec fonctionnalités avancées."""
    
    def __init__(self):
        self.settings = get_settings()
        self._pool: Optional[ConnectionPool] = None
        self._redis: Optional[Redis] = None
        self._pubsub_redis: Optional[Redis] = None
        
    async def initialize(self) -> None:
        """Initialise la connexion Redis avec pool optimisé."""
        try:
            # Pool de connexions optimisé
            self._pool = ConnectionPool.from_url(
                self.settings.redis_url,
                max_connections=self.settings.redis_max_connections,
                retry_on_timeout=True,
                retry_on_error=[ConnectionError],
                health_check_interval=30,
                socket_keepalive=True,
                socket_keepalive_options={
                    1: 1,  # TCP_KEEPIDLE
                    2: 3,  # TCP_KEEPINTVL  
                    3: 5   # TCP_KEEPCNT
                },
                decode_responses=False  # Pour supporter pickle
            )
            
            # Client Redis principal
            self._redis = Redis(
                connection_pool=self._pool,
                socket_timeout=self.settings.redis_socket_timeout,
                socket_connect_timeout=self.settings.redis_connect_timeout,
                retry_on_timeout=True
            )
            
            # Client Redis dédié pour pub/sub
            self._pubsub_redis = Redis(
                connection_pool=self._pool,
                socket_timeout=None,  # Pas de timeout pour pub/sub
                socket_connect_timeout=self.settings.redis_connect_timeout
            )
            
            # Test de connexion
            await self._redis.ping()
            
            logger.info("✅ Redis initialisé avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation de Redis: {e}")
            raise
    
    async def close(self) -> None:
        """Ferme toutes les connexions Redis."""
        try:
            if self._redis:
                await self._redis.close()
            if self._pubsub_redis:
                await self._pubsub_redis.close()
            if self._pool:
                await self._pool.disconnect()
                
            logger.info("Connexions Redis fermées")
            
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de Redis: {e}")
    
    # === CACHE OPERATIONS ===
    
    async def set(
        self, 
        key: str, 
        value: Any, 
        expire: Optional[Union[int, timedelta]] = None,
        serialize: bool = True
    ) -> bool:
        """Stocke une valeur dans Redis avec sérialisation automatique."""
        try:
            if serialize:
                if isinstance(value, (dict, list)):
                    serialized_value = json.dumps(value, default=str)
                else:
                    serialized_value = pickle.dumps(value)
            else:
                serialized_value = value
                
            return await self._redis.set(key, serialized_value, ex=expire)
            
        except Exception as e:
            logger.error(f"Erreur Redis SET {key}: {e}")
            return False
    
    async def get(
        self, 
        key: str, 
        deserialize: bool = True,
        default: Any = None
    ) -> Any:
        """Récupère une valeur de Redis avec désérialisation automatique."""
        try:
            value = await self._redis.get(key)
            if value is None:
                return default
                
            if not deserialize:
                return value
                
            # Tentative de désérialisation JSON d'abord
            try:
                return json.loads(value)
            except (json.JSONDecodeError, TypeError):
                # Fallback sur pickle
                try:
                    return pickle.loads(value)
                except (pickle.PickleError, TypeError):
                    return value.decode('utf-8') if isinstance(value, bytes) else value
                    
        except Exception as e:
            logger.error(f"Erreur Redis GET {key}: {e}")
            return default
    
    async def delete(self, *keys: str) -> int:
        """Supprime une ou plusieurs clés."""
        try:
            return await self._redis.delete(*keys)
        except Exception as e:
            logger.error(f"Erreur Redis DELETE: {e}")
            return 0
    
    async def exists(self, key: str) -> bool:
        """Vérifie si une clé existe."""
        try:
            return bool(await self._redis.exists(key))
        except Exception as e:
            logger.error(f"Erreur Redis EXISTS {key}: {e}")
            return False
    
    async def expire(self, key: str, seconds: int) -> bool:
        """Définit une expiration sur une clé."""
        try:
            return await self._redis.expire(key, seconds)
        except Exception as e:
            logger.error(f"Erreur Redis EXPIRE {key}: {e}")
            return False
    
    async def ttl(self, key: str) -> int:
        """Retourne le TTL d'une clé."""
        try:
            return await self._redis.ttl(key)
        except Exception as e:
            logger.error(f"Erreur Redis TTL {key}: {e}")
            return -1
    
    # === RATE LIMITING ===
    
    async def rate_limit(
        self, 
        key: str, 
        limit: int, 
        window: int,
        identifier: str = ""
    ) -> Dict[str, Any]:
        """Implémente un rate limiting avec sliding window."""
        try:
            full_key = f"rate_limit:{key}:{identifier}" if identifier else f"rate_limit:{key}"
            current_time = datetime.now().timestamp()
            window_start = current_time - window
            
            # Pipeline pour atomicité
            pipe = self._redis.pipeline()
            
            # Supprimer les entrées expirées
            pipe.zremrangebyscore(full_key, 0, window_start)
            
            # Compter les requêtes actuelles
            pipe.zcard(full_key)
            
            # Ajouter la requête actuelle
            pipe.zadd(full_key, {str(current_time): current_time})
            
            # Définir l'expiration
            pipe.expire(full_key, window + 1)
            
            results = await pipe.execute()
            current_requests = results[1]
            
            return {
                "allowed": current_requests < limit,
                "current": current_requests + 1,
                "limit": limit,
                "window": window,
                "reset_time": current_time + window
            }
            
        except Exception as e:
            logger.error(f"Erreur rate limiting {key}: {e}")
            return {"allowed": True, "current": 0, "limit": limit, "window": window}
    
    # === SESSION MANAGEMENT ===
    
    async def create_session(
        self, 
        session_id: str, 
        user_data: Dict[str, Any],
        expire_seconds: int = 3600
    ) -> bool:
        """Crée une session utilisateur."""
        session_key = f"session:{session_id}"
        session_data = {
            "user_data": user_data,
            "created_at": datetime.now().isoformat(),
            "last_accessed": datetime.now().isoformat()
        }
        return await self.set(session_key, session_data, expire=expire_seconds)
    
    async def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Récupère une session utilisateur."""
        session_key = f"session:{session_id}"
        session_data = await self.get(session_key)
        
        if session_data:
            # Mettre à jour le last_accessed
            session_data["last_accessed"] = datetime.now().isoformat()
            await self.set(session_key, session_data, expire=3600)
            
        return session_data
    
    async def delete_session(self, session_id: str) -> bool:
        """Supprime une session utilisateur."""
        session_key = f"session:{session_id}"
        return bool(await self.delete(session_key))
    
    # === PUB/SUB MESSAGING ===
    
    async def publish(self, channel: str, message: Any) -> int:
        """Publie un message sur un canal."""
        try:
            if isinstance(message, (dict, list)):
                message = json.dumps(message, default=str)
            elif not isinstance(message, (str, bytes)):
                message = str(message)
                
            return await self._pubsub_redis.publish(channel, message)
            
        except Exception as e:
            logger.error(f"Erreur Redis PUBLISH {channel}: {e}")
            return 0
    
    @asynccontextmanager
    async def subscribe(self, *channels: str):
        """Context manager pour s'abonner à des canaux."""
        pubsub = self._pubsub_redis.pubsub()
        try:
            await pubsub.subscribe(*channels)
            yield pubsub
        finally:
            await pubsub.unsubscribe(*channels)
            await pubsub.close()
    
    # === HEALTH CHECK ===
    
    async def health_check(self) -> Dict[str, Any]:
        """Vérifie l'état de santé de Redis."""
        try:
            # Test de ping
            ping_result = await self._redis.ping()
            
            # Informations sur la connexion
            info = await self._redis.info()
            
            return {
                "status": "healthy" if ping_result else "unhealthy",
                "ping": ping_result,
                "connected_clients": info.get("connected_clients", 0),
                "used_memory": info.get("used_memory_human", "unknown"),
                "redis_version": info.get("redis_version", "unknown"),
                "timestamp": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

# Instance globale du gestionnaire
redis_manager = RedisManager()

async def get_redis() -> RedisManager:
    """Dépendance FastAPI pour obtenir le gestionnaire Redis."""
    return redis_manager

async def init_redis() -> None:
    """Initialise Redis au démarrage de l'application."""
    await redis_manager.initialize()

async def close_redis() -> None:
    """Ferme Redis à l'arrêt de l'application."""
    await redis_manager.close()

