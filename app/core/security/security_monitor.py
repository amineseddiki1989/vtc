"""
Module de monitoring de sécurité pour l'application VTC.
Surveille les événements de sécurité et génère des alertes.
"""

import time
import json
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
from threading import Lock
import hashlib


class SecurityEvent:
    """Représente un événement de sécurité."""
    
    def __init__(self, event_type: str, severity: str, source: str, 
                 description: str, metadata: Dict[str, Any] = None):
        self.timestamp = datetime.utcnow()
        self.event_type = event_type
        self.severity = severity  # CRITICAL, HIGH, MEDIUM, LOW
        self.source = source
        self.description = description
        self.metadata = metadata or {}
        self.event_id = self._generate_event_id()
    
    def _generate_event_id(self) -> str:
        """Génère un ID unique pour l'événement."""
        data = f"{self.timestamp}{self.event_type}{self.source}{self.description}"
        return hashlib.sha256(data.encode()).hexdigest()[:16]
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'événement en dictionnaire."""
        return {
            "event_id": self.event_id,
            "timestamp": self.timestamp.isoformat(),
            "event_type": self.event_type,
            "severity": self.severity,
            "source": self.source,
            "description": self.description,
            "metadata": self.metadata
        }


class SecurityMonitor:
    """Moniteur de sécurité centralisé."""
    
    def __init__(self, max_events: int = 10000, alert_threshold: int = 5):
        self.max_events = max_events
        self.alert_threshold = alert_threshold
        self.events = deque(maxlen=max_events)
        self.event_counts = defaultdict(int)
        self.rate_limits = defaultdict(lambda: deque(maxlen=100))
        self.lock = Lock()
        
        # Configuration des alertes
        self.alert_rules = {
            "failed_login": {"threshold": 5, "window_minutes": 5},
            "invalid_token": {"threshold": 10, "window_minutes": 10},
            "suspicious_request": {"threshold": 20, "window_minutes": 15},
            "data_access": {"threshold": 100, "window_minutes": 60}
        }
        
        # Logger pour les événements de sécurité
        self.logger = logging.getLogger("security_monitor")
        self.logger.setLevel(logging.INFO)
    
    def log_event(self, event_type: str, severity: str, source: str, 
                  description: str, metadata: Dict[str, Any] = None) -> str:
        """
        Enregistre un événement de sécurité.
        
        Args:
            event_type: Type d'événement (failed_login, invalid_token, etc.)
            severity: Sévérité (CRITICAL, HIGH, MEDIUM, LOW)
            source: Source de l'événement (IP, user_id, etc.)
            description: Description de l'événement
            metadata: Métadonnées additionnelles
            
        Returns:
            ID de l'événement créé
        """
        event = SecurityEvent(event_type, severity, source, description, metadata)
        
        with self.lock:
            self.events.append(event)
            self.event_counts[event_type] += 1
            self.rate_limits[f"{event_type}:{source}"].append(time.time())
        
        # Logger l'événement
        self.logger.info(f"Security Event: {event.to_dict()}")
        
        # Vérifier les seuils d'alerte
        self._check_alert_thresholds(event)
        
        return event.event_id
    
    def _check_alert_thresholds(self, event: SecurityEvent):
        """Vérifie si un événement déclenche une alerte."""
        event_key = f"{event.event_type}:{event.source}"
        
        if event.event_type in self.alert_rules:
            rule = self.alert_rules[event.event_type]
            window_start = time.time() - (rule["window_minutes"] * 60)
            
            # Compter les événements récents
            recent_events = [
                t for t in self.rate_limits[event_key] 
                if t > window_start
            ]
            
            if len(recent_events) >= rule["threshold"]:
                self._trigger_alert(event, len(recent_events), rule)
    
    def _trigger_alert(self, event: SecurityEvent, count: int, rule: Dict[str, Any]):
        """Déclenche une alerte de sécurité."""
        alert_event = SecurityEvent(
            event_type="security_alert",
            severity="HIGH",
            source="security_monitor",
            description=f"Seuil d'alerte dépassé pour {event.event_type}",
            metadata={
                "original_event": event.to_dict(),
                "event_count": count,
                "threshold": rule["threshold"],
                "window_minutes": rule["window_minutes"]
            }
        )
        
        with self.lock:
            self.events.append(alert_event)
        
        self.logger.warning(f"SECURITY ALERT: {alert_event.to_dict()}")
    
    def get_events(self, event_type: str = None, severity: str = None, 
                   source: str = None, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Récupère les événements selon les critères.
        
        Args:
            event_type: Filtrer par type d'événement
            severity: Filtrer par sévérité
            source: Filtrer par source
            limit: Nombre maximum d'événements à retourner
            
        Returns:
            Liste des événements correspondants
        """
        with self.lock:
            filtered_events = []
            
            for event in reversed(self.events):
                if len(filtered_events) >= limit:
                    break
                
                if event_type and event.event_type != event_type:
                    continue
                if severity and event.severity != severity:
                    continue
                if source and event.source != source:
                    continue
                
                filtered_events.append(event.to_dict())
            
            return filtered_events
    
    def get_statistics(self, hours: int = 24) -> Dict[str, Any]:
        """
        Génère des statistiques sur les événements de sécurité.
        
        Args:
            hours: Nombre d'heures à analyser
            
        Returns:
            Dictionnaire avec les statistiques
        """
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        
        with self.lock:
            recent_events = [
                event for event in self.events 
                if event.timestamp > cutoff_time
            ]
        
        stats = {
            "total_events": len(recent_events),
            "by_type": defaultdict(int),
            "by_severity": defaultdict(int),
            "by_source": defaultdict(int),
            "timeline": defaultdict(int)
        }
        
        for event in recent_events:
            stats["by_type"][event.event_type] += 1
            stats["by_severity"][event.severity] += 1
            stats["by_source"][event.source] += 1
            
            # Timeline par heure
            hour_key = event.timestamp.strftime("%Y-%m-%d %H:00")
            stats["timeline"][hour_key] += 1
        
        return dict(stats)
    
    def is_rate_limited(self, event_type: str, source: str, 
                       max_requests: int = 10, window_minutes: int = 5) -> bool:
        """
        Vérifie si une source est limitée par le taux de requêtes.
        
        Args:
            event_type: Type d'événement
            source: Source à vérifier
            max_requests: Nombre maximum de requêtes
            window_minutes: Fenêtre de temps en minutes
            
        Returns:
            True si la source est limitée
        """
        event_key = f"{event_type}:{source}"
        window_start = time.time() - (window_minutes * 60)
        
        with self.lock:
            recent_requests = [
                t for t in self.rate_limits[event_key] 
                if t > window_start
            ]
            
            return len(recent_requests) >= max_requests
    
    def clear_old_events(self, days: int = 30):
        """
        Supprime les anciens événements.
        
        Args:
            days: Nombre de jours à conserver
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        
        with self.lock:
            # Filtrer les événements récents
            recent_events = deque(
                [event for event in self.events if event.timestamp > cutoff_time],
                maxlen=self.max_events
            )
            self.events = recent_events
    
    def export_events(self, filepath: str, event_type: str = None, 
                     hours: int = 24) -> int:
        """
        Exporte les événements vers un fichier JSON.
        
        Args:
            filepath: Chemin du fichier de sortie
            event_type: Type d'événement à exporter (optionnel)
            hours: Nombre d'heures à exporter
            
        Returns:
            Nombre d'événements exportés
        """
        events_to_export = self.get_events(
            event_type=event_type, 
            limit=10000
        )
        
        # Filtrer par temps
        cutoff_time = datetime.utcnow() - timedelta(hours=hours)
        filtered_events = [
            event for event in events_to_export
            if datetime.fromisoformat(event["timestamp"]) > cutoff_time
        ]
        
        export_data = {
            "export_timestamp": datetime.utcnow().isoformat(),
            "total_events": len(filtered_events),
            "events": filtered_events
        }
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        return len(filtered_events)


# Instance globale du moniteur de sécurité
security_monitor = SecurityMonitor()


def log_security_event(event_type: str, severity: str, source: str, 
                      description: str, metadata: Dict[str, Any] = None) -> str:
    """
    Fonction utilitaire pour enregistrer un événement de sécurité.
    
    Args:
        event_type: Type d'événement
        severity: Sévérité (CRITICAL, HIGH, MEDIUM, LOW)
        source: Source de l'événement
        description: Description
        metadata: Métadonnées additionnelles
        
    Returns:
        ID de l'événement
    """
    return security_monitor.log_event(event_type, severity, source, description, metadata)


def get_security_monitor() -> SecurityMonitor:
    """Retourne l'instance du moniteur de sécurité."""
    return security_monitor


def check_rate_limit(event_type: str, source: str, 
                    max_requests: int = 10, window_minutes: int = 5) -> bool:
    """
    Vérifie si une source est limitée par le taux de requêtes.
    
    Args:
        event_type: Type d'événement
        source: Source à vérifier
        max_requests: Nombre maximum de requêtes
        window_minutes: Fenêtre de temps en minutes
        
    Returns:
        True si la source est limitée
    """
    return security_monitor.is_rate_limited(event_type, source, max_requests, window_minutes)

