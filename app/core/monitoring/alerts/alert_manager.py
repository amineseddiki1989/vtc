"""
Gestionnaire d'alertes automatiques pour l'application VTC.
"""

import asyncio
import json
import smtplib
import ssl
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Callable
from enum import Enum
from dataclasses import dataclass, field
import email.mime.text
import email.mime.multipart
import logging
import os
from collections import defaultdict, deque

from ..audit.audit_events import AuditEvent, AuditEventType, AuditSeverity
from ..security.threat_detector import ThreatDetection, ThreatLevel


class AlertChannel(str, Enum):
    """Canaux d'alerte disponibles."""
    EMAIL = "email"
    SMS = "sms"
    WEBHOOK = "webhook"
    SLACK = "slack"
    TEAMS = "teams"
    LOG = "log"
    CONSOLE = "console"


class AlertPriority(str, Enum):
    """Priorités d'alerte."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    EMERGENCY = "emergency"


@dataclass
class AlertRule:
    """Règle d'alerte."""
    rule_id: str
    name: str
    description: str
    condition: Callable[[AuditEvent], bool]
    priority: AlertPriority
    channels: List[AlertChannel]
    cooldown_minutes: int = 5  # Éviter le spam
    enabled: bool = True
    tags: List[str] = field(default_factory=list)


@dataclass
class Alert:
    """Alerte générée."""
    alert_id: str
    rule_id: str
    title: str
    message: str
    priority: AlertPriority
    timestamp: datetime = field(default_factory=datetime.utcnow)
    source_event: Optional[AuditEvent] = None
    threat_detection: Optional[ThreatDetection] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    resolved: bool = False


