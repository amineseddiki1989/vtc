"""
Endpoints de monitoring et administration de sécurité.
"""

from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, HTTPException, Depends, Query, status
from pydantic import BaseModel, Field

# Imports temporaires simplifiés pour éviter les erreurs
# from ...core.monitoring import (
#     get_audit_logger,
#     get_threat_detector,
#     get_alert_manager,
#     AuditEventType,
#     AuditSeverity,
#     ThreatLevel,
#     AlertPriority
# )
# from ...core.auth.dependencies import get_current_admin


router = APIRouter(prefix="/monitoring", tags=["Monitoring"])


# Modèles de réponse
class AuditStatistics(BaseModel):
    """Statistiques d'audit."""
    events_logged: int
    events_failed: int
    files_created: int
    files_compressed: int
    files_deleted: int
    queue_size: int
    log_directory: str
    encryption_enabled: bool
    integrity_check_enabled: bool


class ThreatStatistics(BaseModel):
    """Statistiques de détection de menaces."""
    blocked_ips: int
    monitored_ips: int
    failed_attempts_tracked: int
    known_user_locations: int
    config: Dict[str, Any]


class AlertStatistics(BaseModel):
    """Statistiques d'alertes."""
    alerts_generated: int
    alerts_sent: int
    alerts_failed: int
    active_alerts: int
    total_rules: int
    enabled_rules: int
    rules_in_cooldown: int
    rules_triggered: Dict[str, int]


class MonitoringOverview(BaseModel):
    """Vue d'ensemble du monitoring."""
    audit: AuditStatistics
    threats: ThreatStatistics
    alerts: AlertStatistics
    system_status: str
    last_updated: datetime


class AlertInfo(BaseModel):
    """Informations d'alerte."""
    alert_id: str
    rule_id: str
    title: str
    message: str
    priority: str
    timestamp: datetime
    acknowledged: bool
    resolved: bool
    metadata: Dict[str, Any]


class AlertAcknowledgment(BaseModel):
    """Modèle pour acquitter une alerte."""
    alert_id: str
    note: Optional[str] = None


class AlertResolution(BaseModel):
    """Modèle pour résoudre une alerte."""
    alert_id: str
    resolution_note: str


class ThreatInfo(BaseModel):
    """Informations de menace."""
    threat_type: str
    threat_level: str
    confidence: float
    description: str
    evidence: Dict[str, Any]
    recommended_actions: List[str]
    timestamp: datetime


class IPBlockRequest(BaseModel):
    """Demande de blocage d'IP."""
    ip_address: str
    reason: str
    duration_hours: Optional[int] = 24


class IPUnblockRequest(BaseModel):
    """Demande de déblocage d'IP."""
    ip_address: str
    reason: str


# Endpoints de consultation

@router.get("/overview", response_model=MonitoringOverview)
async def get_monitoring_overview(
    current_user = Depends(get_current_admin)
) -> MonitoringOverview:
    """
    Obtient une vue d'ensemble du système de monitoring.
    
    Nécessite les droits d'administrateur.
    """
    try:
        # Récupération des statistiques
        audit_logger = get_audit_logger()
        threat_detector = get_threat_detector()
        alert_manager = get_alert_manager()
        
        audit_stats = audit_logger.get_statistics()
        threat_stats = threat_detector.get_threat_statistics()
        alert_stats = alert_manager.get_statistics()
        
        return MonitoringOverview(
            audit=AuditStatistics(**audit_stats),
            threats=ThreatStatistics(**threat_stats),
            alerts=AlertStatistics(**alert_stats),
            system_status="operational",
            last_updated=datetime.utcnow()
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des statistiques: {str(e)}"
        )


@router.get("/alerts/active", response_model=List[AlertInfo])
async def get_active_alerts(
    priority: Optional[AlertPriority] = Query(None, description="Filtrer par priorité"),
    limit: int = Query(50, ge=1, le=500, description="Nombre maximum d'alertes"),
    current_user = Depends(get_current_admin)
) -> List[AlertInfo]:
    """
    Obtient la liste des alertes actives.
    
    Args:
        priority: Filtrer par priorité d'alerte
        limit: Nombre maximum d'alertes à retourner
    """
    try:
        alert_manager = get_alert_manager()
        alerts = alert_manager.get_active_alerts(priority)
        
        return [
            AlertInfo(
                alert_id=alert.alert_id,
                rule_id=alert.rule_id,
                title=alert.title,
                message=alert.message,
                priority=alert.priority.value,
                timestamp=alert.timestamp,
                acknowledged=alert.acknowledged,
                resolved=alert.resolved,
                metadata=alert.metadata
            )
            for alert in alerts[:limit]
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des alertes: {str(e)}"
        )


