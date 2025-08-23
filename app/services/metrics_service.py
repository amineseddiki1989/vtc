"""
Service de collecte et gestion des métriques de performance.
"""

import asyncio
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Union
from contextlib import asynccontextmanager
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, desc
from collections import defaultdict, deque
import threading
import json

from ..models.metrics import Metric, MetricSummary, Alert, SystemHealth, MetricType, MetricCategory
from ..core.database.base import get_db


class MetricsCollector:
    """Collecteur de métriques thread-safe avec buffer en mémoire."""
    
    def __init__(self, buffer_size: int = 1000, flush_interval: int = 30):
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.buffer = deque(maxlen=buffer_size)
        self.lock = threading.Lock()
        self.running = False
        self.flush_thread = None
        
        # Métriques en temps réel (en mémoire)
        self.realtime_metrics = defaultdict(lambda: {"value": 0, "count": 0, "last_update": datetime.utcnow()})
        
    def start(self):
        """Démarre le collecteur de métriques."""
        if not self.running:
            self.running = True
            self.flush_thread = threading.Thread(target=self._flush_loop, daemon=True)
            self.flush_thread.start()
    
    def stop(self):
        """Arrête le collecteur de métriques."""
        self.running = False
        if self.flush_thread:
            self.flush_thread.join(timeout=5)
        self._flush_buffer()  # Flush final
    
    def record_metric(
        self,
        name: str,
        value: Union[int, float],
        metric_type: MetricType = MetricType.GAUGE,
        category: MetricCategory = MetricCategory.SYSTEM,
        labels: Optional[Dict[str, Any]] = None,
        user_id: Optional[str] = None,
        session_id: Optional[str] = None,
        request_id: Optional[str] = None,
        description: Optional[str] = None
    ):
        """Enregistre une métrique dans le buffer."""
        
        # Protection contre les erreurs enum
        metric_type_value = metric_type.value if hasattr(metric_type, 'value') else str(metric_type)
        category_value = category.value if hasattr(category, 'value') else str(category)
        
        metric_data = {
            "id": str(uuid.uuid4()),
            "name": name,
            "value": float(value),
            "metric_type": metric_type_value,
            "category": category_value,
            "labels": labels or {},
            "user_id": user_id,
            "session_id": session_id,
            "request_id": request_id,
            "description": description,
            "timestamp": datetime.utcnow(),
            "created_at": datetime.utcnow()
        }
        
        with self.lock:
            self.buffer.append(metric_data)
            
            # Mise à jour des métriques temps réel
            key = f"{category_value}:{name}"
            metric_type_str = metric_type_value if isinstance(metric_type_value, str) else metric_type_value
            if metric_type_str == "counter" or (hasattr(metric_type, 'value') and metric_type.value == "counter"):
                self.realtime_metrics[key]["value"] += value
                self.realtime_metrics[key]["count"] += 1
            else:
                self.realtime_metrics[key]["value"] = value
                self.realtime_metrics[key]["count"] = 1
            self.realtime_metrics[key]["last_update"] = datetime.utcnow()
    
    def get_realtime_metric(self, category: str, name: str) -> Optional[Dict]:
        """Récupère une métrique temps réel."""
        key = f"{category}:{name}"
        with self.lock:
            return self.realtime_metrics.get(key)
    
    def get_all_realtime_metrics(self) -> Dict[str, Dict]:
        """Récupère toutes les métriques temps réel."""
        with self.lock:
            return dict(self.realtime_metrics)
    
    def _flush_loop(self):
        """Boucle de flush périodique."""
        while self.running:
            time.sleep(self.flush_interval)
            if self.running:
                self._flush_buffer()
    
    def _flush_buffer(self):
        """Flush le buffer vers la base de données."""
        if not self.buffer:
            return
        
        metrics_to_flush = []
        with self.lock:
            metrics_to_flush = list(self.buffer)
            self.buffer.clear()
        
        if not metrics_to_flush:
            return
        
        try:
            db = next(get_db())
            try:
                # Insertion en batch pour optimiser les performances
                db.bulk_insert_mappings(Metric, metrics_to_flush)
                db.commit()
            except Exception as e:
                db.rollback()
                print(f"Erreur lors du flush des métriques: {e}")
            finally:
                db.close()
        except Exception as e:
            print(f"Erreur de connexion DB pour flush métriques: {e}")


