"""
Système de logs d'audit pour l'application VTC.
"""

import json
import logging
import asyncio
import threading
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import gzip
import os
from cryptography.fernet import Fernet
import hashlib
import hmac

from .audit_events import AuditEvent, AuditEventType, AuditSeverity


class AuditLogger:
    """Logger d'audit sécurisé et performant."""
    
    def __init__(
        self,
        log_directory: str = "/var/log/vtc_audit",
        encryption_key: Optional[str] = None,
        max_file_size: int = 100 * 1024 * 1024,  # 100MB
        retention_days: int = 365,
        compress_after_days: int = 7,
        enable_encryption: bool = True,
        enable_integrity_check: bool = True
    ):
        """
        Initialise le logger d'audit.
        
        Args:
            log_directory: Répertoire des logs
            encryption_key: Clé de chiffrement (générée si None)
            max_file_size: Taille max des fichiers de log
            retention_days: Durée de rétention des logs
            compress_after_days: Compression après X jours
            enable_encryption: Activer le chiffrement
            enable_integrity_check: Activer la vérification d'intégrité
        """
        self.log_directory = Path(log_directory)
        self.max_file_size = max_file_size
        self.retention_days = retention_days
        self.compress_after_days = compress_after_days
        self.enable_encryption = enable_encryption
        self.enable_integrity_check = enable_integrity_check
        
        # Création du répertoire
        self.log_directory.mkdir(parents=True, exist_ok=True)
        
        # Configuration du chiffrement
        if self.enable_encryption:
            if encryption_key:
                self.encryption_key = encryption_key.encode()
            else:
                self.encryption_key = Fernet.generate_key()
            self.cipher = Fernet(self.encryption_key)
        
        # Configuration de l'intégrité
        if self.enable_integrity_check:
            self.integrity_key = os.urandom(32)
        
        # Pool de threads pour les opérations asynchrones
        self.executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="audit_logger")
        
        # Cache des événements en attente
        self._event_queue = asyncio.Queue(maxsize=1000)
        self._processing_task = None
        
        # Statistiques
        self.stats = {
            "events_logged": 0,
            "events_failed": 0,
            "files_created": 0,
            "files_compressed": 0,
            "files_deleted": 0
        }
        
        # Configuration du logger Python standard
        self._setup_standard_logger()
        
        # Démarrage du processeur d'événements
        self._start_event_processor()
    
    def _setup_standard_logger(self):
        """Configure le logger Python standard pour les logs d'audit."""
        self.logger = logging.getLogger("vtc_audit")
        self.logger.setLevel(logging.INFO)
        
        # Handler pour fichier non chiffré (logs système)
        system_log_file = self.log_directory / "audit_system.log"
        handler = logging.FileHandler(system_log_file)
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
    
    def _start_event_processor(self):
        """Démarre le processeur d'événements asynchrone."""
        if self._processing_task is None or self._processing_task.done():
            self._processing_task = asyncio.create_task(self._process_events())
    
    async def _process_events(self):
        """Traite les événements d'audit en arrière-plan."""
        while True:
            try:
                # Récupération d'un événement avec timeout
                event = await asyncio.wait_for(
                    self._event_queue.get(),
                    timeout=1.0
                )
                
                # Traitement de l'événement
                await self._write_event_to_file(event)
                self.stats["events_logged"] += 1
                
                # Marquer la tâche comme terminée
                self._event_queue.task_done()
                
            except asyncio.TimeoutError:
                # Pas d'événement, vérifier la maintenance
                await self._perform_maintenance()
                
            except Exception as e:
                self.logger.error(f"Erreur lors du traitement d'événement: {e}")
                self.stats["events_failed"] += 1
    
    async def log_event(self, event: AuditEvent) -> bool:
        """
        Enregistre un événement d'audit de manière asynchrone.
        
        Args:
            event: Événement d'audit à enregistrer
            
        Returns:
            True si l'événement a été mis en queue, False sinon
        """
        try:
            # Validation de l'événement
            if not self._validate_event(event):
                return False
            
            # Enrichissement de l'événement
            enriched_event = await self._enrich_event(event)
            
            # Mise en queue pour traitement asynchrone
            await self._event_queue.put(enriched_event)
            return True
            
        except Exception as e:
            self.logger.error(f"Erreur lors de l'enregistrement d'événement: {e}")
            return False
    
    def _validate_event(self, event: AuditEvent) -> bool:
        """Valide un événement d'audit."""
        try:
            # Validation des champs obligatoires
            if not event.event_type or not event.action:
                return False
            
            # Validation du score de risque
            if not (0.0 <= event.risk_score <= 1.0):
                return False
            
            return True
            
        except Exception:
            return False
    
    async def _enrich_event(self, event: AuditEvent) -> AuditEvent:
        """Enrichit un événement avec des métadonnées supplémentaires."""
        # Ajout de métadonnées système
        event.details.update({
            "hostname": os.uname().nodename,
            "process_id": os.getpid(),
            "thread_id": threading.get_ident() if hasattr(threading, 'get_ident') else 0
        })
        
        # Géolocalisation IP (simulation)
        if event.ip_address and not event.location:
            event.location = await self._get_ip_location(event.ip_address)
        
        return event
    
    async def _get_ip_location(self, ip_address: str) -> Dict[str, str]:
        """Obtient la géolocalisation d'une adresse IP."""
        # Simulation de géolocalisation
        # En production, utiliser un service comme MaxMind GeoIP
        if ip_address.startswith("192.168.") or ip_address.startswith("10."):
            return {"country": "FR", "city": "Paris", "region": "Île-de-France"}
        
        return {"country": "Unknown", "city": "Unknown", "region": "Unknown"}
    
    async def _write_event_to_file(self, event: AuditEvent):
        """Écrit un événement dans le fichier de log approprié."""
        # Détermination du fichier de log
        log_file = self._get_log_file(event)
        
        # Sérialisation de l'événement
        event_data = self._serialize_event(event)
        
        # Écriture dans le fichier
        await self._write_to_file(log_file, event_data)
        
        # Log système pour les événements critiques
        if event.severity in [AuditSeverity.HIGH, AuditSeverity.CRITICAL]:
            self.logger.warning(f"Événement critique: {event.event_type} - {event.action}")
    
    def _get_log_file(self, event: AuditEvent) -> Path:
        """Détermine le fichier de log pour un événement."""
        date_str = event.timestamp.strftime("%Y-%m-%d")
        
        # Extraction sécurisée du type d'événement
        if hasattr(event.event_type, 'value'):
            event_type_str = event.event_type.value
        else:
            event_type_str = str(event.event_type)
        
        # Fichiers séparés par type d'événement
        if event_type_str.startswith("auth_"):
            filename = f"audit_auth_{date_str}.log"
        elif event_type_str.startswith("security_"):
            filename = f"audit_security_{date_str}.log"
        elif event_type_str.startswith("gdpr_"):
            filename = f"audit_gdpr_{date_str}.log"
        elif event_type_str.startswith("vtc_"):
            filename = f"audit_vtc_{date_str}.log"
        else:
            filename = f"audit_general_{date_str}.log"
        
        return self.log_directory / filename
    
    def _serialize_event(self, event: AuditEvent) -> str:
        """Sérialise un événement en JSON."""
        event_dict = event.dict()
        
        # Ajout de la signature d'intégrité
        if self.enable_integrity_check:
            event_dict["integrity_hash"] = self._calculate_integrity_hash(event_dict)
        
        return json.dumps(event_dict, ensure_ascii=False, separators=(',', ':'))
    
    def _calculate_integrity_hash(self, event_dict: Dict[str, Any]) -> str:
        """Calcule le hash d'intégrité d'un événement."""
        # Création d'une représentation canonique
        canonical = json.dumps(event_dict, sort_keys=True, separators=(',', ':'))
        
        # Calcul du HMAC
        signature = hmac.new(
            self.integrity_key,
            canonical.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return signature
    
    async def _write_to_file(self, log_file: Path, data: str):
        """Écrit des données dans un fichier de log."""
        def _write():
            # Vérification de la rotation
            if log_file.exists() and log_file.stat().st_size > self.max_file_size:
                self._rotate_log_file(log_file)
            
            # Écriture des données
            content = data + "\n"
            
            if self.enable_encryption:
                # Chiffrement des données sensibles
                if self._is_sensitive_event(data):
                    content = self.cipher.encrypt(content.encode()).decode('latin1')
                    content += "\n"
            
            with open(log_file, 'a', encoding='utf-8') as f:
                f.write(content)
                f.flush()
                os.fsync(f.fileno())  # Force l'écriture sur disque
        
        # Exécution dans le pool de threads
        await asyncio.get_event_loop().run_in_executor(self.executor, _write)
    
    def _is_sensitive_event(self, data: str) -> bool:
        """Détermine si un événement contient des données sensibles."""
        sensitive_keywords = [
            "password", "token", "secret", "key", "credit_card",
            "ssn", "personal_data", "sensitive"
        ]
        
        data_lower = data.lower()
        return any(keyword in data_lower for keyword in sensitive_keywords)
    
    def _rotate_log_file(self, log_file: Path):
        """Effectue la rotation d'un fichier de log."""
        timestamp = datetime.now().strftime("%H%M%S")
        rotated_file = log_file.with_suffix(f".{timestamp}.log")
        
        try:
            log_file.rename(rotated_file)
            self.stats["files_created"] += 1
            self.logger.info(f"Rotation du fichier de log: {rotated_file}")
        except Exception as e:
            self.logger.error(f"Erreur lors de la rotation: {e}")
    
    async def _perform_maintenance(self):
        """Effectue la maintenance des fichiers de log."""
        try:
            await self._compress_old_files()
            await self._cleanup_old_files()
        except Exception as e:
            self.logger.error(f"Erreur lors de la maintenance: {e}")
    
    async def _compress_old_files(self):
        """Compresse les anciens fichiers de log."""
        cutoff_date = datetime.now() - timedelta(days=self.compress_after_days)
        
        for log_file in self.log_directory.glob("*.log"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                await self._compress_file(log_file)
    
    async def _compress_file(self, log_file: Path):
        """Compresse un fichier de log."""
        def _compress():
            compressed_file = log_file.with_suffix('.log.gz')
            
            with open(log_file, 'rb') as f_in:
                with gzip.open(compressed_file, 'wb') as f_out:
                    f_out.writelines(f_in)
            
            log_file.unlink()  # Suppression du fichier original
            self.stats["files_compressed"] += 1
        
        await asyncio.get_event_loop().run_in_executor(self.executor, _compress)
    
    async def _cleanup_old_files(self):
        """Supprime les anciens fichiers de log."""
        cutoff_date = datetime.now() - timedelta(days=self.retention_days)
        
        for log_file in self.log_directory.glob("*.gz"):
            if log_file.stat().st_mtime < cutoff_date.timestamp():
                log_file.unlink()
                self.stats["files_deleted"] += 1
    
    async def search_events(
        self,
        start_date: datetime = None,
        end_date: datetime = None,
        event_types: List[AuditEventType] = None,
        user_id: str = None,
        severity: AuditSeverity = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """
        Recherche des événements d'audit.
        
        Args:
            start_date: Date de début
            end_date: Date de fin
            event_types: Types d'événements
            user_id: ID utilisateur
            severity: Niveau de sévérité
            limit: Nombre max de résultats
            
        Returns:
            Liste des événements trouvés
        """
        events = []
        
        # Détermination des fichiers à analyser
        files_to_search = self._get_files_for_date_range(start_date, end_date)
        
        for log_file in files_to_search:
            file_events = await self._search_in_file(
                log_file, event_types, user_id, severity, limit - len(events)
            )
            events.extend(file_events)
            
            if len(events) >= limit:
                break
        
        return events[:limit]
    
    def _get_files_for_date_range(
        self,
        start_date: datetime = None,
        end_date: datetime = None
    ) -> List[Path]:
        """Obtient les fichiers de log pour une plage de dates."""
        if not start_date:
            start_date = datetime.now() - timedelta(days=7)
        if not end_date:
            end_date = datetime.now()
        
        files = []
        current_date = start_date.date()
        
        while current_date <= end_date.date():
            date_str = current_date.strftime("%Y-%m-%d")
            
            # Recherche de tous les fichiers pour cette date
            for pattern in ["audit_*_{}.log", "audit_*_{}.*.log", "audit_*_{}.log.gz"]:
                files.extend(self.log_directory.glob(pattern.format(date_str)))
            
            current_date += timedelta(days=1)
        
        return sorted(files)
    
    async def _search_in_file(
        self,
        log_file: Path,
        event_types: List[AuditEventType] = None,
        user_id: str = None,
        severity: AuditSeverity = None,
        limit: int = 100
    ) -> List[AuditEvent]:
        """Recherche des événements dans un fichier."""
        def _search():
            events = []
            
            try:
                # Ouverture du fichier (gzip ou normal)
                if log_file.suffix == '.gz':
                    file_obj = gzip.open(log_file, 'rt', encoding='utf-8')
                else:
                    file_obj = open(log_file, 'r', encoding='utf-8')
                
                with file_obj as f:
                    for line in f:
                        if len(events) >= limit:
                            break
                        
                        try:
                            # Déchiffrement si nécessaire
                            if self.enable_encryption and self._is_encrypted_line(line):
                                line = self._decrypt_line(line)
                            
                            # Parsing JSON
                            event_data = json.loads(line.strip())
                            event = AuditEvent(**event_data)
                            
                            # Filtrage
                            if self._matches_filters(event, event_types, user_id, severity):
                                events.append(event)
                                
                        except Exception:
                            continue  # Ligne invalide, ignorer
                
            except Exception as e:
                self.logger.error(f"Erreur lors de la recherche dans {log_file}: {e}")
            
            return events
        
        return await asyncio.get_event_loop().run_in_executor(self.executor, _search)
    
    def _is_encrypted_line(self, line: str) -> bool:
        """Détermine si une ligne est chiffrée."""
        # Heuristique simple : les lignes chiffrées ne sont pas du JSON valide
        try:
            json.loads(line.strip())
            return False
        except:
            return True
    
    def _decrypt_line(self, line: str) -> str:
        """Déchiffre une ligne."""
        try:
            encrypted_data = line.strip().encode('latin1')
            decrypted_data = self.cipher.decrypt(encrypted_data)
            return decrypted_data.decode('utf-8')
        except Exception:
            return line  # Retourner la ligne originale si le déchiffrement échoue
    
    def _matches_filters(
        self,
        event: AuditEvent,
        event_types: List[AuditEventType] = None,
        user_id: str = None,
        severity: AuditSeverity = None
    ) -> bool:
        """Vérifie si un événement correspond aux filtres."""
        if event_types and event.event_type not in event_types:
            return False
        
        if user_id and event.user_id != user_id:
            return False
        
        if severity and event.severity != severity:
            return False
        
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Retourne les statistiques du logger."""
        return {
            **self.stats,
            "queue_size": self._event_queue.qsize(),
            "log_directory": str(self.log_directory),
            "encryption_enabled": self.enable_encryption,
            "integrity_check_enabled": self.enable_integrity_check
        }
    
    async def close(self):
        """Ferme le logger d'audit."""
        # Attendre que tous les événements soient traités
        await self._event_queue.join()
        
        # Arrêter le processeur d'événements
        if self._processing_task:
            self._processing_task.cancel()
            try:
                await self._processing_task
            except asyncio.CancelledError:
                pass
        
        # Fermer le pool de threads
        self.executor.shutdown(wait=True)


# Instance globale du logger d'audit
_audit_logger: Optional[AuditLogger] = None


def get_audit_logger() -> AuditLogger:
    """Retourne l'instance globale du logger d'audit."""
    global _audit_logger
    
    if _audit_logger is None:
        # Configuration par défaut
        _audit_logger = AuditLogger(
            log_directory=os.getenv("AUDIT_LOG_DIRECTORY", "/var/log/vtc_audit"),
            encryption_key=os.getenv("AUDIT_ENCRYPTION_KEY"),
            enable_encryption=os.getenv("AUDIT_ENABLE_ENCRYPTION", "true").lower() == "true",
            enable_integrity_check=os.getenv("AUDIT_ENABLE_INTEGRITY", "true").lower() == "true"
        )
    
    return _audit_logger


async def log_audit_event(event: AuditEvent) -> bool:
    """Fonction utilitaire pour enregistrer un événement d'audit."""
    logger = get_audit_logger()
    return await logger.log_event(event)