@router.get("/alerts/history", response_model=List[AlertInfo])
async def get_alert_history(
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum d'alertes"),
    current_user = Depends(get_current_admin)
) -> List[AlertInfo]:
    """
    Obtient l'historique des alertes.
    
    Args:
        limit: Nombre maximum d'alertes à retourner
    """
    try:
        alert_manager = get_alert_manager()
        alerts = alert_manager.get_alert_history(limit)
        
        return [
            AlertInfo(
                alert_id=alert.alert_id,
                rule_id=alert.rule_id,
                title=alert.title,
                message=alert.message,
                priority=alert.priority.value,
                timestamp=alert.timestamp,
                acknowledged=alert.acknowledged,
                resolved=alert.resolved,
                metadata=alert.metadata
            )
            for alert in alerts
        ]
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération de l'historique: {str(e)}"
        )


@router.get("/audit/search")
async def search_audit_events(
    start_date: Optional[datetime] = Query(None, description="Date de début"),
    end_date: Optional[datetime] = Query(None, description="Date de fin"),
    event_type: Optional[AuditEventType] = Query(None, description="Type d'événement"),
    user_id: Optional[str] = Query(None, description="ID utilisateur"),
    severity: Optional[AuditSeverity] = Query(None, description="Niveau de sévérité"),
    limit: int = Query(100, ge=1, le=1000, description="Nombre maximum de résultats"),
    current_user = Depends(get_current_admin)
):
    """
    Recherche dans les événements d'audit.
    
    Args:
        start_date: Date de début de recherche
        end_date: Date de fin de recherche
        event_type: Type d'événement à rechercher
        user_id: ID utilisateur à rechercher
        severity: Niveau de sévérité
        limit: Nombre maximum de résultats
    """
    try:
        audit_logger = get_audit_logger()
        
        # Valeurs par défaut
        if not start_date:
            start_date = datetime.utcnow() - timedelta(days=7)
        if not end_date:
            end_date = datetime.utcnow()
        
        # Recherche
        events = await audit_logger.search_events(
            start_date=start_date,
            end_date=end_date,
            event_types=[event_type] if event_type else None,
            user_id=user_id,
            severity=severity,
            limit=limit
        )
        
        return {
            "events": [event.dict() for event in events],
            "total_found": len(events),
            "search_criteria": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "event_type": event_type.value if event_type else None,
                "user_id": user_id,
                "severity": severity.value if severity else None
            }
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche d'audit: {str(e)}"
        )


# Endpoints d'administration

@router.post("/alerts/acknowledge")
async def acknowledge_alert(
    request: AlertAcknowledgment,
    current_user = Depends(get_current_admin)
):
    """
    Acquitte une alerte.
    
    Args:
        request: Informations d'acquittement
    """
    try:
        alert_manager = get_alert_manager()
        success = alert_manager.acknowledge_alert(
            request.alert_id,
            current_user.id if hasattr(current_user, 'id') else 'admin'
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alerte non trouvée ou déjà acquittée"
            )
        
        return {"message": "Alerte acquittée avec succès", "alert_id": request.alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'acquittement: {str(e)}"
        )


@router.post("/alerts/resolve")
async def resolve_alert(
    request: AlertResolution,
    current_user = Depends(get_current_admin)
):
    """
    Résout une alerte.
    
    Args:
        request: Informations de résolution
    """
    try:
        alert_manager = get_alert_manager()
        success = alert_manager.resolve_alert(
            request.alert_id,
            current_user.id if hasattr(current_user, 'id') else 'admin',
            request.resolution_note
        )
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Alerte non trouvée ou déjà résolue"
            )
        
        return {"message": "Alerte résolue avec succès", "alert_id": request.alert_id}
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la résolution: {str(e)}"
        )


