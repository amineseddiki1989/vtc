"""
Système de métriques avancé pour l'application VTC.
"""

import time
import asyncio
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict, deque
from enum import Enum
import json
import threading
from concurrent.futures import ThreadPoolExecutor

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Types de métriques."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"
    RATE = "rate"


class AlertLevel(Enum):
    """Niveaux d'alerte."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """Point de métrique."""
    timestamp: float
    value: float
    tags: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Alerte système."""
    id: str
    level: AlertLevel
    message: str
    metric_name: str
    threshold: float
    current_value: float
    timestamp: datetime
    resolved: bool = False


class MetricCollector:
    """Collecteur de métriques thread-safe."""
    
    def __init__(self, max_points: int = 10000):
        self.metrics: Dict[str, deque] = defaultdict(lambda: deque(maxlen=max_points))
        self.metadata: Dict[str, Dict[str, Any]] = {}
        self.lock = threading.RLock()
        self.alerts: List[Alert] = []
        self.alert_rules: Dict[str, Dict[str, Any]] = {}
    
    def record_metric(self, name: str, value: float, metric_type: MetricType, 
                     tags: Optional[Dict[str, str]] = None):
        """Enregistre une métrique."""
        with self.lock:
            point = MetricPoint(
                timestamp=time.time(),
                value=value,
                tags=tags or {}
            )
            
            self.metrics[name].append(point)
            self.metadata[name] = {
                "type": metric_type.value,
                "last_update": point.timestamp,
                "total_points": len(self.metrics[name])
            }
            
            # Vérifier les règles d'alerte
            self._check_alert_rules(name, value)
    
    def _check_alert_rules(self, metric_name: str, value: float):
        """Vérifie les règles d'alerte pour une métrique."""
        if metric_name in self.alert_rules:
            rule = self.alert_rules[metric_name]
            threshold = rule.get("threshold")
            condition = rule.get("condition", "greater_than")
            level = AlertLevel(rule.get("level", "warning"))
            
            triggered = False
            if condition == "greater_than" and value > threshold:
                triggered = True
            elif condition == "less_than" and value < threshold:
                triggered = True
            elif condition == "equals" and value == threshold:
                triggered = True
            
            if triggered:
                alert = Alert(
                    id=f"{metric_name}_{int(time.time())}",
                    level=level,
                    message=rule.get("message", f"Alerte pour {metric_name}"),
                    metric_name=metric_name,
                    threshold=threshold,
                    current_value=value,
                    timestamp=datetime.now()
                )
                self.alerts.append(alert)
                logger.warning(f"Alerte déclenchée: {alert.message} (valeur: {value}, seuil: {threshold})")
    
    def get_metric_stats(self, name: str, window_seconds: int = 300) -> Dict[str, Any]:
        """Calcule les statistiques d'une métrique sur une fenêtre de temps."""
        with self.lock:
            if name not in self.metrics:
                return {}
            
            now = time.time()
            window_start = now - window_seconds
            
            # Filtrer les points dans la fenêtre
            points = [p for p in self.metrics[name] if p.timestamp >= window_start]
            
            if not points:
                return {"count": 0}
            
            values = [p.value for p in points]
            
            return {
                "count": len(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "sum": sum(values),
                "latest": values[-1] if values else 0,
                "window_seconds": window_seconds
            }
    
    def add_alert_rule(self, metric_name: str, threshold: float, condition: str = "greater_than",
                      level: str = "warning", message: str = None):
        """Ajoute une règle d'alerte."""
        self.alert_rules[metric_name] = {
            "threshold": threshold,
            "condition": condition,
            "level": level,
            "message": message or f"Seuil dépassé pour {metric_name}"
        }
    
    def get_active_alerts(self) -> List[Alert]:
        """Retourne les alertes actives."""
        return [alert for alert in self.alerts if not alert.resolved]
    
    def resolve_alert(self, alert_id: str):
        """Résout une alerte."""
        for alert in self.alerts:
            if alert.id == alert_id:
                alert.resolved = True
                break


class BusinessMetricsCollector:
    """Collecteur de métriques business spécifiques au VTC."""
    
    def __init__(self):
        self.collector = MetricCollector()
        self.trip_stats = {
            "total_trips": 0,
            "completed_trips": 0,
            "cancelled_trips": 0,
            "active_trips": 0
        }
        self.revenue_stats = {
            "total_revenue": 0.0,
            "daily_revenue": 0.0,
            "average_trip_value": 0.0
        }
        self.driver_stats = {
            "active_drivers": 0,
            "total_drivers": 0,
            "average_rating": 0.0
        }
        self.customer_stats = {
            "total_customers": 0,
            "active_customers": 0,
            "customer_satisfaction": 0.0
        }
        
        # Configurer les alertes business
        self._setup_business_alerts()
    
    def _setup_business_alerts(self):
        """Configure les alertes business."""
        # Alertes de performance
        self.collector.add_alert_rule("trip_cancellation_rate", 0.15, "greater_than", "warning",
                                    "Taux d'annulation élevé")
        self.collector.add_alert_rule("average_response_time", 5000, "greater_than", "error",
                                    "Temps de réponse API trop élevé")
        self.collector.add_alert_rule("active_drivers", 5, "less_than", "critical",
                                    "Nombre de conducteurs actifs critique")
        
        # Alertes de revenus
        self.collector.add_alert_rule("hourly_revenue", 1000, "less_than", "warning",
                                    "Revenus horaires faibles")
        
        # Alertes de satisfaction
        self.collector.add_alert_rule("customer_satisfaction", 4.0, "less_than", "error",
                                    "Satisfaction client faible")
    
    def record_trip_created(self, trip_id: str, estimated_value: float):
        """Enregistre la création d'un trajet."""
        self.trip_stats["total_trips"] += 1
        self.trip_stats["active_trips"] += 1
        
        self.collector.record_metric("trips_total", self.trip_stats["total_trips"], 
                                   MetricType.COUNTER, {"event": "created"})
        self.collector.record_metric("trips_active", self.trip_stats["active_trips"], 
                                   MetricType.GAUGE)
        self.collector.record_metric("trip_estimated_value", estimated_value, 
                                   MetricType.HISTOGRAM, {"trip_id": trip_id})
    
    def record_trip_completed(self, trip_id: str, final_value: float, duration_minutes: int,
                            distance_km: float, rating: float):
        """Enregistre la completion d'un trajet."""
        self.trip_stats["completed_trips"] += 1
        self.trip_stats["active_trips"] = max(0, self.trip_stats["active_trips"] - 1)
        self.revenue_stats["total_revenue"] += final_value
        
        # Calculer la moyenne des valeurs de trajet
        if self.trip_stats["completed_trips"] > 0:
            self.revenue_stats["average_trip_value"] = (
                self.revenue_stats["total_revenue"] / self.trip_stats["completed_trips"]
            )
        
        # Enregistrer les métriques
        self.collector.record_metric("trips_completed", self.trip_stats["completed_trips"], 
                                   MetricType.COUNTER)
        self.collector.record_metric("trips_active", self.trip_stats["active_trips"], 
                                   MetricType.GAUGE)
        self.collector.record_metric("revenue_total", self.revenue_stats["total_revenue"], 
                                   MetricType.COUNTER)
        self.collector.record_metric("trip_duration", duration_minutes, 
                                   MetricType.HISTOGRAM, {"trip_id": trip_id})
        self.collector.record_metric("trip_distance", distance_km, 
                                   MetricType.HISTOGRAM, {"trip_id": trip_id})
        self.collector.record_metric("trip_rating", rating, 
                                   MetricType.HISTOGRAM, {"trip_id": trip_id})
        self.collector.record_metric("trip_value", final_value, 
                                   MetricType.HISTOGRAM, {"trip_id": trip_id})
    
    def record_trip_cancelled(self, trip_id: str, reason: str):
        """Enregistre l'annulation d'un trajet."""
        self.trip_stats["cancelled_trips"] += 1
        self.trip_stats["active_trips"] = max(0, self.trip_stats["active_trips"] - 1)
        
        # Calculer le taux d'annulation
        total_trips = self.trip_stats["total_trips"]
        cancellation_rate = self.trip_stats["cancelled_trips"] / max(1, total_trips)
        
        self.collector.record_metric("trips_cancelled", self.trip_stats["cancelled_trips"], 
                                   MetricType.COUNTER, {"reason": reason})
        self.collector.record_metric("trips_active", self.trip_stats["active_trips"], 
                                   MetricType.GAUGE)
        self.collector.record_metric("trip_cancellation_rate", cancellation_rate, 
                                   MetricType.GAUGE)
    
    def record_driver_activity(self, driver_id: str, status: str, rating: float = None):
        """Enregistre l'activité d'un conducteur."""
        if status == "online":
            self.driver_stats["active_drivers"] += 1
        elif status == "offline":
            self.driver_stats["active_drivers"] = max(0, self.driver_stats["active_drivers"] - 1)
        
        self.collector.record_metric("drivers_active", self.driver_stats["active_drivers"], 
                                   MetricType.GAUGE)
        
        if rating is not None:
            self.collector.record_metric("driver_rating", rating, 
                                       MetricType.HISTOGRAM, {"driver_id": driver_id})
    
    def record_customer_activity(self, customer_id: str, action: str, satisfaction: float = None):
        """Enregistre l'activité d'un client."""
        if action == "login":
            self.customer_stats["active_customers"] += 1
        elif action == "logout":
            self.customer_stats["active_customers"] = max(0, self.customer_stats["active_customers"] - 1)
        
        self.collector.record_metric("customers_active", self.customer_stats["active_customers"], 
                                   MetricType.GAUGE)
        
        if satisfaction is not None:
            self.collector.record_metric("customer_satisfaction", satisfaction, 
                                       MetricType.HISTOGRAM, {"customer_id": customer_id})
    
    def record_api_call(self, endpoint: str, method: str, status_code: int, 
                       response_time_ms: float):
        """Enregistre un appel API."""
        self.collector.record_metric("api_calls_total", 1, MetricType.COUNTER, 
                                   {"endpoint": endpoint, "method": method, "status": str(status_code)})
        self.collector.record_metric("api_response_time", response_time_ms, MetricType.HISTOGRAM, 
                                   {"endpoint": endpoint})
        
        if status_code >= 400:
            self.collector.record_metric("api_errors_total", 1, MetricType.COUNTER, 
                                       {"endpoint": endpoint, "status": str(status_code)})
    
    def record_fiscal_calculation(self, calculation_time_ms: float, cache_hit: bool, 
                                region: str, service_type: str):
        """Enregistre un calcul fiscal."""
        self.collector.record_metric("fiscal_calculations_total", 1, MetricType.COUNTER, 
                                   {"region": region, "service_type": service_type})
        self.collector.record_metric("fiscal_calculation_time", calculation_time_ms, 
                                   MetricType.HISTOGRAM, {"cache_hit": str(cache_hit)})
        
        if cache_hit:
            self.collector.record_metric("fiscal_cache_hits", 1, MetricType.COUNTER)
        else:
            self.collector.record_metric("fiscal_cache_misses", 1, MetricType.COUNTER)
    
    def get_business_dashboard(self) -> Dict[str, Any]:
        """Retourne un tableau de bord business complet."""
        return {
            "trip_metrics": {
                "total_trips": self.trip_stats["total_trips"],
                "completed_trips": self.trip_stats["completed_trips"],
                "cancelled_trips": self.trip_stats["cancelled_trips"],
                "active_trips": self.trip_stats["active_trips"],
                "completion_rate": (
                    self.trip_stats["completed_trips"] / max(1, self.trip_stats["total_trips"])
                ) * 100,
                "cancellation_rate": (
                    self.trip_stats["cancelled_trips"] / max(1, self.trip_stats["total_trips"])
                ) * 100
            },
            "revenue_metrics": {
                "total_revenue": self.revenue_stats["total_revenue"],
                "average_trip_value": self.revenue_stats["average_trip_value"],
                "revenue_per_hour": self.collector.get_metric_stats("revenue_total", 3600).get("sum", 0)
            },
            "driver_metrics": {
                "active_drivers": self.driver_stats["active_drivers"],
                "average_rating": self.collector.get_metric_stats("driver_rating", 86400).get("avg", 0)
            },
            "customer_metrics": {
                "active_customers": self.customer_stats["active_customers"],
                "satisfaction": self.collector.get_metric_stats("customer_satisfaction", 86400).get("avg", 0)
            },
            "performance_metrics": {
                "api_response_time": self.collector.get_metric_stats("api_response_time", 300),
                "fiscal_calculation_time": self.collector.get_metric_stats("fiscal_calculation_time", 300),
                "error_rate": self._calculate_error_rate()
            },
            "alerts": {
                "active_alerts": len(self.collector.get_active_alerts()),
                "recent_alerts": [
                    {
                        "level": alert.level.value,
                        "message": alert.message,
                        "timestamp": alert.timestamp.isoformat()
                    }
                    for alert in self.collector.alerts[-10:]  # 10 dernières alertes
                ]
            }
        }
    
    def _calculate_error_rate(self) -> float:
        """Calcule le taux d'erreur API."""
        total_calls = self.collector.get_metric_stats("api_calls_total", 300).get("sum", 0)
        error_calls = self.collector.get_metric_stats("api_errors_total", 300).get("sum", 0)
        
        if total_calls == 0:
            return 0.0
        
        return (error_calls / total_calls) * 100


class PerformanceMonitor:
    """Moniteur de performance système."""
    
    def __init__(self):
        self.collector = MetricCollector()
        self.executor = ThreadPoolExecutor(max_workers=2)
        self.monitoring_active = False
    
    async def start_monitoring(self):
        """Démarre le monitoring de performance."""
        self.monitoring_active = True
        
        # Démarrer les tâches de monitoring
        asyncio.create_task(self._monitor_system_resources())
        asyncio.create_task(self._monitor_application_health())
        
        logger.info("Monitoring de performance démarré")
    
    def stop_monitoring(self):
        """Arrête le monitoring de performance."""
        self.monitoring_active = False
        self.executor.shutdown(wait=True)
        logger.info("Monitoring de performance arrêté")
    
    async def _monitor_system_resources(self):
        """Monitore les ressources système."""
        while self.monitoring_active:
            try:
                import psutil
                
                # CPU
                cpu_percent = psutil.cpu_percent(interval=1)
                self.collector.record_metric("system_cpu_percent", cpu_percent, MetricType.GAUGE)
                
                # Mémoire
                memory = psutil.virtual_memory()
                self.collector.record_metric("system_memory_percent", memory.percent, MetricType.GAUGE)
                self.collector.record_metric("system_memory_available", memory.available, MetricType.GAUGE)
                
                # Disque
                disk = psutil.disk_usage('/')
                disk_percent = (disk.used / disk.total) * 100
                self.collector.record_metric("system_disk_percent", disk_percent, MetricType.GAUGE)
                
                # Réseau
                network = psutil.net_io_counters()
                self.collector.record_metric("system_network_bytes_sent", network.bytes_sent, MetricType.COUNTER)
                self.collector.record_metric("system_network_bytes_recv", network.bytes_recv, MetricType.COUNTER)
                
            except ImportError:
                logger.warning("psutil non disponible pour le monitoring système")
                break
            except Exception as e:
                logger.error(f"Erreur lors du monitoring système: {e}")
            
            await asyncio.sleep(30)  # Monitoring toutes les 30 secondes
    
    async def _monitor_application_health(self):
        """Monitore la santé de l'application."""
        while self.monitoring_active:
            try:
                # Simuler des métriques d'application
                import random
                
                # Connexions actives (simulation)
                active_connections = random.randint(50, 200)
                self.collector.record_metric("app_active_connections", active_connections, MetricType.GAUGE)
                
                # Pool de base de données (simulation)
                db_pool_size = random.randint(5, 20)
                self.collector.record_metric("app_db_pool_size", db_pool_size, MetricType.GAUGE)
                
                # Threads actifs (simulation)
                active_threads = random.randint(10, 50)
                self.collector.record_metric("app_active_threads", active_threads, MetricType.GAUGE)
                
            except Exception as e:
                logger.error(f"Erreur lors du monitoring d'application: {e}")
            
            await asyncio.sleep(60)  # Monitoring toutes les minutes
    
    def get_performance_report(self) -> Dict[str, Any]:
        """Génère un rapport de performance."""
        return {
            "system_metrics": {
                "cpu": self.collector.get_metric_stats("system_cpu_percent", 300),
                "memory": self.collector.get_metric_stats("system_memory_percent", 300),
                "disk": self.collector.get_metric_stats("system_disk_percent", 300)
            },
            "application_metrics": {
                "connections": self.collector.get_metric_stats("app_active_connections", 300),
                "db_pool": self.collector.get_metric_stats("app_db_pool_size", 300),
                "threads": self.collector.get_metric_stats("app_active_threads", 300)
            },
            "alerts": [
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
                for alert in self.collector.get_active_alerts()
            ]
        }


# Instances globales
business_metrics = BusinessMetricsCollector()
performance_monitor = PerformanceMonitor()

