"""
API de monitoring avancé pour l'application VTC.
"""

from fastapi import APIRouter, HTTPException, status, Depends, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
import logging
import asyncio

from ...core.monitoring.advanced_metrics import (
    business_metrics, performance_monitor, MetricType, AlertLevel
)

logger = logging.getLogger(__name__)

router = APIRouter()


class MetricRequest(BaseModel):
    """Modèle pour enregistrer une métrique."""
    name: str = Field(..., description="Nom de la métrique")
    value: float = Field(..., description="Valeur de la métrique")
    metric_type: str = Field(..., description="Type de métrique (counter, gauge, histogram, timer, rate)")
    tags: Optional[Dict[str, str]] = Field(None, description="Tags associés")


class AlertRuleRequest(BaseModel):
    """Modèle pour créer une règle d'alerte."""
    metric_name: str = Field(..., description="Nom de la métrique à surveiller")
    threshold: float = Field(..., description="Seuil de déclenchement")
    condition: str = Field(default="greater_than", description="Condition (greater_than, less_than, equals)")
    level: str = Field(default="warning", description="Niveau d'alerte (info, warning, error, critical)")
    message: Optional[str] = Field(None, description="Message d'alerte personnalisé")


class BusinessEventRequest(BaseModel):
    """Modèle pour enregistrer un événement business."""
    event_type: str = Field(..., description="Type d'événement")
    trip_id: Optional[str] = Field(None, description="ID du trajet")
    user_id: Optional[str] = Field(None, description="ID de l'utilisateur")
    value: Optional[float] = Field(None, description="Valeur associée")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Métadonnées additionnelles")


@router.get("/monitoring/dashboard")
async def get_monitoring_dashboard():
    """Retourne le tableau de bord de monitoring complet."""
    try:
        business_dashboard = business_metrics.get_business_dashboard()
        performance_report = performance_monitor.get_performance_report()
        
        return {
            "timestamp": datetime.now().isoformat(),
            "business_metrics": business_dashboard,
            "performance_metrics": performance_report,
            "system_health": {
                "status": "healthy",
                "uptime_hours": 24,  # Simulation
                "version": "3.0.0",
                "environment": "production"
            }
        }
    except Exception as e:
        logger.error(f"Erreur lors de la génération du dashboard: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la génération du dashboard"
        )


