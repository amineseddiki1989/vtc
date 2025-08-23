"""
Service de chiffrement pour les données sensibles de l'application VTC.
Chiffrement AES-256-GCM pour les données au repos et en transit.
"""

import os
import base64
import secrets
import logging
from typing import Optional, Dict, Any, Union
from datetime import datetime, timezone
from enum import Enum

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.backends import default_backend
from pydantic import BaseModel, Field

from ..config.settings import get_settings

logger = logging.getLogger(__name__)


class EncryptionLevel(str, Enum):
    """Niveaux de chiffrement selon la sensibilité des données."""
    LOW = "low"          # Données publiques ou peu sensibles
    MEDIUM = "medium"    # Données personnelles standard
    HIGH = "high"        # Données financières, médicales
    CRITICAL = "critical" # Données ultra-sensibles (mots de passe, tokens)


class EncryptedData(BaseModel):
    """Modèle pour les données chiffrées."""
    encrypted_value: str = Field(..., description="Valeur chiffrée en base64")
    encryption_level: EncryptionLevel = Field(..., description="Niveau de chiffrement utilisé")
    algorithm: str = Field(..., description="Algorithme de chiffrement")
    key_id: Optional[str] = Field(None, description="Identifiant de la clé utilisée")
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = Field(default_factory=dict)