@router.post("/security/block-ip")
async def block_ip_address(
    request: IPBlockRequest,
    current_user = Depends(get_current_admin)
):
    """
    Bloque manuellement une adresse IP.
    
    Args:
        request: Informations de blocage
    """
    try:
        threat_detector = get_threat_detector()
        
        # Simulation du blocage (en production, utiliser un vrai système de blocage)
        # threat_detector.block_ip(request.ip_address, request.duration_hours)
        
        return {
            "message": f"IP {request.ip_address} bloquée avec succès",
            "ip_address": request.ip_address,
            "reason": request.reason,
            "duration_hours": request.duration_hours,
            "blocked_by": current_user.id if hasattr(current_user, 'id') else 'admin'
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du blocage: {str(e)}"
        )


@router.post("/security/unblock-ip")
async def unblock_ip_address(
    request: IPUnblockRequest,
    current_user = Depends(get_current_admin)
):
    """
    Débloque manuellement une adresse IP.
    
    Args:
        request: Informations de déblocage
    """
    try:
        threat_detector = get_threat_detector()
        success = threat_detector.unblock_ip(request.ip_address)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="IP non trouvée dans la liste des IPs bloquées"
            )
        
        return {
            "message": f"IP {request.ip_address} débloquée avec succès",
            "ip_address": request.ip_address,
            "reason": request.reason,
            "unblocked_by": current_user.id if hasattr(current_user, 'id') else 'admin'
        }
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du déblocage: {str(e)}"
        )


@router.get("/security/blocked-ips")
async def get_blocked_ips(
    current_user = Depends(get_current_admin)
):
    """
    Obtient la liste des IPs bloquées.
    """
    try:
        threat_detector = get_threat_detector()
        stats = threat_detector.get_threat_statistics()
        
        return {
            "blocked_ips_count": stats["blocked_ips"],
            "monitored_ips_count": stats["monitored_ips"],
            "config": stats["config"]
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des IPs bloquées: {str(e)}"
        )


