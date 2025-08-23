"""
API pour accéder aux métriques de performance.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta

from ...core.database.base import get_db
from ...core.auth.dependencies import get_current_user
from ...models.user import User
from ...models.metrics import Metric, MetricSummary, Alert, SystemHealth
from ...services.metrics_service import MetricsService
from ...core.monitoring.decorators import monitor_function, MetricCategory

router = APIRouter(prefix="/metrics", tags=["Métriques"])


@router.get("/realtime", summary="Métriques temps réel")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_realtime_metrics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère les métriques en temps réel.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    try:
        metrics_service = MetricsService(db)
        realtime_data = metrics_service.get_realtime_metrics()
        
        return {
            "timestamp": datetime.utcnow(),
            "metrics": realtime_data,
            "count": len(realtime_data)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des métriques: {str(e)}"
        )


@router.get("/history", summary="Historique des métriques")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_metrics_history(
    name: Optional[str] = Query(None, description="Nom de la métrique"),
    category: Optional[str] = Query(None, description="Catégorie de métrique"),
    start_time: Optional[datetime] = Query(None, description="Date de début"),
    end_time: Optional[datetime] = Query(None, description="Date de fin"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum de résultats"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère l'historique des métriques.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    try:
        metrics_service = MetricsService(db)
        metrics = metrics_service.get_metrics(
            name=name,
            category=category,
            start_time=start_time,
            end_time=end_time,
            limit=limit
        )
        
        return {
            "metrics": [
                {
                    "id": m.id,
                    "name": m.name,
                    "category": m.category,
                    "metric_type": m.metric_type,
                    "value": m.value,
                    "count": m.count,
                    "labels": m.labels,
                    "timestamp": m.timestamp,
                    "user_id": m.user_id,
                    "description": m.description
                }
                for m in metrics
            ],
            "total": len(metrics),
            "filters": {
                "name": name,
                "category": category,
                "start_time": start_time,
                "end_time": end_time,
                "limit": limit
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'historique: {str(e)}"
        )


@router.get("/aggregated", summary="Métriques agrégées")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_aggregated_metrics(
    name: str = Query(..., description="Nom de la métrique"),
    aggregation: str = Query("avg", description="Type d'agrégation (avg, sum, count, min, max)"),
    period: str = Query("hour", description="Période d'agrégation (hour, day, week, month)"),
    start_time: Optional[datetime] = Query(None, description="Date de début"),
    end_time: Optional[datetime] = Query(None, description="Date de fin"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère les métriques agrégées par période.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    # Validation des paramètres
    valid_aggregations = ["avg", "sum", "count", "min", "max"]
    valid_periods = ["hour", "day", "week", "month"]
    
    if aggregation not in valid_aggregations:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Agrégation invalide. Valeurs autorisées: {valid_aggregations}"
        )
    
    if period not in valid_periods:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Période invalide. Valeurs autorisées: {valid_periods}"
        )
    
    try:
        metrics_service = MetricsService(db)
        aggregated_data = metrics_service.get_metric_aggregation(
            name=name,
            aggregation=aggregation,
            period=period,
            start_time=start_time,
            end_time=end_time
        )
        
        return {
            "metric_name": name,
            "aggregation": aggregation,
            "period": period,
            "data": aggregated_data,
            "count": len(aggregated_data),
            "start_time": start_time,
            "end_time": end_time
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'agrégation: {str(e)}"
        )


@router.get("/system-health", summary="État de santé du système")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_system_health(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère l'état de santé actuel du système.
    
    Accessible aux administrateurs et conducteurs.
    """
    if current_user.role not in ["admin", "driver"]:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs et conducteurs"
        )
    
    try:
        metrics_service = MetricsService(db)
        health = metrics_service.get_system_health()
        
        if not health:
            return {
                "status": "unknown",
                "message": "Aucune donnée de santé disponible",
                "timestamp": datetime.utcnow()
            }
        
        return {
            "status": health.overall_status,
            "timestamp": health.timestamp,
            "metrics": {
                "cpu_usage": health.cpu_usage,
                "memory_usage": health.memory_usage,
                "disk_usage": health.disk_usage,
                "active_connections": health.active_connections,
                "response_time_avg": health.response_time_avg,
                "error_rate": health.error_rate,
                "active_trips": health.active_trips,
                "active_drivers": health.active_drivers,
                "active_passengers": health.active_passengers
            }
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'état de santé: {str(e)}"
        )


