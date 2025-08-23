"""
Module de gestion des alertes automatiques.
"""

from .alert_manager import (
    AlertManager,
    Alert,
    AlertRule,
    AlertChannel,
    AlertPriority,
    get_alert_manager,
    send_alert_for_event,
    send_alert_for_threat
)

__all__ = [
    "AlertManager",
    "Alert", 
    "AlertRule",
    "AlertChannel",
    "AlertPriority",
    "get_alert_manager",
    "send_alert_for_event",
    "send_alert_for_threat"
]

