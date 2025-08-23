"""
Définition des événements d'audit pour l'application VTC.
"""

from enum import Enum
from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field
import uuid


class AuditEventType(str, Enum):
    """Types d'événements d'audit."""
    
    # Authentification
    AUTH_LOGIN_SUCCESS = "auth_login_success"
    AUTH_LOGIN_FAILED = "auth_login_failed"
    AUTH_LOGOUT = "auth_logout"
    AUTH_2FA_SUCCESS = "auth_2fa_success"
    AUTH_2FA_FAILED = "auth_2fa_failed"
    AUTH_PASSWORD_CHANGE = "auth_password_change"
    AUTH_PASSWORD_RESET = "auth_password_reset"
    
    # Autorisation
    AUTHZ_ACCESS_GRANTED = "authz_access_granted"
    AUTHZ_ACCESS_DENIED = "authz_access_denied"
    AUTHZ_PRIVILEGE_ESCALATION = "authz_privilege_escalation"
    
    # Données utilisateur
    USER_CREATE = "user_create"
    USER_UPDATE = "user_update"
    USER_DELETE = "user_delete"
    USER_VIEW = "user_view"
    USER_EXPORT = "user_export"
    
    # Courses VTC
    TRIP_CREATE = "trip_create"
    TRIP_UPDATE = "trip_update"
    TRIP_CANCEL = "trip_cancel"
    TRIP_COMPLETE = "trip_complete"
    TRIP_VIEW = "trip_view"
    
    # Paiements
    PAYMENT_PROCESS = "payment_process"
    PAYMENT_SUCCESS = "payment_success"
    PAYMENT_FAILED = "payment_failed"
    PAYMENT_REFUND = "payment_refund"
    
    # Configuration système
    CONFIG_UPDATE = "config_update"
    CONFIG_VIEW = "config_view"
    
    # API
    API_CALL = "api_call"
    API_ERROR = "api_error"
    API_RATE_LIMIT = "api_rate_limit"
    
    # Sécurité
    SECURITY_THREAT_DETECTED = "security_threat_detected"
    SECURITY_INTRUSION_ATTEMPT = "security_intrusion_attempt"
    SECURITY_VIOLATION = "security_violation"
    SECURITY_SCAN_DETECTED = "security_scan_detected"
    
    # RGPD
    GDPR_CONSENT_GIVEN = "gdpr_consent_given"
    GDPR_CONSENT_WITHDRAWN = "gdpr_consent_withdrawn"
    GDPR_DATA_ACCESS = "gdpr_data_access"
    GDPR_DATA_RECTIFICATION = "gdpr_data_rectification"
    GDPR_DATA_ERASURE = "gdpr_data_erasure"
    GDPR_DATA_PORTABILITY = "gdpr_data_portability"
    
    # Licences VTC
    VTC_LICENSE_VALIDATED = "vtc_license_validated"
    VTC_LICENSE_EXPIRED = "vtc_license_expired"
    VTC_LICENSE_INVALID = "vtc_license_invalid"
    
    # Assurances
    INSURANCE_VALIDATED = "insurance_validated"
    INSURANCE_EXPIRED = "insurance_expired"
    INSURANCE_INVALID = "insurance_invalid"


class AuditSeverity(str, Enum):
    """Niveaux de sévérité des événements d'audit."""
    
    INFO = "info"
    WARNING = "warning"
    HIGH = "high"
    CRITICAL = "critical"


