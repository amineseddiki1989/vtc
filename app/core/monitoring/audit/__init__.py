"""
Module de logs d'audit pour l'application VTC.
"""

from .audit_events import (
    AuditEvent,
    AuditEventType,
    AuditSeverity,
    AuditEventBuilder,
    create_auth_event,
    create_data_access_event,
    create_security_event,
    create_gdpr_event,
    create_vtc_compliance_event
)

from .audit_logger import (
    AuditLogger,
    get_audit_logger,
    log_audit_event
)

__all__ = [
    # Events
    "AuditEvent",
    "AuditEventType", 
    "AuditSeverity",
    "AuditEventBuilder",
    "create_auth_event",
    "create_data_access_event",
    "create_security_event",
    "create_gdpr_event",
    "create_vtc_compliance_event",
    
    # Logger
    "AuditLogger",
    "get_audit_logger",
    "log_audit_event"
]

