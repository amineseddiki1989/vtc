"""
Gestionnaire de consentements RGPD pour l'application VTC.
Module d'amélioration VTC pour la conformité RGPD complète.
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List, Set
from pydantic import BaseModel, Field
from enum import Enum
import json
import logging

logger = logging.getLogger(__name__)


class ConsentType(str, Enum):
    """Types de consentements RGPD."""
    ESSENTIAL = "essential"  # Cookies essentiels
    ANALYTICS = "analytics"  # Cookies d'analyse
    MARKETING = "marketing"  # Cookies marketing
    PERSONALIZATION = "personalization"  # Personnalisation
    GEOLOCATION = "geolocation"  # Géolocalisation
    COMMUNICATION = "communication"  # Communications marketing
    DATA_SHARING = "data_sharing"  # Partage de données avec tiers


class ConsentStatus(str, Enum):
    """Statuts de consentement."""
    GRANTED = "granted"
    DENIED = "denied"
    WITHDRAWN = "withdrawn"
    EXPIRED = "expired"
    PENDING = "pending"


class DataProcessingPurpose(str, Enum):
    """Finalités de traitement des données."""
    SERVICE_PROVISION = "service_provision"  # Fourniture du service
    TRIP_MANAGEMENT = "trip_management"  # Gestion des courses
    PAYMENT_PROCESSING = "payment_processing"  # Traitement des paiements
    CUSTOMER_SUPPORT = "customer_support"  # Support client
    SAFETY_SECURITY = "safety_security"  # Sécurité et sûreté
    LEGAL_COMPLIANCE = "legal_compliance"  # Conformité légale
    ANALYTICS_IMPROVEMENT = "analytics_improvement"  # Analyses et améliorations
    MARKETING_COMMUNICATION = "marketing_communication"  # Marketing


class LegalBasis(str, Enum):
    """Bases légales RGPD."""
    CONSENT = "consent"  # Consentement (Art. 6.1.a)
    CONTRACT = "contract"  # Exécution d'un contrat (Art. 6.1.b)
    LEGAL_OBLIGATION = "legal_obligation"  # Obligation légale (Art. 6.1.c)
    VITAL_INTERESTS = "vital_interests"  # Intérêts vitaux (Art. 6.1.d)
    PUBLIC_TASK = "public_task"  # Mission d'intérêt public (Art. 6.1.e)
    LEGITIMATE_INTERESTS = "legitimate_interests"  # Intérêts légitimes (Art. 6.1.f)


class ConsentRecord(BaseModel):
    """Enregistrement de consentement."""
    user_id: str
    consent_type: ConsentType
    status: ConsentStatus
    granted_at: Optional[datetime] = None
    withdrawn_at: Optional[datetime] = None
    expires_at: Optional[datetime] = None
    ip_address: Optional[str] = None
    user_agent: Optional[str] = None
    consent_string: Optional[str] = None  # TCF string si applicable
    version: str = Field(default="1.0", description="Version de la politique de confidentialité")


class DataProcessingRecord(BaseModel):
    """Enregistrement de traitement de données."""
    processing_id: str
    user_id: str
    purpose: DataProcessingPurpose
    legal_basis: LegalBasis
    data_categories: List[str]
    retention_period: Optional[int] = None  # En jours
    created_at: datetime = Field(default_factory=datetime.utcnow)
    consent_required: bool = False


class UserDataRequest(BaseModel):
    """Demande d'exercice des droits utilisateur."""
    request_id: str
    user_id: str
    request_type: str  # access, rectification, erasure, portability, restriction
    status: str  # pending, processing, completed, rejected
    created_at: datetime = Field(default_factory=datetime.utcnow)
    completed_at: Optional[datetime] = None
    details: Optional[Dict[str, Any]] = None