class AuditEvent(BaseModel):
    """Modèle d'événement d'audit."""
    
    # Identifiants
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    # Type et sévérité
    event_type: AuditEventType
    severity: AuditSeverity = AuditSeverity.INFO
    
    # Contexte utilisateur
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    
    # Action et ressource
    action: str
    resource: Optional[str] = None
    method: Optional[str] = None
    
    # Détails spécifiques
    details: Dict[str, Any] = Field(default_factory=dict)
    
    # Géolocalisation
    location: Optional[Dict[str, str]] = None
    
    # Score de risque (0.0 à 1.0)
    risk_score: float = 0.0
    
    # Tags de conformité
    compliance_tags: list[str] = Field(default_factory=list)
    
    # Résultat
    success: bool = True
    error_message: Optional[str] = None
    
    # Métadonnées
    correlation_id: Optional[str] = None
    trace_id: Optional[str] = None
    
    class Config:
        """Configuration Pydantic."""
        use_enum_values = True
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AuditEventBuilder:
    """Builder pour créer des événements d'audit facilement."""
    
    def __init__(self):
        self._event = AuditEvent(
            event_type=AuditEventType.API_CALL,
            action="unknown"
        )
    
    def event_type(self, event_type: AuditEventType) -> 'AuditEventBuilder':
        """Définit le type d'événement."""
        self._event.event_type = event_type
        return self
    
    def severity(self, severity: AuditSeverity) -> 'AuditEventBuilder':
        """Définit la sévérité."""
        self._event.severity = severity
        return self
    
    def user(self, user_id: str, session_id: Optional[str] = None) -> 'AuditEventBuilder':
        """Définit l'utilisateur."""
        self._event.user_id = user_id
        if session_id:
            self._event.session_id = session_id
        return self
    
    def request(self, ip: str, user_agent: str, method: str = None) -> 'AuditEventBuilder':
        """Définit les informations de requête."""
        self._event.ip_address = ip
        self._event.user_agent = user_agent
        if method:
            self._event.method = method
        return self
    
    def action(self, action: str, resource: str = None) -> 'AuditEventBuilder':
        """Définit l'action et la ressource."""
        self._event.action = action
        if resource:
            self._event.resource = resource
        return self
    
    def details(self, **kwargs) -> 'AuditEventBuilder':
        """Ajoute des détails."""
        self._event.details.update(kwargs)
        return self
    
    def location(self, country: str = None, city: str = None, region: str = None) -> 'AuditEventBuilder':
        """Définit la géolocalisation."""
        location = {}
        if country:
            location["country"] = country
        if city:
            location["city"] = city
        if region:
            location["region"] = region
        if location:
            self._event.location = location
        return self
    
    def risk_score(self, score: float) -> 'AuditEventBuilder':
        """Définit le score de risque."""
        self._event.risk_score = max(0.0, min(1.0, score))
        return self
    
    def compliance(self, *tags: str) -> 'AuditEventBuilder':
        """Ajoute des tags de conformité."""
        self._event.compliance_tags.extend(tags)
        return self
    
    def success(self, success: bool = True, error: str = None) -> 'AuditEventBuilder':
        """Définit le résultat."""
        self._event.success = success
        if error:
            self._event.error_message = error
        return self
    
    def correlation(self, correlation_id: str, trace_id: str = None) -> 'AuditEventBuilder':
        """Définit les IDs de corrélation."""
        self._event.correlation_id = correlation_id
        if trace_id:
            self._event.trace_id = trace_id
        return self
    
    def build(self) -> AuditEvent:
        """Construit l'événement d'audit."""
        return self._event


# Fonctions utilitaires pour créer des événements courants

def create_auth_event(
    event_type: AuditEventType,
    user_id: str,
    ip_address: str,
    success: bool = True,
    details: Dict[str, Any] = None
) -> AuditEvent:
    """Crée un événement d'authentification."""
    builder = AuditEventBuilder()
    builder.event_type(event_type)
    builder.user(user_id)
    builder.request(ip_address, "")
    builder.action(event_type.value)
    builder.success(success)
    builder.compliance("SECURITY", "AUDIT")
    
    if details:
        builder.details(**details)
    
    if not success:
        builder.severity(AuditSeverity.WARNING)
        builder.risk_score(0.3)
    
    return builder.build()


def create_data_access_event(
    user_id: str,
    resource: str,
    action: str,
    ip_address: str,
    success: bool = True,
    sensitive: bool = False
) -> AuditEvent:
    """Crée un événement d'accès aux données."""
    builder = AuditEventBuilder()
    builder.event_type(AuditEventType.USER_VIEW if "view" in action else AuditEventType.USER_UPDATE)
    builder.user(user_id)
    builder.request(ip_address, "")
    builder.action(action, resource)
    builder.success(success)
    builder.compliance("RGPD", "AUDIT")
    
    if sensitive:
        builder.severity(AuditSeverity.WARNING)
        builder.risk_score(0.2)
        builder.compliance("SENSITIVE_DATA")
    
    return builder.build()


def create_security_event(
    event_type: AuditEventType,
    ip_address: str,
    severity: AuditSeverity = AuditSeverity.HIGH,
    details: Dict[str, Any] = None
) -> AuditEvent:
    """Crée un événement de sécurité."""
    builder = AuditEventBuilder()
    builder.event_type(event_type)
    builder.severity(severity)
    builder.request(ip_address, "")
    builder.action(event_type.value)
    builder.success(False)
    builder.risk_score(0.8 if severity == AuditSeverity.CRITICAL else 0.6)
    builder.compliance("SECURITY", "THREAT")
    
    if details:
        builder.details(**details)
    
    return builder.build()


def create_gdpr_event(
    event_type: AuditEventType,
    user_id: str,
    data_subject_id: str,
    action: str,
    legal_basis: str = None
) -> AuditEvent:
    """Crée un événement RGPD."""
    builder = AuditEventBuilder()
    builder.event_type(event_type)
    builder.user(user_id)
    builder.action(action)
    builder.details(
        data_subject_id=data_subject_id,
        legal_basis=legal_basis or "consent"
    )
    builder.compliance("RGPD", "DATA_PROTECTION")
    
    return builder.build()


def create_vtc_compliance_event(
    event_type: AuditEventType,
    driver_id: str,
    license_number: str = None,
    insurance_policy: str = None,
    success: bool = True
) -> AuditEvent:
    """Crée un événement de conformité VTC."""
    builder = AuditEventBuilder()
    builder.event_type(event_type)
    builder.action(event_type.value)
    builder.details(
        driver_id=driver_id,
        license_number=license_number,
        insurance_policy=insurance_policy
    )
    builder.success(success)
    builder.compliance("VTC_REGULATION", "COMPLIANCE")
    
    if not success:
        builder.severity(AuditSeverity.HIGH)
        builder.risk_score(0.7)
    
    return builder.build()