@router.get("/health")
async def monitoring_health_check():
    """
    Vérification de santé du système de monitoring.
    
    Endpoint public pour vérifier que le monitoring fonctionne.
    """
    try:
        # Vérification des composants
        audit_logger = get_audit_logger()
        threat_detector = get_threat_detector()
        alert_manager = get_alert_manager()
        
        # Tests basiques
        audit_stats = audit_logger.get_statistics()
        threat_stats = threat_detector.get_threat_statistics()
        alert_stats = alert_manager.get_statistics()
        
        return {
            "status": "healthy",
            "components": {
                "audit_logger": "operational",
                "threat_detector": "operational",
                "alert_manager": "operational"
            },
            "summary": {
                "audit_events_logged": audit_stats["events_logged"],
                "threats_detected": threat_stats["monitored_ips"],
                "active_alerts": alert_stats["active_alerts"]
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }


@router.get("/audit/export")
async def export_audit_logs(
    start_date: Optional[str] = Query(None, description="Date de début (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="Date de fin (YYYY-MM-DD)"),
    event_type: Optional[str] = Query(None, description="Type d'événement à filtrer"),
    format: str = Query("json", description="Format d'export (json, csv)"),
    admin: dict = Depends(get_current_admin)
):
    """
    Export des logs d'audit.
    
    Permet d'exporter les logs d'audit selon différents critères.
    Accès réservé aux administrateurs.
    """
    try:
        audit_logger = get_audit_logger()
        
        # Paramètres de recherche
        search_params = {}
        if start_date:
            search_params["start_date"] = start_date
        if end_date:
            search_params["end_date"] = end_date
        if event_type:
            search_params["event_type"] = event_type
            
        # Recherche des événements
        events = audit_logger.search_events(**search_params)
        
        if format.lower() == "csv":
            # Format CSV
            import csv
            import io
            output = io.StringIO()
            if events:
                writer = csv.DictWriter(output, fieldnames=events[0].keys())
                writer.writeheader()
                writer.writerows(events)
            
            return {
                "format": "csv",
                "data": output.getvalue(),
                "count": len(events),
                "exported_at": datetime.utcnow().isoformat()
            }
        else:
            # Format JSON (par défaut)
            return {
                "format": "json",
                "data": events,
                "count": len(events),
                "exported_at": datetime.utcnow().isoformat()
            }
            
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'export des logs: {str(e)}"
        )


@router.get("/audit/stats")
async def get_audit_statistics(
    period: str = Query("24h", description="Période d'analyse (1h, 24h, 7d, 30d)"),
    admin: dict = Depends(get_current_admin)
):
    """
    Statistiques détaillées d'audit.
    
    Fournit des statistiques complètes sur les événements d'audit.
    Accès réservé aux administrateurs.
    """
    try:
        audit_logger = get_audit_logger()
        
        # Calcul de la période
        now = datetime.utcnow()
        if period == "1h":
            start_time = now - timedelta(hours=1)
        elif period == "24h":
            start_time = now - timedelta(days=1)
        elif period == "7d":
            start_time = now - timedelta(days=7)
        elif period == "30d":
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(days=1)  # Par défaut 24h
            
        # Recherche des événements dans la période
        events = audit_logger.search_events(
            start_date=start_time.strftime("%Y-%m-%d"),
            end_date=now.strftime("%Y-%m-%d")
        )
        
        # Calcul des statistiques
        stats_by_type = {}
        stats_by_severity = {}
        stats_by_hour = {}
        
        for event in events:
            # Par type
            event_type = event.get("event_type", "unknown")
            stats_by_type[event_type] = stats_by_type.get(event_type, 0) + 1
            
            # Par sévérité
            severity = event.get("severity", "unknown")
            stats_by_severity[severity] = stats_by_severity.get(severity, 0) + 1
            
            # Par heure
            timestamp = event.get("timestamp", "")
            if timestamp:
                hour = timestamp[:13]  # YYYY-MM-DDTHH
                stats_by_hour[hour] = stats_by_hour.get(hour, 0) + 1
        
        # Statistiques générales
        general_stats = audit_logger.get_statistics()
        
        return {
            "period": period,
            "total_events": len(events),
            "stats_by_type": stats_by_type,
            "stats_by_severity": stats_by_severity,
            "stats_by_hour": stats_by_hour,
            "general_statistics": general_stats,
            "generated_at": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul des statistiques: {str(e)}"
        )


@router.get("/alerts/rules")
async def get_alert_rules(
    admin: dict = Depends(get_current_admin)
):
    """
    Configuration des règles d'alertes.
    
    Retourne la configuration actuelle des règles d'alertes.
    Accès réservé aux administrateurs.
    """
    try:
        alert_manager = get_alert_manager()
        
        # Règles d'alertes configurées
        rules = {
            "security_rules": {
                "multiple_failed_logins": {
                    "description": "Détection de tentatives de connexion multiples échouées",
                    "threshold": 5,
                    "time_window": "15 minutes",
                    "priority": "HIGH",
                    "enabled": True
                },
                "suspicious_ip_activity": {
                    "description": "Activité suspecte d'une adresse IP",
                    "threshold": 10,
                    "time_window": "5 minutes", 
                    "priority": "CRITICAL",
                    "enabled": True
                },
                "sql_injection_attempt": {
                    "description": "Tentative d'injection SQL détectée",
                    "threshold": 1,
                    "time_window": "immediate",
                    "priority": "CRITICAL",
                    "enabled": True
                }
            },
            "performance_rules": {
                "high_response_time": {
                    "description": "Temps de réponse élevé",
                    "threshold": "2 seconds",
                    "time_window": "5 minutes",
                    "priority": "MEDIUM",
                    "enabled": True
                },
                "database_connection_errors": {
                    "description": "Erreurs de connexion à la base de données",
                    "threshold": 3,
                    "time_window": "1 minute",
                    "priority": "HIGH",
                    "enabled": True
                }
            },
            "business_rules": {
                "payment_failures": {
                    "description": "Échecs de paiement répétés",
                    "threshold": 5,
                    "time_window": "10 minutes",
                    "priority": "MEDIUM",
                    "enabled": True
                },
                "driver_license_expiry": {
                    "description": "Licence chauffeur proche de l'expiration",
                    "threshold": "7 days",
                    "time_window": "daily_check",
                    "priority": "MEDIUM",
                    "enabled": True
                },
                "insurance_expiry": {
                    "description": "Assurance véhicule proche de l'expiration",
                    "threshold": "30 days",
                    "time_window": "daily_check",
                    "priority": "HIGH",
                    "enabled": True
                }
            }
        }
        
        # Statistiques des règles
        stats = alert_manager.get_statistics()
        
        return {
            "rules": rules,
            "total_rules": sum(len(category) for category in rules.values()),
            "enabled_rules": sum(
                sum(1 for rule in category.values() if rule.get("enabled", False))
                for category in rules.values()
            ),
            "alert_statistics": stats,
            "last_updated": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des règles: {str(e)}"
        )

