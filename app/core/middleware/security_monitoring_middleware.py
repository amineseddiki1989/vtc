"""
Middleware de monitoring de sécurité pour l'application VTC.
"""

import time
import json
import asyncio
from typing import Callable, Optional
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
import logging

from ..monitoring.audit import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    get_audit_logger,
    create_auth_event,
    create_security_event
)
from ..monitoring.security.threat_detector import (
    SecurityContext,
    get_threat_detector,
    ThreatLevel
)
from ..monitoring.alerts import (
    get_alert_manager,
    send_alert_for_event,
    send_alert_for_threat
)


class SecurityMonitoringMiddleware(BaseHTTPMiddleware):
    """Middleware de monitoring de sécurité en temps réel."""
    
    def __init__(
        self,
        app: ASGIApp,
        enable_audit: bool = True,
        enable_threat_detection: bool = True,
        enable_alerts: bool = True,
        block_threats: bool = True,
        log_all_requests: bool = False
    ):
        """
        Initialise le middleware de monitoring de sécurité.
        
        Args:
            app: Application ASGI
            enable_audit: Activer l'audit des requêtes
            enable_threat_detection: Activer la détection de menaces
            enable_alerts: Activer les alertes automatiques
            block_threats: Bloquer automatiquement les menaces critiques
            log_all_requests: Logger toutes les requêtes (debug)
        """
        super().__init__(app)
        
        self.enable_audit = enable_audit
        self.enable_threat_detection = enable_threat_detection
        self.enable_alerts = enable_alerts
        self.block_threats = block_threats
        self.log_all_requests = log_all_requests
        
        # Composants de monitoring
        self.audit_logger = get_audit_logger() if enable_audit else None
        self.threat_detector = get_threat_detector() if enable_threat_detection else None
        self.alert_manager = get_alert_manager() if enable_alerts else None
        
        # Logger
        self.logger = logging.getLogger("vtc_security_middleware")
        
        # Statistiques
        self.stats = {
            "requests_processed": 0,
            "threats_detected": 0,
            "threats_blocked": 0,
            "alerts_sent": 0,
            "audit_events_logged": 0
        }
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Traite une requête avec monitoring de sécurité.
        
        Args:
            request: Requête HTTP
            call_next: Fonction suivante dans la chaîne
            
        Returns:
            Réponse HTTP
        """
        start_time = time.time()
        
        # Extraction du contexte de sécurité
        security_context = await self._extract_security_context(request)
        
        # Détection de menaces
        threats = []
        if self.enable_threat_detection:
            threats = await self._detect_threats(security_context)
        
        # Blocage des menaces critiques
        if self.block_threats and threats:
            critical_threats = [t for t in threats if t.threat_level in [ThreatLevel.HIGH, ThreatLevel.CRITICAL]]
            if critical_threats:
                return await self._block_request(request, critical_threats)
        
        # Traitement de la requête
        try:
            response = await call_next(request)
            success = True
            error_message = None
        except Exception as e:
            # Gestion des erreurs
            self.logger.error(f"Erreur lors du traitement de la requête: {e}")
            response = JSONResponse(
                status_code=500,
                content={"error": "Erreur interne du serveur"}
            )
            success = False
            error_message = str(e)
        
        # Calcul du temps de traitement
        processing_time = time.time() - start_time
        
        # Audit de la requête
        if self.enable_audit:
            await self._audit_request(
                security_context, 
                response.status_code, 
                processing_time,
                success,
                error_message
            )
        
        # Gestion des alertes pour les menaces
        if self.enable_alerts and threats:
            await self._handle_threat_alerts(threats)
        
        # Mise à jour des statistiques
        self._update_stats(threats, success)
        
        # Ajout d'en-têtes de sécurité
        self._add_security_headers(response)
        
        return response
    
    async def _extract_security_context(self, request: Request) -> SecurityContext:
        """Extrait le contexte de sécurité d'une requête."""
        # Extraction de l'IP client
        client_ip = self._get_client_ip(request)
        
        # Extraction de l'utilisateur (si authentifié)
        user_id = None
        if hasattr(request.state, 'user') and request.state.user:
            user_id = getattr(request.state.user, 'id', None)
        
        # Extraction du User-Agent
        user_agent = request.headers.get("user-agent", "")
        
        # Extraction du payload
        payload = None
        if request.method in ["POST", "PUT", "PATCH"]:
            try:
                # Lecture du body (attention: ne peut être lu qu'une fois)
                body = await request.body()
                if body:
                    payload = body.decode('utf-8', errors='ignore')
            except Exception:
                payload = None
        
        # Construction du contexte
        context = SecurityContext(
            ip_address=client_ip,
            user_id=user_id,
            user_agent=user_agent,
            endpoint=str(request.url.path),
            method=request.method,
            payload=payload,
            headers=dict(request.headers)
        )
        
        return context
    
    def _get_client_ip(self, request: Request) -> str:
        """Obtient l'adresse IP réelle du client."""
        # Vérification des en-têtes de proxy
        forwarded_for = request.headers.get("x-forwarded-for")
        if forwarded_for:
            # Prendre la première IP (client original)
            return forwarded_for.split(",")[0].strip()
        
        real_ip = request.headers.get("x-real-ip")
        if real_ip:
            return real_ip
        
        # IP directe
        if request.client:
            return request.client.host
        
        return "unknown"
    
    async def _detect_threats(self, context: SecurityContext) -> list:
        """Détecte les menaces dans le contexte de sécurité."""
        if not self.threat_detector:
            return []
        
        try:
            threats = await self.threat_detector.analyze_request(context)
            if threats:
                self.logger.warning(f"Menaces détectées: {len(threats)} depuis {context.ip_address}")
            return threats
        except Exception as e:
            self.logger.error(f"Erreur lors de la détection de menaces: {e}")
            return []
    
    async def _block_request(self, request: Request, threats: list) -> Response:
        """Bloque une requête en raison de menaces détectées."""
        self.stats["threats_blocked"] += 1
        
        # Log de sécurité
        self.logger.critical(f"Requête bloquée - Menaces critiques détectées: {[t.threat_type.value for t in threats]}")
        
        # Audit de l'événement de blocage
        if self.enable_audit:
            event = create_security_event(
                AuditEventType.SECURITY_THREAT_DETECTED,
                self._get_client_ip(request),
                AuditSeverity.CRITICAL,
                {
                    "threats": [t.threat_type.value for t in threats],
                    "action": "request_blocked",
                    "endpoint": str(request.url.path),
                    "method": request.method
                }
            )
            await self.audit_logger.log_event(event)
        
        # Réponse de blocage
        return JSONResponse(
            status_code=403,
            content={
                "error": "Accès refusé",
                "message": "Activité suspecte détectée",
                "incident_id": f"SEC_{int(time.time())}"
            }
        )
    
    async def _audit_request(
        self,
        context: SecurityContext,
        status_code: int,
        processing_time: float,
        success: bool,
        error_message: Optional[str] = None
    ):
        """Audite une requête."""
        if not self.audit_logger:
            return
        
        try:
            # Détermination du type d'événement
            if context.endpoint.startswith("/auth"):
                event_type = AuditEventType.AUTH_LOGIN_SUCCESS if success else AuditEventType.AUTH_LOGIN_FAILED
            elif context.endpoint.startswith("/api"):
                event_type = AuditEventType.API_CALL if success else AuditEventType.API_ERROR
            else:
                event_type = AuditEventType.API_CALL
            
            # Détermination de la sévérité
            if not success:
                severity = AuditSeverity.WARNING
            elif status_code >= 400:
                severity = AuditSeverity.WARNING
            else:
                severity = AuditSeverity.INFO
            
            # Création de l'événement d'audit
            event = AuditEvent(
                event_type=event_type,
                severity=severity,
                user_id=context.user_id,
                ip_address=context.ip_address,
                user_agent=context.user_agent,
                action=f"{context.method} {context.endpoint}",
                resource=context.endpoint,
                method=context.method,
                success=success,
                error_message=error_message,
                details={
                    "status_code": status_code,
                    "processing_time_ms": round(processing_time * 1000, 2),
                    "payload_size": len(context.payload) if context.payload else 0,
                    "headers_count": len(context.headers)
                }
            )
            
            # Enregistrement de l'événement
            await self.audit_logger.log_event(event)
            self.stats["audit_events_logged"] += 1
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'audit: {e}")
    
    async def _handle_threat_alerts(self, threats: list):
        """Gère les alertes pour les menaces détectées."""
        if not self.alert_manager:
            return
        
        try:
            for threat in threats:
                alerts = await send_alert_for_threat(threat)
                self.stats["alerts_sent"] += len(alerts)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi d'alertes: {e}")
    
    def _update_stats(self, threats: list, success: bool):
        """Met à jour les statistiques."""
        self.stats["requests_processed"] += 1
        if threats:
            self.stats["threats_detected"] += len(threats)
    
    def _add_security_headers(self, response: Response):
        """Ajoute des en-têtes de sécurité à la réponse."""
        # En-têtes de sécurité standard
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["X-XSS-Protection"] = "1; mode=block"
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        
        # CSP pour les API
        response.headers["Content-Security-Policy"] = "default-src 'none'; frame-ancestors 'none';"
        
        # En-tête personnalisé pour identifier le monitoring
        response.headers["X-VTC-Security-Monitoring"] = "active"
    
    def get_statistics(self) -> dict:
        """Retourne les statistiques du middleware."""
        return {
            **self.stats,
            "monitoring_enabled": {
                "audit": self.enable_audit,
                "threat_detection": self.enable_threat_detection,
                "alerts": self.enable_alerts,
                "blocking": self.block_threats
            }
        }
    
    def reset_statistics(self):
        """Remet à zéro les statistiques."""
        for key in self.stats:
            self.stats[key] = 0


# Fonction utilitaire pour créer le middleware
def create_security_monitoring_middleware(
    enable_audit: bool = True,
    enable_threat_detection: bool = True,
    enable_alerts: bool = True,
    block_threats: bool = True,
    log_all_requests: bool = False
) -> type:
    """
    Crée une classe de middleware avec la configuration spécifiée.
    
    Args:
        enable_audit: Activer l'audit
        enable_threat_detection: Activer la détection de menaces
        enable_alerts: Activer les alertes
        block_threats: Bloquer les menaces automatiquement
        log_all_requests: Logger toutes les requêtes
        
    Returns:
        Classe de middleware configurée
    """
    class ConfiguredSecurityMonitoringMiddleware(SecurityMonitoringMiddleware):
        def __init__(self, app: ASGIApp):
            super().__init__(
                app,
                enable_audit=enable_audit,
                enable_threat_detection=enable_threat_detection,
                enable_alerts=enable_alerts,
                block_threats=block_threats,
                log_all_requests=log_all_requests
            )
    
    return ConfiguredSecurityMonitoringMiddleware