@router.get("/monitoring/metrics/{metric_name}")
async def get_metric_stats(
    metric_name: str,
    window_seconds: int = 300
):
    """Retourne les statistiques d'une métrique spécifique."""
    try:
        stats = business_metrics.collector.get_metric_stats(metric_name, window_seconds)
        
        if not stats:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Métrique '{metric_name}' non trouvée"
            )
        
        return {
            "metric_name": metric_name,
            "window_seconds": window_seconds,
            "statistics": stats,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des stats de métrique: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


@router.post("/monitoring/metrics")
async def record_custom_metric(request: MetricRequest):
    """Enregistre une métrique personnalisée."""
    try:
        metric_type = MetricType(request.metric_type)
        business_metrics.collector.record_metric(
            request.name,
            request.value,
            metric_type,
            request.tags
        )
        
        return {
            "message": "Métrique enregistrée avec succès",
            "metric_name": request.name,
            "value": request.value,
            "timestamp": datetime.now().isoformat()
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Type de métrique invalide: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement de métrique: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement de la métrique"
        )


@router.get("/monitoring/alerts")
async def get_active_alerts():
    """Retourne les alertes actives."""
    try:
        alerts = business_metrics.collector.get_active_alerts()
        
        return {
            "active_alerts_count": len(alerts),
            "alerts": [
                {
                    "id": alert.id,
                    "level": alert.level.value,
                    "message": alert.message,
                    "metric_name": alert.metric_name,
                    "threshold": alert.threshold,
                    "current_value": alert.current_value,
                    "timestamp": alert.timestamp.isoformat(),
                    "resolved": alert.resolved
                }
                for alert in alerts
            ],
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des alertes: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des alertes"
        )


@router.post("/monitoring/alerts/rules")
async def create_alert_rule(request: AlertRuleRequest):
    """Crée une nouvelle règle d'alerte."""
    try:
        business_metrics.collector.add_alert_rule(
            request.metric_name,
            request.threshold,
            request.condition,
            request.level,
            request.message
        )
        
        return {
            "message": "Règle d'alerte créée avec succès",
            "metric_name": request.metric_name,
            "threshold": request.threshold,
            "condition": request.condition,
            "level": request.level,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors de la création de règle d'alerte: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de la règle d'alerte"
        )


@router.post("/monitoring/alerts/{alert_id}/resolve")
async def resolve_alert(alert_id: str):
    """Résout une alerte."""
    try:
        business_metrics.collector.resolve_alert(alert_id)
        
        return {
            "message": "Alerte résolue avec succès",
            "alert_id": alert_id,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors de la résolution d'alerte: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la résolution de l'alerte"
        )


@router.post("/monitoring/events/business")
async def record_business_event(request: BusinessEventRequest):
    """Enregistre un événement business."""
    try:
        if request.event_type == "trip_created":
            business_metrics.record_trip_created(
                request.trip_id or "unknown",
                request.value or 0.0
            )
        elif request.event_type == "trip_completed":
            metadata = request.metadata or {}
            business_metrics.record_trip_completed(
                request.trip_id or "unknown",
                request.value or 0.0,
                metadata.get("duration_minutes", 0),
                metadata.get("distance_km", 0.0),
                metadata.get("rating", 5.0)
            )
        elif request.event_type == "trip_cancelled":
            metadata = request.metadata or {}
            business_metrics.record_trip_cancelled(
                request.trip_id or "unknown",
                metadata.get("reason", "unknown")
            )
        elif request.event_type == "driver_activity":
            metadata = request.metadata or {}
            business_metrics.record_driver_activity(
                request.user_id or "unknown",
                metadata.get("status", "unknown"),
                metadata.get("rating")
            )
        elif request.event_type == "customer_activity":
            metadata = request.metadata or {}
            business_metrics.record_customer_activity(
                request.user_id or "unknown",
                metadata.get("action", "unknown"),
                metadata.get("satisfaction")
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Type d'événement non supporté: {request.event_type}"
            )
        
        return {
            "message": "Événement business enregistré avec succès",
            "event_type": request.event_type,
            "timestamp": datetime.now().isoformat()
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'enregistrement d'événement business: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'enregistrement de l'événement"
        )


@router.get("/monitoring/performance")
async def get_performance_metrics():
    """Retourne les métriques de performance détaillées."""
    try:
        performance_report = performance_monitor.get_performance_report()
        
        # Ajouter des métriques supplémentaires
        additional_metrics = {
            "api_metrics": {
                "total_requests": business_metrics.collector.get_metric_stats("api_calls_total", 3600),
                "error_requests": business_metrics.collector.get_metric_stats("api_errors_total", 3600),
                "response_times": business_metrics.collector.get_metric_stats("api_response_time", 3600)
            },
            "fiscal_metrics": {
                "total_calculations": business_metrics.collector.get_metric_stats("fiscal_calculations_total", 3600),
                "calculation_times": business_metrics.collector.get_metric_stats("fiscal_calculation_time", 3600),
                "cache_hits": business_metrics.collector.get_metric_stats("fiscal_cache_hits", 3600),
                "cache_misses": business_metrics.collector.get_metric_stats("fiscal_cache_misses", 3600)
            }
        }
        
        return {
            **performance_report,
            **additional_metrics,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des métriques de performance: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des métriques de performance"
        )


@router.get("/monitoring/health")
async def get_system_health():
    """Retourne l'état de santé du système de monitoring."""
    try:
        active_alerts = business_metrics.collector.get_active_alerts()
        critical_alerts = [a for a in active_alerts if a.level == AlertLevel.CRITICAL]
        
        health_status = "healthy"
        if critical_alerts:
            health_status = "critical"
        elif len(active_alerts) > 10:
            health_status = "degraded"
        elif len(active_alerts) > 5:
            health_status = "warning"
        
        return {
            "status": health_status,
            "monitoring_active": performance_monitor.monitoring_active,
            "total_metrics": len(business_metrics.collector.metrics),
            "active_alerts": len(active_alerts),
            "critical_alerts": len(critical_alerts),
            "last_update": datetime.now().isoformat(),
            "version": "3.0.0"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la vérification de santé: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la vérification de santé"
        )


@router.post("/monitoring/start")
async def start_monitoring(background_tasks: BackgroundTasks):
    """Démarre le monitoring de performance."""
    try:
        if not performance_monitor.monitoring_active:
            background_tasks.add_task(performance_monitor.start_monitoring)
            return {
                "message": "Monitoring de performance démarré",
                "timestamp": datetime.now().isoformat()
            }
        else:
            return {
                "message": "Monitoring déjà actif",
                "timestamp": datetime.now().isoformat()
            }
    except Exception as e:
        logger.error(f"Erreur lors du démarrage du monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du démarrage du monitoring"
        )


@router.post("/monitoring/stop")
async def stop_monitoring():
    """Arrête le monitoring de performance."""
    try:
        performance_monitor.stop_monitoring()
        return {
            "message": "Monitoring de performance arrêté",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors de l'arrêt du monitoring: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'arrêt du monitoring"
        )

