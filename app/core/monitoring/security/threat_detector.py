"""
Détecteur de menaces de sécurité pour l'application VTC.
"""

import re
import time
import asyncio
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Any
from collections import defaultdict, deque
from dataclasses import dataclass, field
from enum import Enum
import ipaddress
import hashlib
from urllib.parse import unquote

from ..audit.audit_events import AuditEvent, AuditEventType, AuditSeverity, create_security_event


class ThreatLevel(str, Enum):
    """Niveaux de menace."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ThreatType(str, Enum):
    """Types de menaces."""
    BRUTE_FORCE = "brute_force"
    SQL_INJECTION = "sql_injection"
    XSS_ATTACK = "xss_attack"
    PATH_TRAVERSAL = "path_traversal"
    RATE_LIMIT_VIOLATION = "rate_limit_violation"
    SUSPICIOUS_LOCATION = "suspicious_location"
    PRIVILEGE_ESCALATION = "privilege_escalation"
    DATA_EXFILTRATION = "data_exfiltration"
    MALICIOUS_PAYLOAD = "malicious_payload"
    ANOMALOUS_BEHAVIOR = "anomalous_behavior"


@dataclass
class ThreatDetection:
    """Résultat de détection de menace."""
    threat_type: ThreatType
    threat_level: ThreatLevel
    confidence: float  # 0.0 à 1.0
    description: str
    evidence: Dict[str, Any] = field(default_factory=dict)
    recommended_actions: List[str] = field(default_factory=list)
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class SecurityContext:
    """Contexte de sécurité pour l'analyse."""
    ip_address: str
    user_id: Optional[str] = None
    user_agent: Optional[str] = None
    endpoint: Optional[str] = None
    method: Optional[str] = None
    payload: Optional[str] = None
    headers: Dict[str, str] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ThreatDetector:
    """Détecteur de menaces de sécurité en temps réel."""
    
    def __init__(self):
        """Initialise le détecteur de menaces."""
        
        # Compteurs pour la détection de brute force
        self.failed_attempts = defaultdict(deque)  # IP -> deque of timestamps
        self.blocked_ips = {}  # IP -> block_until_timestamp
        
        # Historique des requêtes pour la détection d'anomalies
        self.request_history = defaultdict(deque)  # IP -> deque of requests
        
        # Patterns de détection
        self.sql_injection_patterns = self._load_sql_injection_patterns()
        self.xss_patterns = self._load_xss_patterns()
        self.path_traversal_patterns = self._load_path_traversal_patterns()
        self.malicious_user_agents = self._load_malicious_user_agents()
        
        # Configuration
        self.config = {
            "brute_force_threshold": 5,  # Tentatives max
            "brute_force_window": 300,   # Fenêtre de temps (5 min)
            "rate_limit_threshold": 100, # Requêtes max par minute
            "block_duration": 3600,      # Durée de blocage (1h)
            "anomaly_threshold": 0.8,    # Seuil d'anomalie
            "max_payload_size": 1024 * 1024,  # 1MB
        }
        
        # Géolocalisation des IPs connues
        self.known_locations = {}  # IP -> location
        
        # Patterns d'utilisateurs légitimes
        self.legitimate_patterns = set()
    
    def _load_sql_injection_patterns(self) -> List[re.Pattern]:
        """Charge les patterns de détection d'injection SQL."""
        patterns = [
            r"(\b(union|select|insert|update|delete|drop|create|alter|exec|execute)\b)",
            r"(\b(or|and)\s+\d+\s*=\s*\d+)",
            r"(\b(or|and)\s+['\"]?\w+['\"]?\s*=\s*['\"]?\w+['\"]?)",
            r"(--|#|/\*|\*/)",
            r"(\bxp_cmdshell\b|\bsp_executesql\b)",
            r"(\bload_file\b|\binto\s+outfile\b)",
            r"(\bchar\s*\(\s*\d+\s*\))",
            r"(\bhex\s*\(|\bunhex\s*\()",
            r"(\bconcat\s*\(|\bsubstring\s*\()",
            r"(\bwaitfor\s+delay\b|\bbenchmark\s*\()",
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def _load_xss_patterns(self) -> List[re.Pattern]:
        """Charge les patterns de détection XSS."""
        patterns = [
            r"<script[^>]*>.*?</script>",
            r"javascript:",
            r"on\w+\s*=",
            r"<iframe[^>]*>",
            r"<object[^>]*>",
            r"<embed[^>]*>",
            r"<link[^>]*>",
            r"<meta[^>]*>",
            r"eval\s*\(",
            r"expression\s*\(",
            r"vbscript:",
            r"data:text/html",
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def _load_path_traversal_patterns(self) -> List[re.Pattern]:
        """Charge les patterns de détection de traversée de répertoires."""
        patterns = [
            r"\.\./",
            r"\.\.\\",
            r"%2e%2e%2f",
            r"%2e%2e%5c",
            r"\.\.%2f",
            r"\.\.%5c",
            r"%252e%252e%252f",
            r"..%c0%af",
            r"..%c1%9c",
        ]
        
        return [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
    
    def _load_malicious_user_agents(self) -> Set[str]:
        """Charge la liste des User-Agents malveillants."""
        return {
            "sqlmap",
            "nikto",
            "nmap",
            "masscan",
            "zap",
            "burp",
            "w3af",
            "havij",
            "pangolin",
            "acunetix",
            "netsparker",
            "appscan",
            "webscarab",
            "paros",
            "httprint",
            "whatweb",
            "dirb",
            "dirbuster",
            "gobuster",
            "wfuzz",
            "ffuf",
        }
    
    async def analyze_request(self, context: SecurityContext) -> List[ThreatDetection]:
        """
        Analyse une requête pour détecter des menaces.
        
        Args:
            context: Contexte de sécurité de la requête
            
        Returns:
            Liste des menaces détectées
        """
        threats = []
        
        # Vérification IP bloquée
        if self._is_ip_blocked(context.ip_address):
            threats.append(ThreatDetection(
                threat_type=ThreatType.BRUTE_FORCE,
                threat_level=ThreatLevel.HIGH,
                confidence=1.0,
                description=f"IP {context.ip_address} est bloquée",
                evidence={"blocked_until": self.blocked_ips[context.ip_address]},
                recommended_actions=["block_request", "log_incident"]
            ))
            return threats
        
        # Détection de brute force
        brute_force_threat = await self._detect_brute_force(context)
        if brute_force_threat:
            threats.append(brute_force_threat)
        
        # Détection d'injection SQL
        sql_injection_threat = await self._detect_sql_injection(context)
        if sql_injection_threat:
            threats.append(sql_injection_threat)
        
        # Détection XSS
        xss_threat = await self._detect_xss(context)
        if xss_threat:
            threats.append(xss_threat)
        
        # Détection de traversée de répertoires
        path_traversal_threat = await self._detect_path_traversal(context)
        if path_traversal_threat:
            threats.append(path_traversal_threat)
        
        # Détection de violation de rate limit
        rate_limit_threat = await self._detect_rate_limit_violation(context)
        if rate_limit_threat:
            threats.append(rate_limit_threat)
        
        # Détection de User-Agent malveillant
        malicious_ua_threat = await self._detect_malicious_user_agent(context)
        if malicious_ua_threat:
            threats.append(malicious_ua_threat)
        
        # Détection de localisation suspecte
        location_threat = await self._detect_suspicious_location(context)
        if location_threat:
            threats.append(location_threat)
        
        # Détection de payload malveillant
        payload_threat = await self._detect_malicious_payload(context)
        if payload_threat:
            threats.append(payload_threat)
        
        # Détection de comportement anormal
        anomaly_threat = await self._detect_anomalous_behavior(context)
        if anomaly_threat:
            threats.append(anomaly_threat)
        
        # Mise à jour de l'historique
        self._update_request_history(context)
        
        return threats
    
    async def _detect_brute_force(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les attaques de brute force."""
        if not context.user_id:
            return None
        
        # Vérification des tentatives récentes
        now = time.time()
        attempts = self.failed_attempts[context.ip_address]
        
        # Nettoyage des anciennes tentatives
        while attempts and now - attempts[0] > self.config["brute_force_window"]:
            attempts.popleft()
        
        # Vérification du seuil
        if len(attempts) >= self.config["brute_force_threshold"]:
            # Blocage de l'IP
            self.blocked_ips[context.ip_address] = now + self.config["block_duration"]
            
            return ThreatDetection(
                threat_type=ThreatType.BRUTE_FORCE,
                threat_level=ThreatLevel.HIGH,
                confidence=0.9,
                description=f"Attaque de brute force détectée depuis {context.ip_address}",
                evidence={
                    "failed_attempts": len(attempts),
                    "time_window": self.config["brute_force_window"],
                    "blocked_until": self.blocked_ips[context.ip_address]
                },
                recommended_actions=["block_ip", "alert_admin", "log_incident"]
            )
        
        return None
    
    async def _detect_sql_injection(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les tentatives d'injection SQL."""
        if not context.payload:
            return None
        
        # Décodage URL
        decoded_payload = unquote(context.payload)
        
        # Test des patterns
        matches = []
        for pattern in self.sql_injection_patterns:
            if pattern.search(decoded_payload):
                matches.append(pattern.pattern)
        
        if matches:
            confidence = min(0.9, len(matches) * 0.3)
            
            return ThreatDetection(
                threat_type=ThreatType.SQL_INJECTION,
                threat_level=ThreatLevel.CRITICAL,
                confidence=confidence,
                description="Tentative d'injection SQL détectée",
                evidence={
                    "payload": decoded_payload[:200],  # Limiter la taille
                    "patterns_matched": matches,
                    "endpoint": context.endpoint
                },
                recommended_actions=["block_request", "alert_admin", "log_incident"]
            )
        
        return None
    
    async def _detect_xss(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les tentatives d'attaque XSS."""
        if not context.payload:
            return None
        
        # Décodage URL
        decoded_payload = unquote(context.payload)
        
        # Test des patterns
        matches = []
        for pattern in self.xss_patterns:
            if pattern.search(decoded_payload):
                matches.append(pattern.pattern)
        
        if matches:
            confidence = min(0.8, len(matches) * 0.25)
            
            return ThreatDetection(
                threat_type=ThreatType.XSS_ATTACK,
                threat_level=ThreatLevel.HIGH,
                confidence=confidence,
                description="Tentative d'attaque XSS détectée",
                evidence={
                    "payload": decoded_payload[:200],
                    "patterns_matched": matches,
                    "endpoint": context.endpoint
                },
                recommended_actions=["sanitize_input", "block_request", "log_incident"]
            )
        
        return None
    
    async def _detect_path_traversal(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les tentatives de traversée de répertoires."""
        if not context.endpoint:
            return None
        
        # Test de l'endpoint et du payload
        test_strings = [context.endpoint]
        if context.payload:
            test_strings.append(unquote(context.payload))
        
        for test_string in test_strings:
            for pattern in self.path_traversal_patterns:
                if pattern.search(test_string):
                    return ThreatDetection(
                        threat_type=ThreatType.PATH_TRAVERSAL,
                        threat_level=ThreatLevel.HIGH,
                        confidence=0.8,
                        description="Tentative de traversée de répertoires détectée",
                        evidence={
                            "pattern": pattern.pattern,
                            "endpoint": context.endpoint,
                            "payload": context.payload[:100] if context.payload else None
                        },
                        recommended_actions=["block_request", "validate_paths", "log_incident"]
                    )
        
        return None
    
    async def _detect_rate_limit_violation(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les violations de rate limit."""
        now = time.time()
        requests = self.request_history[context.ip_address]
        
        # Nettoyage des anciennes requêtes (dernière minute)
        while requests and now - requests[0] > 60:
            requests.popleft()
        
        # Vérification du seuil
        if len(requests) > self.config["rate_limit_threshold"]:
            return ThreatDetection(
                threat_type=ThreatType.RATE_LIMIT_VIOLATION,
                threat_level=ThreatLevel.MEDIUM,
                confidence=0.7,
                description=f"Violation de rate limit depuis {context.ip_address}",
                evidence={
                    "requests_per_minute": len(requests),
                    "threshold": self.config["rate_limit_threshold"]
                },
                recommended_actions=["throttle_requests", "temporary_block", "log_incident"]
            )
        
        return None
    
    async def _detect_malicious_user_agent(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les User-Agents malveillants."""
        if not context.user_agent:
            return None
        
        user_agent_lower = context.user_agent.lower()
        
        for malicious_ua in self.malicious_user_agents:
            if malicious_ua in user_agent_lower:
                return ThreatDetection(
                    threat_type=ThreatType.MALICIOUS_PAYLOAD,
                    threat_level=ThreatLevel.HIGH,
                    confidence=0.9,
                    description=f"User-Agent malveillant détecté: {malicious_ua}",
                    evidence={
                        "user_agent": context.user_agent,
                        "detected_tool": malicious_ua
                    },
                    recommended_actions=["block_request", "block_ip", "alert_admin"]
                )
        
        return None
    
    async def _detect_suspicious_location(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les connexions depuis des localisations suspectes."""
        if not context.user_id:
            return None
        
        # Simulation de géolocalisation
        current_location = await self._get_ip_location(context.ip_address)
        
        # Vérification des localisations précédentes
        user_locations = self.known_locations.get(context.user_id, set())
        
        if user_locations and current_location not in user_locations:
            # Nouvelle localisation
            if len(user_locations) > 0:
                return ThreatDetection(
                    threat_type=ThreatType.SUSPICIOUS_LOCATION,
                    threat_level=ThreatLevel.MEDIUM,
                    confidence=0.6,
                    description=f"Connexion depuis une nouvelle localisation: {current_location}",
                    evidence={
                        "current_location": current_location,
                        "known_locations": list(user_locations),
                        "user_id": context.user_id
                    },
                    recommended_actions=["require_2fa", "notify_user", "log_incident"]
                )
        
        # Mise à jour des localisations connues
        if context.user_id not in self.known_locations:
            self.known_locations[context.user_id] = set()
        self.known_locations[context.user_id].add(current_location)
        
        return None
    
    async def _detect_malicious_payload(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les payloads malveillants."""
        if not context.payload:
            return None
        
        # Vérification de la taille
        if len(context.payload) > self.config["max_payload_size"]:
            return ThreatDetection(
                threat_type=ThreatType.MALICIOUS_PAYLOAD,
                threat_level=ThreatLevel.MEDIUM,
                confidence=0.5,
                description="Payload anormalement volumineux",
                evidence={
                    "payload_size": len(context.payload),
                    "max_size": self.config["max_payload_size"]
                },
                recommended_actions=["limit_payload_size", "log_incident"]
            )
        
        # Détection de caractères suspects
        suspicious_chars = ['<', '>', '"', "'", '&', '%', ';', '|', '`', '$']
        suspicious_count = sum(1 for char in suspicious_chars if char in context.payload)
        
        if suspicious_count > 5:
            return ThreatDetection(
                threat_type=ThreatType.MALICIOUS_PAYLOAD,
                threat_level=ThreatLevel.MEDIUM,
                confidence=min(0.8, suspicious_count * 0.1),
                description="Payload contenant des caractères suspects",
                evidence={
                    "suspicious_chars_count": suspicious_count,
                    "payload_preview": context.payload[:100]
                },
                recommended_actions=["sanitize_input", "validate_payload", "log_incident"]
            )
        
        return None
    
    async def _detect_anomalous_behavior(self, context: SecurityContext) -> Optional[ThreatDetection]:
        """Détecte les comportements anormaux."""
        if not context.user_id:
            return None
        
        # Analyse des patterns de requêtes
        requests = self.request_history[context.ip_address]
        
        if len(requests) < 10:
            return None  # Pas assez de données
        
        # Calcul de l'entropie des endpoints
        endpoints = [req.get('endpoint', '') for req in list(requests)[-10:]]
        unique_endpoints = len(set(endpoints))
        
        # Comportement suspect : trop d'endpoints différents
        if unique_endpoints > 8:
            return ThreatDetection(
                threat_type=ThreatType.ANOMALOUS_BEHAVIOR,
                threat_level=ThreatLevel.MEDIUM,
                confidence=0.6,
                description="Comportement anormal: exploration d'endpoints",
                evidence={
                    "unique_endpoints": unique_endpoints,
                    "total_requests": len(requests),
                    "endpoints": list(set(endpoints))
                },
                recommended_actions=["monitor_closely", "rate_limit", "log_incident"]
            )
        
        return None
    
    async def _get_ip_location(self, ip_address: str) -> str:
        """Obtient la localisation d'une adresse IP."""
        # Simulation de géolocalisation
        try:
            ip = ipaddress.ip_address(ip_address)
            if ip.is_private:
                return "Local"
            elif ip_address.startswith("127."):
                return "Localhost"
            else:
                # Hash de l'IP pour une localisation cohérente
                hash_obj = hashlib.md5(ip_address.encode())
                hash_int = int(hash_obj.hexdigest()[:8], 16)
                
                countries = ["FR", "US", "GB", "DE", "ES", "IT", "CA", "AU"]
                return countries[hash_int % len(countries)]
        except:
            return "Unknown"
    
    def _is_ip_blocked(self, ip_address: str) -> bool:
        """Vérifie si une IP est bloquée."""
        if ip_address in self.blocked_ips:
            if time.time() < self.blocked_ips[ip_address]:
                return True
            else:
                # Déblocage automatique
                del self.blocked_ips[ip_address]
        return False
    
    def _update_request_history(self, context: SecurityContext):
        """Met à jour l'historique des requêtes."""
        request_data = {
            'timestamp': time.time(),
            'endpoint': context.endpoint,
            'method': context.method,
            'user_id': context.user_id
        }
        
        self.request_history[context.ip_address].append(request_data)
        
        # Limitation de la taille de l'historique
        if len(self.request_history[context.ip_address]) > 1000:
            self.request_history[context.ip_address].popleft()
    
    def record_failed_attempt(self, ip_address: str):
        """Enregistre une tentative d'authentification échouée."""
        self.failed_attempts[ip_address].append(time.time())
        
        # Limitation de la taille
        if len(self.failed_attempts[ip_address]) > 20:
            self.failed_attempts[ip_address].popleft()
    
    def get_threat_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques des menaces."""
        return {
            "blocked_ips": len(self.blocked_ips),
            "monitored_ips": len(self.request_history),
            "failed_attempts_tracked": len(self.failed_attempts),
            "known_user_locations": len(self.known_locations),
            "config": self.config
        }
    
    def unblock_ip(self, ip_address: str) -> bool:
        """Débloque manuellement une IP."""
        if ip_address in self.blocked_ips:
            del self.blocked_ips[ip_address]
            return True
        return False
    
    def add_legitimate_pattern(self, pattern: str):
        """Ajoute un pattern d'utilisateur légitime."""
        self.legitimate_patterns.add(pattern)
    
    def update_config(self, **kwargs):
        """Met à jour la configuration."""
        for key, value in kwargs.items():
            if key in self.config:
                self.config[key] = value


# Instance globale du détecteur de menaces
_threat_detector: Optional[ThreatDetector] = None


def get_threat_detector() -> ThreatDetector:
    """Retourne l'instance globale du détecteur de menaces."""
    global _threat_detector
    
    if _threat_detector is None:
        _threat_detector = ThreatDetector()
    
    return _threat_detector


async def analyze_security_context(context: SecurityContext) -> List[ThreatDetection]:
    """Fonction utilitaire pour analyser un contexte de sécurité."""
    detector = get_threat_detector()
    return await detector.analyze_request(context)