class MetricsService:
    """Service principal de gestion des métriques."""
    
    def __init__(self, db: Session = None):
        self.db = db
        self.collector = MetricsCollector()
    
    @classmethod
    def get_instance(cls, db: Session = None):
        """Obtenir une instance du service de métriques."""
        if not hasattr(cls, '_instance'):
            cls._instance = cls(db)
        if db and not cls._instance.db:
            cls._instance.db = db
        return cls._instance
    
    def start_collection(self):
        """Démarre la collecte de métriques."""
        self.collector.start()
    
    def stop_collection(self):
        """Arrête la collecte de métriques."""
        self.collector.stop()
    
    # Méthodes de collecte simplifiées
    def increment_counter(self, name: str, value: int = 1, **kwargs):
        """Incrémente un compteur."""
        self.collector.record_metric(
            name=name,
            value=value,
            metric_type=MetricType.COUNTER,
            **kwargs
        )
    
    def set_gauge(self, name: str, value: Union[int, float], **kwargs):
        """Définit une valeur de jauge."""
        self.collector.record_metric(
            name=name,
            value=value,
            metric_type=MetricType.GAUGE,
            **kwargs
        )
    
    def record_timer(self, name: str, duration: float, **kwargs):
        """Enregistre un temps d'exécution."""
        self.collector.record_metric(
            name=name,
            value=duration,
            metric_type=MetricType.TIMER,
            **kwargs
        )
    
    @asynccontextmanager
    async def timer_context(self, name: str, **kwargs):
        """Context manager pour mesurer le temps d'exécution."""
        start_time = time.time()
        try:
            yield
        finally:
            duration = time.time() - start_time
            self.record_timer(name, duration, **kwargs)
    
    # Méthodes de récupération des métriques
    def get_metrics(
        self,
        name: Optional[str] = None,
        category: Optional[str] = None,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 1000
    ) -> List[Metric]:
        """Récupère les métriques selon les critères."""
        query = self.db.query(Metric)
        
        if name:
            query = query.filter(Metric.name == name)
        if category:
            query = query.filter(Metric.category == category)
        if start_time:
            query = query.filter(Metric.timestamp >= start_time)
        if end_time:
            query = query.filter(Metric.timestamp <= end_time)
        
        return query.order_by(desc(Metric.timestamp)).limit(limit).all()
    
    def get_metric_aggregation(
        self,
        name: str,
        aggregation: str = "avg",  # avg, sum, count, min, max
        period: str = "hour",      # hour, day, week, month
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> List[Dict]:
        """Récupère les métriques agrégées."""
        if not start_time:
            start_time = datetime.utcnow() - timedelta(days=1)
        if not end_time:
            end_time = datetime.utcnow()
        
        # Définir le format de troncature selon la période
        trunc_format = {
            "hour": "hour",
            "day": "day",
            "week": "week",
            "month": "month"
        }.get(period, "hour")
        
        # Fonction d'agrégation
        agg_func = {
            "avg": func.avg(Metric.value),
            "sum": func.sum(Metric.value),
            "count": func.count(Metric.id),
            "min": func.min(Metric.value),
            "max": func.max(Metric.value)
        }.get(aggregation, func.avg(Metric.value))
        
        query = self.db.query(
            func.date_trunc(trunc_format, Metric.timestamp).label("period"),
            agg_func.label("value")
        ).filter(
            and_(
                Metric.name == name,
                Metric.timestamp >= start_time,
                Metric.timestamp <= end_time
            )
        ).group_by(
            func.date_trunc(trunc_format, Metric.timestamp)
        ).order_by("period")
        
        results = query.all()
        return [{"period": r.period, "value": float(r.value)} for r in results]
    
    def get_realtime_metrics(self) -> Dict[str, Any]:
        """Récupère les métriques temps réel."""
        return self.collector.get_all_realtime_metrics()
    
    def get_system_health(self) -> Optional[SystemHealth]:
        """Récupère l'état de santé système le plus récent."""
        return self.db.query(SystemHealth).order_by(desc(SystemHealth.timestamp)).first()
    
    def update_system_health(self, health_data: Dict[str, Any]):
        """Met à jour l'état de santé du système."""
        health = SystemHealth(**health_data)
        self.db.add(health)
        self.db.commit()
        return health
    
    # Méthodes d'alerte
    def create_alert(
        self,
        name: str,
        metric_name: str,
        condition: str,
        threshold: float,
        **kwargs
    ) -> Alert:
        """Crée une nouvelle alerte."""
        alert = Alert(
            name=name,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            **kwargs
        )
        self.db.add(alert)
        self.db.commit()
        return alert
    
    def check_alerts(self):
        """Vérifie toutes les alertes actives."""
        alerts = self.db.query(Alert).filter(Alert.is_active == True).all()
        triggered_alerts = []
        
        for alert in alerts:
            # Récupérer la dernière valeur de la métrique
            latest_metric = self.db.query(Metric).filter(
                Metric.name == alert.metric_name
            ).order_by(desc(Metric.timestamp)).first()
            
            if latest_metric:
                should_trigger = self._evaluate_alert_condition(
                    latest_metric.value, alert.condition, alert.threshold
                )
                
                if should_trigger and not alert.is_triggered:
                    alert.is_triggered = True
                    alert.last_triggered_at = datetime.utcnow()
                    alert.trigger_count += 1
                    triggered_alerts.append(alert)
                elif not should_trigger and alert.is_triggered:
                    alert.is_triggered = False
        
        if triggered_alerts:
            self.db.commit()
        
        return triggered_alerts
    
    def _evaluate_alert_condition(self, value: float, condition: str, threshold: float) -> bool:
        """Évalue une condition d'alerte."""
        conditions = {
            "gt": value > threshold,
            "gte": value >= threshold,
            "lt": value < threshold,
            "lte": value <= threshold,
            "eq": value == threshold,
            "ne": value != threshold
        }
        return conditions.get(condition, False)
    
    # Méthodes utilitaires
    def cleanup_old_metrics(self, days_to_keep: int = 30):
        """Nettoie les anciennes métriques."""
        cutoff_date = datetime.utcnow() - timedelta(days=days_to_keep)
        deleted_count = self.db.query(Metric).filter(
            Metric.timestamp < cutoff_date
        ).delete()
        self.db.commit()
        return deleted_count
    
    def get_metrics_summary(self) -> Dict[str, Any]:
        """Récupère un résumé des métriques."""
        total_metrics = self.db.query(func.count(Metric.id)).scalar()
        
        categories_count = self.db.query(
            Metric.category,
            func.count(Metric.id).label("count")
        ).group_by(Metric.category).all()
        
        recent_metrics = self.db.query(func.count(Metric.id)).filter(
            Metric.timestamp >= datetime.utcnow() - timedelta(hours=1)
        ).scalar()
        
        return {
            "total_metrics": total_metrics,
            "categories": {cat: count for cat, count in categories_count},
            "recent_metrics_1h": recent_metrics,
            "realtime_metrics_count": len(self.collector.get_all_realtime_metrics())
        }


# Instance globale du collecteur
_global_collector = MetricsCollector()

def get_metrics_collector() -> MetricsCollector:
    """Récupère l'instance globale du collecteur."""
    return _global_collector

def start_metrics_collection():
    """Démarre la collecte globale de métriques."""
    _global_collector.start()

def stop_metrics_collection():
    """Arrête la collecte globale de métriques."""
    _global_collector.stop()