@router.get("/summary", summary="Résumé des métriques")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_metrics_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère un résumé des métriques collectées.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    try:
        metrics_service = MetricsService(db)
        summary = metrics_service.get_metrics_summary()
        
        return {
            "timestamp": datetime.utcnow(),
            "summary": summary
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération du résumé: {str(e)}"
        )


@router.get("/alerts", summary="Alertes actives")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_active_alerts(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère les alertes actives.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    try:
        alerts = db.query(Alert).filter(Alert.is_active == True).all()
        
        return {
            "alerts": [
                {
                    "id": alert.id,
                    "name": alert.name,
                    "metric_name": alert.metric_name,
                    "condition": alert.condition,
                    "threshold": alert.threshold,
                    "is_triggered": alert.is_triggered,
                    "severity": alert.severity,
                    "last_triggered_at": alert.last_triggered_at,
                    "trigger_count": alert.trigger_count,
                    "description": alert.description
                }
                for alert in alerts
            ],
            "total": len(alerts),
            "triggered_count": len([a for a in alerts if a.is_triggered])
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des alertes: {str(e)}"
        )


@router.post("/alerts", summary="Créer une alerte")
@monitor_function(category=MetricCategory.SYSTEM)
async def create_alert(
    name: str = Query(..., description="Nom de l'alerte"),
    metric_name: str = Query(..., description="Nom de la métrique à surveiller"),
    condition: str = Query(..., description="Condition (gt, gte, lt, lte, eq, ne)"),
    threshold: float = Query(..., description="Seuil de déclenchement"),
    severity: str = Query("medium", description="Sévérité (low, medium, high, critical)"),
    description: Optional[str] = Query(None, description="Description de l'alerte"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crée une nouvelle alerte.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    # Validation des paramètres
    valid_conditions = ["gt", "gte", "lt", "lte", "eq", "ne"]
    valid_severities = ["low", "medium", "high", "critical"]
    
    if condition not in valid_conditions:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Condition invalide. Valeurs autorisées: {valid_conditions}"
        )
    
    if severity not in valid_severities:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Sévérité invalide. Valeurs autorisées: {valid_severities}"
        )
    
    try:
        metrics_service = MetricsService(db)
        alert = metrics_service.create_alert(
            name=name,
            metric_name=metric_name,
            condition=condition,
            threshold=threshold,
            severity=severity,
            description=description
        )
        
        return {
            "id": alert.id,
            "name": alert.name,
            "metric_name": alert.metric_name,
            "condition": alert.condition,
            "threshold": alert.threshold,
            "severity": alert.severity,
            "description": alert.description,
            "created_at": alert.created_at,
            "is_active": alert.is_active
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la création de l'alerte: {str(e)}"
        )


@router.get("/dashboard-data", summary="Données pour tableau de bord")
@monitor_function(category=MetricCategory.SYSTEM)
async def get_dashboard_data(
    period: str = Query("day", description="Période (hour, day, week, month)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère les données principales pour le tableau de bord.
    
    Accessible uniquement aux administrateurs.
    """
    if current_user.role != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    try:
        metrics_service = MetricsService(db)
        
        # Définir la période de temps
        end_time = datetime.utcnow()
        if period == "hour":
            start_time = end_time - timedelta(hours=24)
        elif period == "day":
            start_time = end_time - timedelta(days=7)
        elif period == "week":
            start_time = end_time - timedelta(weeks=4)
        else:  # month
            start_time = end_time - timedelta(days=90)
        
        # Métriques principales
        dashboard_data = {
            "period": period,
            "start_time": start_time,
            "end_time": end_time,
            "system_health": None,
            "key_metrics": {},
            "performance_metrics": {},
            "business_metrics": {}
        }
        
        # État de santé système
        health = metrics_service.get_system_health()
        if health:
            dashboard_data["system_health"] = {
                "status": health.overall_status,
                "cpu_usage": health.cpu_usage,
                "memory_usage": health.memory_usage,
                "active_trips": health.active_trips,
                "active_drivers": health.active_drivers,
                "error_rate": health.error_rate
            }
        
        # Métriques clés
        key_metrics = [
            "http_requests_total",
            "http_request_duration_seconds",
            "trips_created",
            "trips_completed",
            "auth_login_success"
        ]
        
        for metric in key_metrics:
            try:
                data = metrics_service.get_metric_aggregation(
                    name=metric,
                    aggregation="sum" if "total" in metric or "created" in metric else "avg",
                    period=period,
                    start_time=start_time,
                    end_time=end_time
                )
                dashboard_data["key_metrics"][metric] = data
            except:
                dashboard_data["key_metrics"][metric] = []
        
        return dashboard_data
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la génération des données du tableau de bord: {str(e)}"
        )