class GDPRConsentManager:
    """Gestionnaire de consentements RGPD."""
    
    def __init__(self):
        """Initialise le gestionnaire de consentements."""
        self._consent_records: Dict[str, List[ConsentRecord]] = {}
        self._processing_records: Dict[str, List[DataProcessingRecord]] = {}
        self._user_requests: Dict[str, List[UserDataRequest]] = {}
        self._consent_definitions = self._initialize_consent_definitions()
    
    def _initialize_consent_definitions(self) -> Dict[ConsentType, Dict[str, Any]]:
        """Initialise les définitions des consentements."""
        return {
            ConsentType.ESSENTIAL: {
                "name": "Cookies essentiels",
                "description": "Cookies nécessaires au fonctionnement du service VTC",
                "required": True,
                "duration_days": None,  # Permanent
                "legal_basis": LegalBasis.CONTRACT
            },
            ConsentType.ANALYTICS: {
                "name": "Cookies d'analyse",
                "description": "Cookies pour analyser l'utilisation et améliorer le service",
                "required": False,
                "duration_days": 365,
                "legal_basis": LegalBasis.CONSENT
            },
            ConsentType.MARKETING: {
                "name": "Cookies marketing",
                "description": "Cookies pour personnaliser la publicité",
                "required": False,
                "duration_days": 365,
                "legal_basis": LegalBasis.CONSENT
            },
            ConsentType.GEOLOCATION: {
                "name": "Géolocalisation",
                "description": "Accès à votre position pour les services VTC",
                "required": True,
                "duration_days": None,
                "legal_basis": LegalBasis.CONTRACT
            },
            ConsentType.COMMUNICATION: {
                "name": "Communications marketing",
                "description": "Réception d'offres et communications commerciales",
                "required": False,
                "duration_days": 1095,  # 3 ans
                "legal_basis": LegalBasis.CONSENT
            },
            ConsentType.DATA_SHARING: {
                "name": "Partage de données",
                "description": "Partage de données avec nos partenaires",
                "required": False,
                "duration_days": 365,
                "legal_basis": LegalBasis.CONSENT
            }
        }
    
    def record_consent(
        self,
        user_id: str,
        consent_type: ConsentType,
        granted: bool,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
        consent_string: Optional[str] = None
    ) -> ConsentRecord:
        """
        Enregistre un consentement utilisateur.
        
        Args:
            user_id: Identifiant de l'utilisateur
            consent_type: Type de consentement
            granted: True si accordé, False si refusé
            ip_address: Adresse IP de l'utilisateur
            user_agent: User agent du navigateur
            consent_string: Chaîne de consentement TCF si applicable
            
        Returns:
            ConsentRecord: Enregistrement de consentement créé
        """
        try:
            now = datetime.utcnow()
            
            # Déterminer la date d'expiration
            consent_def = self._consent_definitions.get(consent_type)
            expires_at = None
            if consent_def and consent_def["duration_days"]:
                expires_at = now + timedelta(days=consent_def["duration_days"])
            
            # Créer l'enregistrement
            record = ConsentRecord(
                user_id=user_id,
                consent_type=consent_type,
                status=ConsentStatus.GRANTED if granted else ConsentStatus.DENIED,
                granted_at=now if granted else None,
                expires_at=expires_at,
                ip_address=ip_address,
                user_agent=user_agent,
                consent_string=consent_string
            )
            
            # Stocker l'enregistrement
            if user_id not in self._consent_records:
                self._consent_records[user_id] = []
            
            # Retirer les anciens consentements du même type
            self._consent_records[user_id] = [
                r for r in self._consent_records[user_id] 
                if r.consent_type != consent_type
            ]
            
            # Ajouter le nouveau consentement
            self._consent_records[user_id].append(record)
            
            logger.info(f"Consentement {consent_type} {'accordé' if granted else 'refusé'} pour l'utilisateur {user_id}")
            return record
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du consentement: {e}")
            raise
    
    def withdraw_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """
        Retire un consentement utilisateur.
        
        Args:
            user_id: Identifiant de l'utilisateur
            consent_type: Type de consentement à retirer
            
        Returns:
            bool: True si le retrait a été effectué
        """
        try:
            if user_id not in self._consent_records:
                return False
            
            # Trouver le consentement actuel
            current_consent = None
            for record in self._consent_records[user_id]:
                if record.consent_type == consent_type and record.status == ConsentStatus.GRANTED:
                    current_consent = record
                    break
            
            if not current_consent:
                return False
            
            # Marquer comme retiré
            current_consent.status = ConsentStatus.WITHDRAWN
            current_consent.withdrawn_at = datetime.utcnow()
            
            logger.info(f"Consentement {consent_type} retiré pour l'utilisateur {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors du retrait du consentement: {e}")
            return False
    
    def check_consent(self, user_id: str, consent_type: ConsentType) -> bool:
        """
        Vérifie si un utilisateur a donné son consentement.
        
        Args:
            user_id: Identifiant de l'utilisateur
            consent_type: Type de consentement à vérifier
            
        Returns:
            bool: True si le consentement est accordé et valide
        """
        try:
            if user_id not in self._consent_records:
                # Vérifier si c'est un consentement requis
                consent_def = self._consent_definitions.get(consent_type)
                return consent_def and consent_def["required"]
            
            # Trouver le consentement actuel
            for record in self._consent_records[user_id]:
                if record.consent_type == consent_type:
                    # Vérifier le statut
                    if record.status != ConsentStatus.GRANTED:
                        return False
                    
                    # Vérifier l'expiration
                    if record.expires_at and record.expires_at <= datetime.utcnow():
                        # Marquer comme expiré
                        record.status = ConsentStatus.EXPIRED
                        return False
                    
                    return True
            
            # Pas de consentement trouvé - vérifier si requis
            consent_def = self._consent_definitions.get(consent_type)
            return consent_def and consent_def["required"]
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du consentement: {e}")
            return False
    
    def get_user_consents(self, user_id: str) -> Dict[ConsentType, ConsentRecord]:
        """
        Récupère tous les consentements d'un utilisateur.
        
        Args:
            user_id: Identifiant de l'utilisateur
            
        Returns:
            Dict[ConsentType, ConsentRecord]: Consentements par type
        """
        try:
            if user_id not in self._consent_records:
                return {}
            
            consents = {}
            for record in self._consent_records[user_id]:
                consents[record.consent_type] = record
            
            return consents
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des consentements: {e}")
            return {}
    
    def record_data_processing(
        self,
        user_id: str,
        purpose: DataProcessingPurpose,
        legal_basis: LegalBasis,
        data_categories: List[str],
        retention_period: Optional[int] = None
    ) -> DataProcessingRecord:
        """
        Enregistre une activité de traitement de données.
        
        Args:
            user_id: Identifiant de l'utilisateur
            purpose: Finalité du traitement
            legal_basis: Base légale
            data_categories: Catégories de données traitées
            retention_period: Période de conservation en jours
            
        Returns:
            DataProcessingRecord: Enregistrement créé
        """
        try:
            processing_id = f"{user_id}_{purpose}_{datetime.utcnow().timestamp()}"
            
            record = DataProcessingRecord(
                processing_id=processing_id,
                user_id=user_id,
                purpose=purpose,
                legal_basis=legal_basis,
                data_categories=data_categories,
                retention_period=retention_period,
                consent_required=(legal_basis == LegalBasis.CONSENT)
            )
            
            if user_id not in self._processing_records:
                self._processing_records[user_id] = []
            
            self._processing_records[user_id].append(record)
            
            logger.info(f"Traitement de données enregistré: {purpose} pour l'utilisateur {user_id}")
            return record
            
        except Exception as e:
            logger.error(f"Erreur lors de l'enregistrement du traitement: {e}")
            raise
    
    def handle_data_subject_request(
        self,
        user_id: str,
        request_type: str,
        details: Optional[Dict[str, Any]] = None
    ) -> UserDataRequest:
        """
        Traite une demande d'exercice des droits.
        
        Args:
            user_id: Identifiant de l'utilisateur
            request_type: Type de demande (access, rectification, erasure, etc.)
            details: Détails supplémentaires de la demande
            
        Returns:
            UserDataRequest: Demande créée
        """
        try:
            request_id = f"req_{user_id}_{datetime.utcnow().timestamp()}"
            
            request = UserDataRequest(
                request_id=request_id,
                user_id=user_id,
                request_type=request_type,
                status="pending",
                details=details or {}
            )
            
            if user_id not in self._user_requests:
                self._user_requests[user_id] = []
            
            self._user_requests[user_id].append(request)
            
            logger.info(f"Demande {request_type} créée pour l'utilisateur {user_id}")
            return request
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la demande: {e}")
            raise
    
    def export_user_data(self, user_id: str) -> Dict[str, Any]:
        """
        Exporte toutes les données d'un utilisateur (droit d'accès).
        
        Args:
            user_id: Identifiant de l'utilisateur
            
        Returns:
            Dict[str, Any]: Données exportées
        """
        try:
            export_data = {
                "user_id": user_id,
                "export_date": datetime.utcnow().isoformat(),
                "consents": [],
                "processing_activities": [],
                "requests": []
            }
            
            # Exporter les consentements
            if user_id in self._consent_records:
                for record in self._consent_records[user_id]:
                    export_data["consents"].append({
                        "type": record.consent_type,
                        "status": record.status,
                        "granted_at": record.granted_at.isoformat() if record.granted_at else None,
                        "withdrawn_at": record.withdrawn_at.isoformat() if record.withdrawn_at else None,
                        "expires_at": record.expires_at.isoformat() if record.expires_at else None
                    })
            
            # Exporter les activités de traitement
            if user_id in self._processing_records:
                for record in self._processing_records[user_id]:
                    export_data["processing_activities"].append({
                        "processing_id": record.processing_id,
                        "purpose": record.purpose,
                        "legal_basis": record.legal_basis,
                        "data_categories": record.data_categories,
                        "created_at": record.created_at.isoformat()
                    })
            
            # Exporter les demandes
            if user_id in self._user_requests:
                for request in self._user_requests[user_id]:
                    export_data["requests"].append({
                        "request_id": request.request_id,
                        "type": request.request_type,
                        "status": request.status,
                        "created_at": request.created_at.isoformat(),
                        "completed_at": request.completed_at.isoformat() if request.completed_at else None
                    })
            
            logger.info(f"Données exportées pour l'utilisateur {user_id}")
            return export_data
            
        except Exception as e:
            logger.error(f"Erreur lors de l'export des données: {e}")
            raise
    
    def delete_user_data(self, user_id: str) -> bool:
        """
        Supprime toutes les données d'un utilisateur (droit à l'effacement).
        
        Args:
            user_id: Identifiant de l'utilisateur
            
        Returns:
            bool: True si la suppression a été effectuée
        """
        try:
            deleted = False
            
            # Supprimer les consentements
            if user_id in self._consent_records:
                del self._consent_records[user_id]
                deleted = True
            
            # Supprimer les enregistrements de traitement
            if user_id in self._processing_records:
                del self._processing_records[user_id]
                deleted = True
            
            # Supprimer les demandes
            if user_id in self._user_requests:
                del self._user_requests[user_id]
                deleted = True
            
            if deleted:
                logger.info(f"Données supprimées pour l'utilisateur {user_id}")
            
            return deleted
            
        except Exception as e:
            logger.error(f"Erreur lors de la suppression des données: {e}")
            return False
    
    def get_consent_definitions(self) -> Dict[ConsentType, Dict[str, Any]]:
        """
        Retourne les définitions des consentements.
        
        Returns:
            Dict[ConsentType, Dict[str, Any]]: Définitions des consentements
        """
        return self._consent_definitions.copy()
    
    def generate_consent_banner_config(self) -> Dict[str, Any]:
        """
        Génère la configuration pour la bannière de consentement.
        
        Returns:
            Dict[str, Any]: Configuration de la bannière
        """
        try:
            config = {
                "version": "1.0",
                "categories": [],
                "required_categories": [],
                "optional_categories": []
            }
            
            for consent_type, definition in self._consent_definitions.items():
                category = {
                    "id": consent_type,
                    "name": definition["name"],
                    "description": definition["description"],
                    "required": definition["required"],
                    "duration_days": definition["duration_days"]
                }
                
                config["categories"].append(category)
                
                if definition["required"]:
                    config["required_categories"].append(consent_type)
                else:
                    config["optional_categories"].append(consent_type)
            
            return config
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération de la config bannière: {e}")
            return {}
    
    def check_compliance_status(self, user_id: str) -> Dict[str, Any]:
        """
        Vérifie le statut de conformité RGPD pour un utilisateur.
        
        Args:
            user_id: Identifiant de l'utilisateur
            
        Returns:
            Dict[str, Any]: Statut de conformité
        """
        try:
            status = {
                "user_id": user_id,
                "compliant": True,
                "issues": [],
                "consents": {},
                "last_check": datetime.utcnow().isoformat()
            }
            
            # Vérifier chaque type de consentement
            for consent_type in ConsentType:
                consent_valid = self.check_consent(user_id, consent_type)
                status["consents"][consent_type] = consent_valid
                
                # Vérifier si c'est requis
                consent_def = self._consent_definitions.get(consent_type)
                if consent_def and consent_def["required"] and not consent_valid:
                    status["compliant"] = False
                    status["issues"].append(f"Consentement requis manquant: {consent_type}")
            
            return status
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de conformité: {e}")
            return {"compliant": False, "error": str(e)}


# Instance globale du gestionnaire de consentements
consent_manager = GDPRConsentManager()


def get_consent_manager() -> GDPRConsentManager:
    """Retourne l'instance du gestionnaire de consentements."""
    return consent_manager


def check_user_consent(user_id: str, consent_type: str) -> bool:
    """
    Fonction utilitaire pour vérifier rapidement un consentement.
    
    Args:
        user_id: Identifiant de l'utilisateur
        consent_type: Type de consentement
        
    Returns:
        bool: True si le consentement est accordé
    """
    try:
        return consent_manager.check_consent(user_id, ConsentType(consent_type))
    except Exception as e:
        logger.error(f"Erreur lors de la vérification rapide du consentement: {e}")
        return False

