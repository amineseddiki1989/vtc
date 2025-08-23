"""
Système de health checks complet pour la production.
Monitoring de tous les composants critiques.
"""

import time
import asyncio
import psutil
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable
from enum import Enum

from fastapi import HTTPException
from pydantic import BaseModel

from ..database.postgresql import db_manager
from ..cache.redis_manager import redis_manager
from ..config.production_settings import get_settings

class HealthStatus(str, Enum):
    """Statuts de santé possibles."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"

class ComponentHealth(BaseModel):
    """Modèle pour la santé d'un composant."""
    name: str
    status: HealthStatus
    response_time_ms: float
    details: Dict[str, Any] = {}
    error: Optional[str] = None
    last_check: datetime

class SystemHealth(BaseModel):
    """Modèle pour la santé globale du système."""
    status: HealthStatus
    timestamp: datetime
    uptime_seconds: float
    components: List[ComponentHealth]
    summary: Dict[str, Any]

class HealthChecker:
    """Gestionnaire de health checks."""
    
    def __init__(self):
        self.settings = get_settings()
        self.start_time = time.time()
        self.checks: Dict[str, Callable] = {}
        self._register_default_checks()
    
    def _register_default_checks(self):
        """Enregistre les checks par défaut."""
        self.checks = {
            "database": self._check_database,
            "redis": self._check_redis,
            "memory": self._check_memory,
            "disk": self._check_disk,
            "cpu": self._check_cpu,
            "network": self._check_network
        }
    
    async def _check_database(self) -> ComponentHealth:
        """Vérifie la santé de la base de données."""
        start_time = time.time()
        
        try:
            health_data = await db_manager.health_check()
            response_time = (time.time() - start_time) * 1000
            
            if health_data["status"] == "healthy":
                status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="database",
                status=status,
                response_time_ms=response_time,
                details=health_data,
                last_check=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="database",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e),
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_redis(self) -> ComponentHealth:
        """Vérifie la santé de Redis."""
        start_time = time.time()
        
        try:
            health_data = await redis_manager.health_check()
            response_time = (time.time() - start_time) * 1000
            
            if health_data["status"] == "healthy":
                status = HealthStatus.HEALTHY
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="redis",
                status=status,
                response_time_ms=response_time,
                details=health_data,
                last_check=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="redis",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e),
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_memory(self) -> ComponentHealth:
        """Vérifie l'utilisation mémoire."""
        start_time = time.time()
        
        try:
            memory = psutil.virtual_memory()
            response_time = (time.time() - start_time) * 1000
            
            # Seuils d'alerte
            if memory.percent < 80:
                status = HealthStatus.HEALTHY
            elif memory.percent < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="memory",
                status=status,
                response_time_ms=response_time,
                details={
                    "total_gb": round(memory.total / (1024**3), 2),
                    "available_gb": round(memory.available / (1024**3), 2),
                    "used_percent": memory.percent,
                    "free_percent": 100 - memory.percent
                },
                last_check=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="memory",
                status=HealthStatus.UNKNOWN,
                response_time_ms=response_time,
                error=str(e),
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_disk(self) -> ComponentHealth:
        """Vérifie l'espace disque."""
        start_time = time.time()
        
        try:
            disk = psutil.disk_usage('/')
            response_time = (time.time() - start_time) * 1000
            
            # Seuils d'alerte
            if disk.percent < 80:
                status = HealthStatus.HEALTHY
            elif disk.percent < 90:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="disk",
                status=status,
                response_time_ms=response_time,
                details={
                    "total_gb": round(disk.total / (1024**3), 2),
                    "free_gb": round(disk.free / (1024**3), 2),
                    "used_percent": disk.percent,
                    "free_percent": 100 - disk.percent
                },
                last_check=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="disk",
                status=HealthStatus.UNKNOWN,
                response_time_ms=response_time,
                error=str(e),
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_cpu(self) -> ComponentHealth:
        """Vérifie l'utilisation CPU."""
        start_time = time.time()
        
        try:
            # Mesurer sur 1 seconde pour plus de précision
            cpu_percent = psutil.cpu_percent(interval=1)
            response_time = (time.time() - start_time) * 1000
            
            # Seuils d'alerte
            if cpu_percent < 70:
                status = HealthStatus.HEALTHY
            elif cpu_percent < 85:
                status = HealthStatus.DEGRADED
            else:
                status = HealthStatus.UNHEALTHY
            
            return ComponentHealth(
                name="cpu",
                status=status,
                response_time_ms=response_time,
                details={
                    "usage_percent": cpu_percent,
                    "core_count": psutil.cpu_count(),
                    "load_average": psutil.getloadavg() if hasattr(psutil, 'getloadavg') else None
                },
                last_check=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="cpu",
                status=HealthStatus.UNKNOWN,
                response_time_ms=response_time,
                error=str(e),
                last_check=datetime.now(timezone.utc)
            )
    
    async def _check_network(self) -> ComponentHealth:
        """Vérifie la connectivité réseau."""
        start_time = time.time()
        
        try:
            import socket
            
            # Test de connectivité DNS
            socket.gethostbyname('google.com')
            
            # Statistiques réseau
            net_io = psutil.net_io_counters()
            response_time = (time.time() - start_time) * 1000
            
            return ComponentHealth(
                name="network",
                status=HealthStatus.HEALTHY,
                response_time_ms=response_time,
                details={
                    "bytes_sent": net_io.bytes_sent,
                    "bytes_recv": net_io.bytes_recv,
                    "packets_sent": net_io.packets_sent,
                    "packets_recv": net_io.packets_recv,
                    "errors_in": net_io.errin,
                    "errors_out": net_io.errout
                },
                last_check=datetime.now(timezone.utc)
            )
            
        except Exception as e:
            response_time = (time.time() - start_time) * 1000
            return ComponentHealth(
                name="network",
                status=HealthStatus.UNHEALTHY,
                response_time_ms=response_time,
                error=str(e),
                last_check=datetime.now(timezone.utc)
            )
    
    async def check_all(self) -> SystemHealth:
        """Effectue tous les health checks."""
        components = []
        
        # Exécuter tous les checks en parallèle
        tasks = [check() for check in self.checks.values()]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, ComponentHealth):
                components.append(result)
            elif isinstance(result, Exception):
                # Créer un composant en erreur
                components.append(ComponentHealth(
                    name="unknown",
                    status=HealthStatus.UNKNOWN,
                    response_time_ms=0,
                    error=str(result),
                    last_check=datetime.now(timezone.utc)
                ))
        
        # Déterminer le statut global
        statuses = [comp.status for comp in components]
        
        if all(status == HealthStatus.HEALTHY for status in statuses):
            overall_status = HealthStatus.HEALTHY
        elif any(status == HealthStatus.UNHEALTHY for status in statuses):
            overall_status = HealthStatus.UNHEALTHY
        elif any(status == HealthStatus.DEGRADED for status in statuses):
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.UNKNOWN
        
        # Calculer l'uptime
        uptime = time.time() - self.start_time
        
        # Résumé
        summary = {
            "total_components": len(components),
            "healthy_components": len([c for c in components if c.status == HealthStatus.HEALTHY]),
            "degraded_components": len([c for c in components if c.status == HealthStatus.DEGRADED]),
            "unhealthy_components": len([c for c in components if c.status == HealthStatus.UNHEALTHY]),
            "average_response_time_ms": sum(c.response_time_ms for c in components) / len(components) if components else 0,
            "uptime_hours": round(uptime / 3600, 2)
        }
        
        return SystemHealth(
            status=overall_status,
            timestamp=datetime.now(timezone.utc),
            uptime_seconds=uptime,
            components=components,
            summary=summary
        )
    
    async def check_component(self, component_name: str) -> ComponentHealth:
        """Effectue le health check d'un composant spécifique."""
        if component_name not in self.checks:
            raise HTTPException(
                status_code=404,
                detail=f"Composant '{component_name}' non trouvé"
            )
        
        return await self.checks[component_name]()
    
    def register_check(self, name: str, check_func: Callable) -> None:
        """Enregistre un nouveau health check."""
        self.checks[name] = check_func
    
    async def get_readiness(self) -> Dict[str, Any]:
        """Vérifie si l'application est prête à recevoir du trafic."""
        # Vérifier les composants critiques
        critical_checks = ["database", "redis"]
        
        for component in critical_checks:
            health = await self.check_component(component)
            if health.status == HealthStatus.UNHEALTHY:
                return {
                    "ready": False,
                    "reason": f"Composant critique '{component}' non disponible",
                    "details": health.dict()
                }
        
        return {
            "ready": True,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_liveness(self) -> Dict[str, Any]:
        """Vérifie si l'application est vivante."""
        # Simple check que l'application répond
        return {
            "alive": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "uptime_seconds": time.time() - self.start_time
        }

# Instance globale
health_checker = HealthChecker()

async def get_health_checker() -> HealthChecker:
    """Dépendance FastAPI pour obtenir le health checker."""
    return health_checker