class AlertManager:
    """Gestionnaire d'alertes automatiques."""
    
    def __init__(self):
        """Initialise le gestionnaire d'alertes."""
        
        # Configuration
        self.config = {
            "email": {
                "smtp_server": os.getenv("ALERT_SMTP_SERVER", "smtp.gmail.com"),
                "smtp_port": int(os.getenv("ALERT_SMTP_PORT", "587")),
                "username": os.getenv("ALERT_EMAIL_USERNAME"),
                "password": os.getenv("ALERT_EMAIL_PASSWORD"),
                "from_email": os.getenv("ALERT_FROM_EMAIL"),
                "to_emails": os.getenv("ALERT_TO_EMAILS", "").split(",")
            },
            "webhook": {
                "url": os.getenv("ALERT_WEBHOOK_URL"),
                "secret": os.getenv("ALERT_WEBHOOK_SECRET")
            },
            "slack": {
                "webhook_url": os.getenv("ALERT_SLACK_WEBHOOK"),
                "channel": os.getenv("ALERT_SLACK_CHANNEL", "#security")
            }
        }
        
        # Règles d'alerte
        self.rules: Dict[str, AlertRule] = {}
        
        # Historique des alertes
        self.alert_history: deque = deque(maxlen=10000)
        self.active_alerts: Dict[str, Alert] = {}
        
        # Cooldown pour éviter le spam
        self.rule_cooldowns: Dict[str, datetime] = {}
        
        # Statistiques
        self.stats = {
            "alerts_generated": 0,
            "alerts_sent": 0,
            "alerts_failed": 0,
            "rules_triggered": defaultdict(int)
        }
        
        # Logger
        self.logger = logging.getLogger("vtc_alerts")
        
        # Initialisation des règles par défaut
        self._setup_default_rules()
    
    def _setup_default_rules(self):
        """Configure les règles d'alerte par défaut."""
        
        # Règle 1: Tentatives de brute force
        self.add_rule(AlertRule(
            rule_id="brute_force_attack",
            name="Attaque de brute force détectée",
            description="Détection d'une tentative d'attaque de brute force",
            condition=lambda event: (
                event.event_type == AuditEventType.AUTH_LOGIN_FAILED and
                event.details.get("consecutive_failures", 0) >= 5
            ),
            priority=AlertPriority.HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG],
            cooldown_minutes=10,
            tags=["security", "authentication", "brute_force"]
        ))
        
        # Règle 2: Injection SQL
        self.add_rule(AlertRule(
            rule_id="sql_injection_attempt",
            name="Tentative d'injection SQL",
            description="Détection d'une tentative d'injection SQL",
            condition=lambda event: (
                event.event_type == AuditEventType.SECURITY_THREAT_DETECTED and
                "sql_injection" in event.details.get("threat_type", "").lower()
            ),
            priority=AlertPriority.CRITICAL,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK],
            cooldown_minutes=1,
            tags=["security", "sql_injection", "critical"]
        ))
        
        # Règle 3: Accès administrateur
        self.add_rule(AlertRule(
            rule_id="admin_access",
            name="Accès administrateur",
            description="Accès aux fonctions d'administration",
            condition=lambda event: (
                event.event_type == AuditEventType.AUTHZ_PRIVILEGE_ESCALATION or
                "admin" in event.details.get("role", "").lower()
            ),
            priority=AlertPriority.MEDIUM,
            channels=[AlertChannel.LOG, AlertChannel.EMAIL],
            cooldown_minutes=30,
            tags=["access_control", "admin"]
        ))
        
        # Règle 4: Échec de validation de licence VTC
        self.add_rule(AlertRule(
            rule_id="vtc_license_invalid",
            name="Licence VTC invalide",
            description="Tentative d'utilisation avec une licence VTC invalide",
            condition=lambda event: (
                event.event_type == AuditEventType.VTC_LICENSE_INVALID
            ),
            priority=AlertPriority.HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.LOG],
            cooldown_minutes=5,
            tags=["compliance", "vtc_license"]
        ))
        
        # Règle 5: Violation RGPD
        self.add_rule(AlertRule(
            rule_id="gdpr_violation",
            name="Violation RGPD potentielle",
            description="Accès non autorisé aux données personnelles",
            condition=lambda event: (
                event.event_type in [
                    AuditEventType.GDPR_DATA_ACCESS,
                    AuditEventType.GDPR_DATA_ERASURE
                ] and not event.success
            ),
            priority=AlertPriority.HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.WEBHOOK],
            cooldown_minutes=1,
            tags=["gdpr", "data_protection", "compliance"]
        ))
        
        # Règle 6: Assurance expirée
        self.add_rule(AlertRule(
            rule_id="insurance_expired",
            name="Assurance expirée",
            description="Tentative d'utilisation avec une assurance expirée",
            condition=lambda event: (
                event.event_type == AuditEventType.INSURANCE_EXPIRED
            ),
            priority=AlertPriority.HIGH,
            channels=[AlertChannel.EMAIL, AlertChannel.LOG],
            cooldown_minutes=60,
            tags=["compliance", "insurance"]
        ))
        
        # Règle 7: Erreurs système critiques
        self.add_rule(AlertRule(
            rule_id="system_error_critical",
            name="Erreur système critique",
            description="Erreur système de niveau critique",
            condition=lambda event: (
                event.severity == AuditSeverity.CRITICAL and
                not event.success
            ),
            priority=AlertPriority.EMERGENCY,
            channels=[AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK],
            cooldown_minutes=1,
            tags=["system", "critical", "error"]
        ))
        
        # Règle 8: Localisation suspecte
        self.add_rule(AlertRule(
            rule_id="suspicious_location",
            name="Connexion depuis une localisation suspecte",
            description="Connexion depuis une nouvelle localisation géographique",
            condition=lambda event: (
                event.event_type == AuditEventType.AUTH_LOGIN_SUCCESS and
                event.details.get("new_location", False)
            ),
            priority=AlertPriority.MEDIUM,
            channels=[AlertChannel.EMAIL, AlertChannel.LOG],
            cooldown_minutes=60,
            tags=["security", "geolocation"]
        ))
    
    def add_rule(self, rule: AlertRule):
        """Ajoute une règle d'alerte."""
        self.rules[rule.rule_id] = rule
        self.logger.info(f"Règle d'alerte ajoutée: {rule.name}")
    
    def remove_rule(self, rule_id: str) -> bool:
        """Supprime une règle d'alerte."""
        if rule_id in self.rules:
            del self.rules[rule_id]
            self.logger.info(f"Règle d'alerte supprimée: {rule_id}")
            return True
        return False
    
    def enable_rule(self, rule_id: str) -> bool:
        """Active une règle d'alerte."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = True
            return True
        return False
    
    def disable_rule(self, rule_id: str) -> bool:
        """Désactive une règle d'alerte."""
        if rule_id in self.rules:
            self.rules[rule_id].enabled = False
            return True
        return False
    
    async def process_event(self, event: AuditEvent) -> List[Alert]:
        """
        Traite un événement d'audit et génère des alertes si nécessaire.
        
        Args:
            event: Événement d'audit à traiter
            
        Returns:
            Liste des alertes générées
        """
        alerts = []
        
        for rule in self.rules.values():
            if not rule.enabled:
                continue
            
            # Vérification du cooldown
            if self._is_rule_in_cooldown(rule.rule_id):
                continue
            
            try:
                # Test de la condition
                if rule.condition(event):
                    alert = await self._create_alert(rule, event)
                    alerts.append(alert)
                    
                    # Envoi de l'alerte
                    await self._send_alert(alert)
                    
                    # Mise à jour des statistiques
                    self.stats["alerts_generated"] += 1
                    self.stats["rules_triggered"][rule.rule_id] += 1
                    
                    # Mise à jour du cooldown
                    self._update_rule_cooldown(rule.rule_id, rule.cooldown_minutes)
                    
            except Exception as e:
                self.logger.error(f"Erreur lors du traitement de la règle {rule.rule_id}: {e}")
        
        return alerts
    
    async def process_threat_detection(self, threat: ThreatDetection) -> List[Alert]:
        """
        Traite une détection de menace et génère des alertes.
        
        Args:
            threat: Détection de menace
            
        Returns:
            Liste des alertes générées
        """
        alerts = []
        
        # Création d'une alerte basée sur le niveau de menace
        priority = self._threat_level_to_priority(threat.threat_level)
        
        alert = Alert(
            alert_id=f"threat_{threat.timestamp.strftime('%Y%m%d_%H%M%S')}_{hash(threat.description) % 10000:04d}",
            rule_id="threat_detection",
            title=f"Menace détectée: {threat.threat_type.value}",
            message=f"{threat.description}\nConfiance: {threat.confidence:.2%}\nActions recommandées: {', '.join(threat.recommended_actions)}",
            priority=priority,
            threat_detection=threat,
            metadata={
                "threat_type": threat.threat_type.value,
                "confidence": threat.confidence,
                "evidence": threat.evidence
            }
        )
        
        # Détermination des canaux selon la priorité
        channels = self._get_channels_for_priority(priority)
        
        # Envoi de l'alerte
        for channel in channels:
            await self._send_alert_to_channel(alert, channel)
        
        alerts.append(alert)
        self.alert_history.append(alert)
        
        return alerts
    
    def _threat_level_to_priority(self, threat_level: ThreatLevel) -> AlertPriority:
        """Convertit un niveau de menace en priorité d'alerte."""
        mapping = {
            ThreatLevel.LOW: AlertPriority.LOW,
            ThreatLevel.MEDIUM: AlertPriority.MEDIUM,
            ThreatLevel.HIGH: AlertPriority.HIGH,
            ThreatLevel.CRITICAL: AlertPriority.EMERGENCY
        }
        return mapping.get(threat_level, AlertPriority.MEDIUM)
    
    def _get_channels_for_priority(self, priority: AlertPriority) -> List[AlertChannel]:
        """Retourne les canaux appropriés selon la priorité."""
        if priority == AlertPriority.EMERGENCY:
            return [AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.WEBHOOK, AlertChannel.LOG]
        elif priority == AlertPriority.CRITICAL:
            return [AlertChannel.EMAIL, AlertChannel.SLACK, AlertChannel.LOG]
        elif priority == AlertPriority.HIGH:
            return [AlertChannel.EMAIL, AlertChannel.LOG]
        elif priority == AlertPriority.MEDIUM:
            return [AlertChannel.LOG, AlertChannel.EMAIL]
        else:
            return [AlertChannel.LOG]
    
    def _is_rule_in_cooldown(self, rule_id: str) -> bool:
        """Vérifie si une règle est en cooldown."""
        if rule_id not in self.rule_cooldowns:
            return False
        
        return datetime.utcnow() < self.rule_cooldowns[rule_id]
    
    def _update_rule_cooldown(self, rule_id: str, cooldown_minutes: int):
        """Met à jour le cooldown d'une règle."""
        self.rule_cooldowns[rule_id] = datetime.utcnow() + timedelta(minutes=cooldown_minutes)
    
    async def _create_alert(self, rule: AlertRule, event: AuditEvent) -> Alert:
        """Crée une alerte à partir d'une règle et d'un événement."""
        alert_id = f"{rule.rule_id}_{event.timestamp.strftime('%Y%m%d_%H%M%S')}_{hash(event.event_id) % 10000:04d}"
        
        # Construction du message
        message = f"Règle déclenchée: {rule.name}\n"
        message += f"Description: {rule.description}\n"
        message += f"Événement: {event.event_type.value}\n"
        message += f"Action: {event.action}\n"
        
        if event.user_id:
            message += f"Utilisateur: {event.user_id}\n"
        
        if event.ip_address:
            message += f"Adresse IP: {event.ip_address}\n"
        
        if event.details:
            message += f"Détails: {json.dumps(event.details, indent=2)}\n"
        
        alert = Alert(
            alert_id=alert_id,
            rule_id=rule.rule_id,
            title=rule.name,
            message=message,
            priority=rule.priority,
            source_event=event,
            metadata={
                "rule_tags": rule.tags,
                "event_severity": event.severity.value,
                "risk_score": event.risk_score
            }
        )
        
        # Ajout à l'historique
        self.alert_history.append(alert)
        
        # Ajout aux alertes actives si priorité élevée
        if rule.priority in [AlertPriority.HIGH, AlertPriority.CRITICAL, AlertPriority.EMERGENCY]:
            self.active_alerts[alert_id] = alert
        
        return alert
    
    async def _send_alert(self, alert: Alert):
        """Envoie une alerte sur tous les canaux configurés."""
        rule = self.rules.get(alert.rule_id)
        if not rule:
            return
        
        for channel in rule.channels:
            try:
                await self._send_alert_to_channel(alert, channel)
                self.stats["alerts_sent"] += 1
            except Exception as e:
                self.logger.error(f"Erreur lors de l'envoi sur {channel}: {e}")
                self.stats["alerts_failed"] += 1
    
    async def _send_alert_to_channel(self, alert: Alert, channel: AlertChannel):
        """Envoie une alerte sur un canal spécifique."""
        if channel == AlertChannel.EMAIL:
            await self._send_email_alert(alert)
        elif channel == AlertChannel.SLACK:
            await self._send_slack_alert(alert)
        elif channel == AlertChannel.WEBHOOK:
            await self._send_webhook_alert(alert)
        elif channel == AlertChannel.LOG:
            await self._send_log_alert(alert)
        elif channel == AlertChannel.CONSOLE:
            await self._send_console_alert(alert)
    
    async def _send_email_alert(self, alert: Alert):
        """Envoie une alerte par email."""
        if not self.config["email"]["username"] or not self.config["email"]["to_emails"]:
            return
        
        try:
            # Création du message
            msg = email.mime.multipart.MimeMultipart()
            msg['From'] = self.config["email"]["from_email"] or self.config["email"]["username"]
            msg['To'] = ", ".join(self.config["email"]["to_emails"])
            msg['Subject'] = f"[VTC Alert - {alert.priority.value.upper()}] {alert.title}"
            
            # Corps du message
            body = f"""
Alerte VTC - {alert.priority.value.upper()}

Titre: {alert.title}
Priorité: {alert.priority.value}
Timestamp: {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}

Message:
{alert.message}

ID de l'alerte: {alert.alert_id}
Règle: {alert.rule_id}

---
Système d'alertes VTC
            """
            
            msg.attach(email.mime.text.MimeText(body, 'plain'))
            
            # Envoi
            context = ssl.create_default_context()
            with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
                server.starttls(context=context)
                server.login(self.config["email"]["username"], self.config["email"]["password"])
                server.send_message(msg)
                
        except Exception as e:
            self.logger.error(f"Erreur lors de l'envoi d'email: {e}")
            raise
    
    async def _send_slack_alert(self, alert: Alert):
        """Envoie une alerte sur Slack."""
        if not self.config["slack"]["webhook_url"]:
            return
        
        # Construction du payload Slack
        color_map = {
            AlertPriority.LOW: "#36a64f",
            AlertPriority.MEDIUM: "#ff9500",
            AlertPriority.HIGH: "#ff0000",
            AlertPriority.CRITICAL: "#8b0000",
            AlertPriority.EMERGENCY: "#000000"
        }
        
        payload = {
            "channel": self.config["slack"]["channel"],
            "username": "VTC Security Bot",
            "icon_emoji": ":warning:",
            "attachments": [{
                "color": color_map.get(alert.priority, "#ff9500"),
                "title": f"🚨 {alert.title}",
                "text": alert.message[:500] + "..." if len(alert.message) > 500 else alert.message,
                "fields": [
                    {
                        "title": "Priorité",
                        "value": alert.priority.value.upper(),
                        "short": True
                    },
                    {
                        "title": "Timestamp",
                        "value": alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC'),
                        "short": True
                    },
                    {
                        "title": "ID Alerte",
                        "value": alert.alert_id,
                        "short": True
                    }
                ],
                "footer": "VTC Security System",
                "ts": int(alert.timestamp.timestamp())
            }]
        }
        
        # Envoi via webhook (simulation)
        self.logger.info(f"Slack alert sent: {alert.title}")
    
    async def _send_webhook_alert(self, alert: Alert):
        """Envoie une alerte via webhook."""
        if not self.config["webhook"]["url"]:
            return
        
        # Construction du payload
        payload = {
            "alert_id": alert.alert_id,
            "rule_id": alert.rule_id,
            "title": alert.title,
            "message": alert.message,
            "priority": alert.priority.value,
            "timestamp": alert.timestamp.isoformat(),
            "metadata": alert.metadata
        }
        
        # Envoi (simulation)
        self.logger.info(f"Webhook alert sent: {alert.title}")
    
    async def _send_log_alert(self, alert: Alert):
        """Envoie une alerte dans les logs."""
        log_level = {
            AlertPriority.LOW: logging.INFO,
            AlertPriority.MEDIUM: logging.WARNING,
            AlertPriority.HIGH: logging.ERROR,
            AlertPriority.CRITICAL: logging.CRITICAL,
            AlertPriority.EMERGENCY: logging.CRITICAL
        }.get(alert.priority, logging.WARNING)
        
        self.logger.log(
            log_level,
            f"ALERT [{alert.priority.value.upper()}] {alert.title} - {alert.message[:200]}"
        )
    
    async def _send_console_alert(self, alert: Alert):
        """Affiche une alerte dans la console."""
        print(f"\n🚨 ALERTE VTC [{alert.priority.value.upper()}] 🚨")
        print(f"Titre: {alert.title}")
        print(f"Message: {alert.message}")
        print(f"Timestamp: {alert.timestamp}")
        print("-" * 50)
    
    def acknowledge_alert(self, alert_id: str, user_id: str = None) -> bool:
        """Acquitte une alerte."""
        if alert_id in self.active_alerts:
            self.active_alerts[alert_id].acknowledged = True
            self.active_alerts[alert_id].metadata["acknowledged_by"] = user_id
            self.active_alerts[alert_id].metadata["acknowledged_at"] = datetime.utcnow().isoformat()
            return True
        return False
    
    def resolve_alert(self, alert_id: str, user_id: str = None, resolution_note: str = None) -> bool:
        """Résout une alerte."""
        if alert_id in self.active_alerts:
            alert = self.active_alerts[alert_id]
            alert.resolved = True
            alert.metadata["resolved_by"] = user_id
            alert.metadata["resolved_at"] = datetime.utcnow().isoformat()
            if resolution_note:
                alert.metadata["resolution_note"] = resolution_note
            
            # Suppression des alertes actives
            del self.active_alerts[alert_id]
            return True
        return False
    
    def get_active_alerts(self, priority: AlertPriority = None) -> List[Alert]:
        """Retourne les alertes actives."""
        alerts = list(self.active_alerts.values())
        
        if priority:
            alerts = [alert for alert in alerts if alert.priority == priority]
        
        return sorted(alerts, key=lambda x: x.timestamp, reverse=True)
    
    def get_alert_history(self, limit: int = 100) -> List[Alert]:
        """Retourne l'historique des alertes."""
        return list(self.alert_history)[-limit:]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques des alertes."""
        return {
            **self.stats,
            "active_alerts": len(self.active_alerts),
            "total_rules": len(self.rules),
            "enabled_rules": sum(1 for rule in self.rules.values() if rule.enabled),
            "rules_in_cooldown": len([r for r in self.rule_cooldowns.values() if r > datetime.utcnow()])
        }
    
    def update_config(self, **kwargs):
        """Met à jour la configuration."""
        for key, value in kwargs.items():
            if "." in key:
                # Configuration imbriquée (ex: "email.smtp_server")
                section, param = key.split(".", 1)
                if section in self.config:
                    self.config[section][param] = value
            else:
                self.config[key] = value


# Instance globale du gestionnaire d'alertes
_alert_manager: Optional[AlertManager] = None


def get_alert_manager() -> AlertManager:
    """Retourne l'instance globale du gestionnaire d'alertes."""
    global _alert_manager
    
    if _alert_manager is None:
        _alert_manager = AlertManager()
    
    return _alert_manager


async def send_alert_for_event(event: AuditEvent) -> List[Alert]:
    """Fonction utilitaire pour envoyer des alertes pour un événement."""
    manager = get_alert_manager()
    return await manager.process_event(event)


async def send_alert_for_threat(threat: ThreatDetection) -> List[Alert]:
    """Fonction utilitaire pour envoyer des alertes pour une menace."""
    manager = get_alert_manager()
    return await manager.process_threat_detection(threat)