class EncryptionService:
    """Service de chiffrement avancé pour données sensibles."""
    
    def __init__(self):
        self.settings = get_settings()
        self._master_key = self._get_master_key()
        self._fernet = Fernet(self._master_key)
        self._aes_gcm = AESGCM(self._get_aes_key())
        
        # Cache des clés dérivées pour optimiser les performances
        self._derived_keys_cache: Dict[str, bytes] = {}
        
        logger.info("Service de chiffrement initialisé")
    
    def _get_master_key(self) -> bytes:
        """Récupère ou génère la clé maître de chiffrement."""
        master_key_env = os.getenv("ENCRYPTION_MASTER_KEY")
        
        if master_key_env:
            try:
                # Décoder la clé depuis l'environnement
                return base64.urlsafe_b64decode(master_key_env.encode())
            except Exception as e:
                logger.error(f"Erreur lors du décodage de la clé maître: {e}")
                raise ValueError("Clé maître invalide dans ENCRYPTION_MASTER_KEY")
        
        # En développement, générer une clé temporaire
        if not self.settings.is_production:
            logger.warning("Génération d'une clé maître temporaire pour le développement")
            return Fernet.generate_key()
        
        # En production, la clé doit être fournie
        raise ValueError(
            "ENCRYPTION_MASTER_KEY doit être définie en production. "
            "Générez une clé avec: python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    
    def _get_aes_key(self) -> bytes:
        """Récupère la clé AES-256 pour le chiffrement AEAD."""
        aes_key_env = os.getenv("AES_ENCRYPTION_KEY")
        
        if aes_key_env:
            try:
                key = base64.urlsafe_b64decode(aes_key_env.encode())
                if len(key) != 32:  # AES-256 nécessite 32 bytes
                    raise ValueError("La clé AES doit faire 32 bytes (256 bits)")
                return key
            except Exception as e:
                logger.error(f"Erreur lors du décodage de la clé AES: {e}")
                raise ValueError("Clé AES invalide dans AES_ENCRYPTION_KEY")
        
        # En développement, générer une clé temporaire
        if not self.settings.is_production:
            logger.warning("Génération d'une clé AES temporaire pour le développement")
            return secrets.token_bytes(32)
        
        # En production, la clé doit être fournie
        raise ValueError(
            "AES_ENCRYPTION_KEY doit être définie en production. "
            "Générez une clé avec: python -c 'import secrets, base64; print(base64.urlsafe_b64encode(secrets.token_bytes(32)).decode())'"
        )
    
    def _derive_key(self, context: str, salt: Optional[bytes] = None) -> bytes:
        """Dérive une clé spécifique au contexte."""
        if context in self._derived_keys_cache:
            return self._derived_keys_cache[context]
        
        if salt is None:
            salt = context.encode('utf-8')[:16].ljust(16, b'\x00')
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        derived_key = kdf.derive(self._master_key)
        self._derived_keys_cache[context] = derived_key
        
        return derived_key
    
    def encrypt_sensitive_data(
        self,
        data: Union[str, bytes, Dict[str, Any]],
        level: EncryptionLevel = EncryptionLevel.MEDIUM,
        context: Optional[str] = None
    ) -> EncryptedData:
        """
        Chiffre des données sensibles selon le niveau de sécurité requis.
        
        Args:
            data: Données à chiffrer
            level: Niveau de chiffrement
            context: Contexte pour la dérivation de clé
        
        Returns:
            EncryptedData: Données chiffrées avec métadonnées
        """
        try:
            # Convertir en bytes si nécessaire
            if isinstance(data, dict):
                import json
                data_bytes = json.dumps(data, ensure_ascii=False).encode('utf-8')
            elif isinstance(data, str):
                data_bytes = data.encode('utf-8')
            else:
                data_bytes = data
            
            # Choisir l'algorithme selon le niveau
            if level in [EncryptionLevel.HIGH, EncryptionLevel.CRITICAL]:
                # AES-GCM pour les données très sensibles
                encrypted_value, algorithm, key_id = self._encrypt_aes_gcm(data_bytes, context)
            else:
                # Fernet pour les données standard
                encrypted_value, algorithm, key_id = self._encrypt_fernet(data_bytes, context)
            
            return EncryptedData(
                encrypted_value=encrypted_value,
                encryption_level=level,
                algorithm=algorithm,
                key_id=key_id,
                metadata={
                    "original_type": type(data).__name__,
                    "context": context,
                    "encrypted_at": datetime.now(timezone.utc).isoformat()
                }
            )
            
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement: {e}")
            raise ValueError(f"Impossible de chiffrer les données: {e}")
    
    def decrypt_sensitive_data(
        self,
        encrypted_data: EncryptedData,
        expected_type: Optional[type] = None
    ) -> Union[str, bytes, Dict[str, Any]]:
        """
        Déchiffre des données sensibles.
        
        Args:
            encrypted_data: Données chiffrées
            expected_type: Type attendu pour validation
        
        Returns:
            Données déchiffrées dans leur format original
        """
        try:
            # Déchiffrer selon l'algorithme
            if encrypted_data.algorithm == "AES-GCM":
                data_bytes = self._decrypt_aes_gcm(
                    encrypted_data.encrypted_value,
                    encrypted_data.metadata.get("context")
                )
            elif encrypted_data.algorithm == "Fernet":
                data_bytes = self._decrypt_fernet(
                    encrypted_data.encrypted_value,
                    encrypted_data.metadata.get("context")
                )
            else:
                raise ValueError(f"Algorithme non supporté: {encrypted_data.algorithm}")
            
            # Reconvertir dans le type original
            original_type = encrypted_data.metadata.get("original_type", "str")
            
            if original_type == "dict":
                import json
                return json.loads(data_bytes.decode('utf-8'))
            elif original_type == "str":
                return data_bytes.decode('utf-8')
            else:
                return data_bytes
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement: {e}")
            raise ValueError(f"Impossible de déchiffrer les données: {e}")
    
    def _encrypt_fernet(self, data: bytes, context: Optional[str] = None) -> tuple[str, str, str]:
        """Chiffrement Fernet (AES-128 en mode CBC)."""
        if context:
            # Utiliser une clé dérivée pour le contexte
            derived_key = self._derive_key(context)
            fernet = Fernet(base64.urlsafe_b64encode(derived_key))
            encrypted = fernet.encrypt(data)
            key_id = f"derived_{context}"
        else:
            encrypted = self._fernet.encrypt(data)
            key_id = "master"
        
        return base64.urlsafe_b64encode(encrypted).decode(), "Fernet", key_id
    
    def _decrypt_fernet(self, encrypted_data: str, context: Optional[str] = None) -> bytes:
        """Déchiffrement Fernet."""
        encrypted_bytes = base64.urlsafe_b64decode(encrypted_data.encode())
        
        if context:
            derived_key = self._derive_key(context)
            fernet = Fernet(base64.urlsafe_b64encode(derived_key))
            return fernet.decrypt(encrypted_bytes)
        else:
            return self._fernet.decrypt(encrypted_bytes)
    
    def _encrypt_aes_gcm(self, data: bytes, context: Optional[str] = None) -> tuple[str, str, str]:
        """Chiffrement AES-GCM (authentifié)."""
        # Générer un nonce unique
        nonce = secrets.token_bytes(12)  # 96 bits pour AES-GCM
        
        # Utiliser la clé appropriée
        if context:
            key = self._derive_key(context)
            key_id = f"derived_{context}"
        else:
            key = self._get_aes_key()
            key_id = "aes_master"
        
        # Chiffrer avec authentification
        aes_gcm = AESGCM(key)
        ciphertext = aes_gcm.encrypt(nonce, data, None)
        
        # Combiner nonce + ciphertext
        combined = nonce + ciphertext
        
        return base64.urlsafe_b64encode(combined).decode(), "AES-GCM", key_id
    
    def _decrypt_aes_gcm(self, encrypted_data: str, context: Optional[str] = None) -> bytes:
        """Déchiffrement AES-GCM."""
        combined = base64.urlsafe_b64decode(encrypted_data.encode())
        
        # Séparer nonce et ciphertext
        nonce = combined[:12]
        ciphertext = combined[12:]
        
        # Utiliser la clé appropriée
        if context:
            key = self._derive_key(context)
        else:
            key = self._get_aes_key()
        
        # Déchiffrer et vérifier l'authenticité
        aes_gcm = AESGCM(key)
        return aes_gcm.decrypt(nonce, ciphertext, None)
    
    def encrypt_field(self, value: str, field_name: str, level: EncryptionLevel = EncryptionLevel.MEDIUM) -> str:
        """
        Chiffre un champ spécifique pour stockage en base de données.
        
        Args:
            value: Valeur à chiffrer
            field_name: Nom du champ (utilisé comme contexte)
            level: Niveau de chiffrement
        
        Returns:
            Valeur chiffrée encodée en base64
        """
        if not value:
            return value
        
        encrypted_data = self.encrypt_sensitive_data(value, level, field_name)
        
        # Encoder pour stockage en base
        import json
        return base64.urlsafe_b64encode(
            json.dumps(encrypted_data.dict()).encode('utf-8')
        ).decode()
    
    def decrypt_field(self, encrypted_value: str, field_name: str) -> str:
        """
        Déchiffre un champ depuis la base de données.
        
        Args:
            encrypted_value: Valeur chiffrée
            field_name: Nom du champ
        
        Returns:
            Valeur déchiffrée
        """
        if not encrypted_value:
            return encrypted_value
        
        try:
            # Décoder depuis la base
            import json
            data_dict = json.loads(
                base64.urlsafe_b64decode(encrypted_value.encode()).decode('utf-8')
            )
            
            encrypted_data = EncryptedData(**data_dict)
            return self.decrypt_sensitive_data(encrypted_data)
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement du champ {field_name}: {e}")
            # En cas d'erreur, retourner la valeur telle quelle (migration)
            return encrypted_value
    
    def rotate_keys(self) -> Dict[str, Any]:
        """
        Rotation des clés de chiffrement (pour maintenance de sécurité).
        
        Returns:
            Rapport de rotation
        """
        logger.warning("Rotation des clés de chiffrement demandée")
        
        # Vider le cache des clés dérivées
        old_cache_size = len(self._derived_keys_cache)
        self._derived_keys_cache.clear()
        
        # En production, il faudrait:
        # 1. Générer de nouvelles clés
        # 2. Re-chiffrer toutes les données avec les nouvelles clés
        # 3. Mettre à jour les variables d'environnement
        # 4. Redémarrer l'application
        
        return {
            "status": "cache_cleared",
            "old_cache_size": old_cache_size,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "warning": "Rotation complète nécessite redéploiement avec nouvelles clés"
        }
    
    def get_encryption_stats(self) -> Dict[str, Any]:
        """Statistiques du service de chiffrement."""
        return {
            "service_status": "active",
            "algorithms_available": ["Fernet", "AES-GCM"],
            "derived_keys_cached": len(self._derived_keys_cache),
            "master_key_configured": bool(os.getenv("ENCRYPTION_MASTER_KEY")),
            "aes_key_configured": bool(os.getenv("AES_ENCRYPTION_KEY")),
            "production_mode": self.settings.is_production
        }


# Instance globale du service
_encryption_service: Optional[EncryptionService] = None


def get_encryption_service() -> EncryptionService:
    """Récupère l'instance du service de chiffrement."""
    global _encryption_service
    if _encryption_service is None:
        _encryption_service = EncryptionService()
    return _encryption_service


# Fonctions utilitaires pour les modèles SQLAlchemy
def encrypt_personal_data(value: str) -> str:
    """Chiffre des données personnelles (nom, adresse, etc.)."""
    if not value:
        return value
    service = get_encryption_service()
    return service.encrypt_field(value, "personal_data", EncryptionLevel.MEDIUM)


def decrypt_personal_data(encrypted_value: str) -> str:
    """Déchiffre des données personnelles."""
    if not encrypted_value:
        return encrypted_value
    service = get_encryption_service()
    return service.decrypt_field(encrypted_value, "personal_data")


def encrypt_financial_data(value: str) -> str:
    """Chiffre des données financières."""
    if not value:
        return value
    service = get_encryption_service()
    return service.encrypt_field(value, "financial_data", EncryptionLevel.HIGH)


def decrypt_financial_data(encrypted_value: str) -> str:
    """Déchiffre des données financières."""
    if not encrypted_value:
        return encrypted_value
    service = get_encryption_service()
    return service.decrypt_field(encrypted_value, "financial_data")


def encrypt_sensitive_data(value: str) -> str:
    """Chiffre des données ultra-sensibles."""
    if not value:
        return value
    service = get_encryption_service()
    return service.encrypt_field(value, "sensitive_data", EncryptionLevel.CRITICAL)


def decrypt_sensitive_data(encrypted_value: str) -> str:
    """Déchiffre des données ultra-sensibles."""
    if not encrypted_value:
        return encrypted_value
    service = get_encryption_service()
    return service.decrypt_field(encrypted_value, "sensitive_data")

