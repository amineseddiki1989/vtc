"""
Modèles de données pour le système de métriques de performance.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, Float, Integer, DateTime, Text, JSON, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import Index

from ..core.database.base import Base


class MetricType(str, Enum):
    """Types de métriques."""
    COUNTER = "counter"          # Compteur (incrémental)
    GAUGE = "gauge"             # Jauge (valeur instantanée)
    HISTOGRAM = "histogram"     # Histogramme (distribution)
    TIMER = "timer"            # Temps d'exécution


class MetricCategory(str, Enum):
    """Catégories de métriques."""
    SYSTEM = "system"           # Métriques système (API, DB, etc.)
    BUSINESS = "business"       # Métriques métier (courses, revenus, etc.)
    USER = "user"              # Métriques utilisateur (satisfaction, rétention)
    PERFORMANCE = "performance" # Métriques de performance


class Metric(Base):
    """Modèle principal pour stocker les métriques."""
    
    __tablename__ = "metrics"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Identification de la métrique
    name = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    metric_type = Column(String(50), nullable=False)
    
    # Valeurs
    value = Column(Float, nullable=False)
    count = Column(Integer, default=1, nullable=False)
    
    # Métadonnées
    labels = Column(JSON, nullable=True)  # Labels pour filtrage (ex: {"endpoint": "/api/v1/trips", "method": "POST"})
    description = Column(Text, nullable=True)
    
    # Contexte
    user_id = Column(String(36), nullable=True, index=True)
    session_id = Column(String(255), nullable=True)
    request_id = Column(String(255), nullable=True)
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Index composites pour optimiser les requêtes
    __table_args__ = (
        Index('idx_metrics_name_timestamp', 'name', 'timestamp'),
        Index('idx_metrics_category_timestamp', 'category', 'timestamp'),
        Index('idx_metrics_user_timestamp', 'user_id', 'timestamp'),
    )
    
    def __repr__(self):
        return f"<Metric(name={self.name}, value={self.value}, timestamp={self.timestamp})>"


class MetricSummary(Base):
    """Modèle pour les résumés de métriques (agrégations pré-calculées)."""
    
    __tablename__ = "metric_summaries"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Identification
    metric_name = Column(String(255), nullable=False, index=True)
    category = Column(String(50), nullable=False, index=True)
    
    # Période d'agrégation
    period_type = Column(String(20), nullable=False)  # hour, day, week, month
    period_start = Column(DateTime, nullable=False, index=True)
    period_end = Column(DateTime, nullable=False)
    
    # Valeurs agrégées
    total_count = Column(Integer, default=0, nullable=False)
    sum_value = Column(Float, default=0.0, nullable=False)
    avg_value = Column(Float, default=0.0, nullable=False)
    min_value = Column(Float, nullable=True)
    max_value = Column(Float, nullable=True)
    
    # Métadonnées
    labels = Column(JSON, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Index pour optimiser les requêtes d'agrégation
    __table_args__ = (
        Index('idx_summary_metric_period', 'metric_name', 'period_type', 'period_start'),
        Index('idx_summary_category_period', 'category', 'period_type', 'period_start'),
    )
    
    def __repr__(self):
        return f"<MetricSummary(metric={self.metric_name}, period={self.period_type}, avg={self.avg_value})>"


class Alert(Base):
    """Modèle pour les alertes basées sur les métriques."""
    
    __tablename__ = "alerts"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Configuration de l'alerte
    name = Column(String(255), nullable=False)
    metric_name = Column(String(255), nullable=False, index=True)
    condition = Column(String(50), nullable=False)  # gt, lt, eq, gte, lte
    threshold = Column(Float, nullable=False)
    
    # État de l'alerte
    is_active = Column(Boolean, default=True, nullable=False)
    is_triggered = Column(Boolean, default=False, nullable=False)
    
    # Notification
    notification_channels = Column(JSON, nullable=True)  # email, slack, webhook, etc.
    last_triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0, nullable=False)
    
    # Métadonnées
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="medium", nullable=False)  # low, medium, high, critical
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<Alert(name={self.name}, metric={self.metric_name}, threshold={self.threshold})>"


class SystemHealth(Base):
    """Modèle pour surveiller la santé globale du système."""
    
    __tablename__ = "system_health"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Métriques système
    cpu_usage = Column(Float, nullable=True)
    memory_usage = Column(Float, nullable=True)
    disk_usage = Column(Float, nullable=True)
    
    # Métriques application
    active_connections = Column(Integer, nullable=True)
    response_time_avg = Column(Float, nullable=True)
    error_rate = Column(Float, nullable=True)
    
    # Métriques métier
    active_trips = Column(Integer, nullable=True)
    active_drivers = Column(Integer, nullable=True)
    active_passengers = Column(Integer, nullable=True)
    
    # État global
    overall_status = Column(String(20), default="healthy", nullable=False)  # healthy, warning, critical
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<SystemHealth(status={self.overall_status}, timestamp={self.timestamp})>"


class SystemMetric(Base):
    """Modèle pour les métriques système spécifiques."""
    
    __tablename__ = "system_metrics"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Identification
    metric_name = Column(String(255), nullable=False, index=True)
    component = Column(String(100), nullable=False)  # api, database, cache, etc.
    
    # Valeurs
    value = Column(Float, nullable=False)
    unit = Column(String(50), nullable=True)  # ms, %, MB, etc.
    
    # Métadonnées
    labels = Column(JSON, nullable=True)
    threshold_warning = Column(Float, nullable=True)
    threshold_critical = Column(Float, nullable=True)
    
    # Timestamp
    timestamp = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
    
    def __repr__(self):
        return f"<SystemMetric(name={self.metric_name}, value={self.value}, component={self.component})>"


class MetricAlert(Base):
    """Modèle pour les alertes basées sur les métriques (alias pour Alert)."""
    
    __tablename__ = "metric_alerts"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Configuration de l'alerte
    name = Column(String(255), nullable=False)
    metric_name = Column(String(255), nullable=False, index=True)
    condition = Column(String(50), nullable=False)  # gt, lt, eq, gte, lte
    threshold = Column(Float, nullable=False)
    
    # État de l'alerte
    is_active = Column(Boolean, default=True, nullable=False)
    is_triggered = Column(Boolean, default=False, nullable=False)
    
    # Notification
    notification_channels = Column(JSON, nullable=True)  # email, slack, webhook, etc.
    last_triggered_at = Column(DateTime, nullable=True)
    trigger_count = Column(Integer, default=0, nullable=False)
    
    # Métadonnées
    description = Column(Text, nullable=True)
    severity = Column(String(20), default="medium", nullable=False)  # low, medium, high, critical
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    def __repr__(self):
        return f"<MetricAlert(name={self.name}, metric={self.metric_name}, threshold={self.threshold})>"

