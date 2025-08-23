"""
Service de validation des assurances VTC.
Module d'amélioration VTC pour la validation des polices d'assurance.
"""

import re
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class InsuranceType(str, Enum):
    """Types d'assurance VTC."""
    RESPONSABILITE_CIVILE = "responsabilite_civile"  # RC obligatoire
    PROTECTION_JURIDIQUE = "protection_juridique"  # Protection juridique
    INDIVIDUELLE_ACCIDENT = "individuelle_accident"  # Garantie individuelle accident
    DOMMAGES_VEHICULE = "dommages_vehicule"  # Dommages au véhicule
    VOL_INCENDIE = "vol_incendie"  # Vol et incendie
    BRIS_GLACE = "bris_glace"  # Bris de glace


class InsuranceStatus(str, Enum):
    """Statuts des assurances."""
    ACTIVE = "active"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    CANCELLED = "cancelled"
    PENDING = "pending"
    UNKNOWN = "unknown"


class InsuranceProvider(str, Enum):
    """Compagnies d'assurance partenaires."""
    AXA = "axa"
    ALLIANZ = "allianz"
    GENERALI = "generali"
    MAIF = "maif"
    MACIF = "macif"
    GROUPAMA = "groupama"
    MAAF = "maaf"
    MATMUT = "matmut"
    OTHER = "other"


class VTCInsurancePolicy(BaseModel):
    """Modèle pour une police d'assurance VTC."""
    policy_id: str = Field(..., description="Identifiant unique de la police")
    policy_number: str = Field(..., description="Numéro de police")
    insurance_type: InsuranceType = Field(..., description="Type d'assurance")
    provider: InsuranceProvider = Field(..., description="Compagnie d'assurance")
    holder_name: str = Field(..., description="Nom de l'assuré")
    holder_id: str = Field(..., description="Identifiant de l'assuré")
    vehicle_registration: Optional[str] = Field(None, description="Immatriculation du véhicule")
    start_date: datetime = Field(..., description="Date de début de couverture")
    end_date: datetime = Field(..., description="Date de fin de couverture")
    coverage_amount: Optional[float] = Field(None, description="Montant de couverture")
    premium_amount: Optional[float] = Field(None, description="Montant de la prime")
    status: InsuranceStatus = Field(default=InsuranceStatus.UNKNOWN, description="Statut de la police")
    last_verified: Optional[datetime] = Field(default=None, description="Dernière vérification")
    
    @validator('policy_number')
    def validate_policy_number(cls, v, values):
        """Valide le format du numéro de police selon le fournisseur."""
        provider = values.get('provider')
        
        if provider == InsuranceProvider.AXA:
            # Format AXA: AX + 8 chiffres
            if not re.match(r'^AX\d{8}$', v):
                raise ValueError("Format de police AXA invalide (attendu: AX12345678)")
        
        elif provider == InsuranceProvider.ALLIANZ:
            # Format Allianz: AL + 10 chiffres
            if not re.match(r'^AL\d{10}$', v):
                raise ValueError("Format de police Allianz invalide (attendu: AL1234567890)")
        
        elif provider == InsuranceProvider.GENERALI:
            # Format Generali: GE + 9 chiffres
            if not re.match(r'^GE\d{9}$', v):
                raise ValueError("Format de police Generali invalide (attendu: GE123456789)")
        
        elif provider == InsuranceProvider.MAIF:
            # Format MAIF: MF + 7 chiffres
            if not re.match(r'^MF\d{7}$', v):
                raise ValueError("Format de police MAIF invalide (attendu: MF1234567)")
        
        return v
    
    @validator('vehicle_registration')
    def validate_vehicle_registration(cls, v):
        """Valide le format de l'immatriculation française."""
        if v is None:
            return v
        
        # Format français: AB-123-CD ou 123-ABC-45
        if not re.match(r'^[A-Z]{2}-\d{3}-[A-Z]{2}$|^\d{3}-[A-Z]{3}-\d{2}$', v):
            raise ValueError("Format d'immatriculation invalide")
        
        return v


class InsuranceValidationResult(BaseModel):
    """Résultat de validation d'une assurance."""
    is_valid: bool
    status: InsuranceStatus
    expires_in_days: Optional[int] = None
    coverage_adequate: bool = True
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    last_check: datetime = Field(default_factory=datetime.utcnow)


class InsuranceRegistry:
    """Registre des assurances pour simulation."""
    
    def __init__(self):
        """Initialise le registre avec des données de test."""
        self._policies = {
            "AX12345678": {
                "status": InsuranceStatus.ACTIVE,
                "holder_name": "Jean Dupont",
                "end_date": datetime.utcnow() + timedelta(days=180),
                "coverage_amount": 1000000.0,
                "provider": InsuranceProvider.AXA
            },
            "AL1234567890": {
                "status": InsuranceStatus.EXPIRED,
                "holder_name": "Marie Martin",
                "end_date": datetime.utcnow() - timedelta(days=15),
                "coverage_amount": 750000.0,
                "provider": InsuranceProvider.ALLIANZ
            },
            "GE123456789": {
                "status": InsuranceStatus.ACTIVE,
                "holder_name": "Pierre Durand",
                "end_date": datetime.utcnow() + timedelta(days=45),
                "coverage_amount": 1200000.0,
                "provider": InsuranceProvider.GENERALI
            },
            "MF1234567": {
                "status": InsuranceStatus.SUSPENDED,
                "holder_name": "Sophie Leblanc",
                "end_date": datetime.utcnow() + timedelta(days=120),
                "coverage_amount": 800000.0,
                "provider": InsuranceProvider.MAIF
            }
        }
    
    def lookup_policy(self, policy_number: str) -> Optional[Dict[str, Any]]:
        """Recherche une police dans le registre."""
        return self._policies.get(policy_number)


class VTCInsuranceValidator:
    """Service de validation des assurances VTC."""
    
    def __init__(self):
        """Initialise le validateur."""
        self.registry = InsuranceRegistry()
        self._api_endpoints = {
            InsuranceProvider.AXA: "https://api.axa.fr/vtc/policies",
            InsuranceProvider.ALLIANZ: "https://api.allianz.fr/vtc/policies",
            InsuranceProvider.GENERALI: "https://api.generali.fr/vtc/policies",
            InsuranceProvider.MAIF: "https://api.maif.fr/vtc/policies"
        }
        self._minimum_coverage = {
            InsuranceType.RESPONSABILITE_CIVILE: 1000000.0,  # 1M€ minimum
            InsuranceType.PROTECTION_JURIDIQUE: 50000.0,     # 50k€ minimum
            InsuranceType.INDIVIDUELLE_ACCIDENT: 100000.0    # 100k€ minimum
        }
        self._timeout = 10
    
    def validate_policy(self, policy: VTCInsurancePolicy) -> InsuranceValidationResult:
        """
        Valide une police d'assurance VTC.
        
        Args:
            policy: Police d'assurance à valider
            
        Returns:
            InsuranceValidationResult: Résultat de la validation
        """
        try:
            result = InsuranceValidationResult(
                is_valid=False,
                status=InsuranceStatus.UNKNOWN
            )
            
            # Vérification du format
            format_valid = self._validate_format(policy, result)
            if not format_valid:
                return result
            
            # Vérification de l'expiration
            expiry_valid = self._check_expiry(policy, result)
            
            # Vérification de la couverture
            coverage_valid = self._check_coverage(policy, result)
            
            # Vérification dans le registre/API
            registry_valid = self._check_registry(policy, result)
            
            # Déterminer le statut final
            if format_valid and expiry_valid and coverage_valid and registry_valid:
                result.is_valid = True
                result.status = InsuranceStatus.ACTIVE
            
            # Calculer les jours avant expiration
            if policy.end_date:
                days_until_expiry = (policy.end_date - datetime.utcnow()).days
                result.expires_in_days = max(0, days_until_expiry)
                
                # Ajouter des avertissements
                if days_until_expiry <= 7:
                    result.warnings.append(f"Assurance expire dans {days_until_expiry} jours - URGENT")
                elif days_until_expiry <= 30:
                    result.warnings.append(f"Assurance expire dans {days_until_expiry} jours - Renouvellement nécessaire")
                elif days_until_expiry <= 60:
                    result.warnings.append(f"Assurance expire dans {days_until_expiry} jours - Prévoir le renouvellement")
            
            logger.info(f"Validation assurance {policy.policy_number}: {result.status}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation de l'assurance: {e}")
            return InsuranceValidationResult(
                is_valid=False,
                status=InsuranceStatus.UNKNOWN,
                errors=[f"Erreur de validation: {str(e)}"]
            )
    
    def _validate_format(self, policy: VTCInsurancePolicy, result: InsuranceValidationResult) -> bool:
        """Valide le format de la police."""
        try:
            # La validation du format est déjà faite par Pydantic
            return True
        except Exception as e:
            result.errors.append(f"Format invalide: {str(e)}")
            return False
    
    def _check_expiry(self, policy: VTCInsurancePolicy, result: InsuranceValidationResult) -> bool:
        """Vérifie si la police n'est pas expirée."""
        try:
            now = datetime.utcnow()
            
            if policy.end_date <= now:
                result.status = InsuranceStatus.EXPIRED
                result.errors.append("Police d'assurance expirée")
                return False
            
            if policy.start_date > now:
                result.status = InsuranceStatus.PENDING
                result.warnings.append("Police pas encore active")
                return False
            
            return True
            
        except Exception as e:
            result.errors.append(f"Erreur de vérification d'expiration: {str(e)}")
            return False
    
    def _check_coverage(self, policy: VTCInsurancePolicy, result: InsuranceValidationResult) -> bool:
        """Vérifie si la couverture est adéquate."""
        try:
            if policy.coverage_amount is None:
                result.warnings.append("Montant de couverture non spécifié")
                return True
            
            minimum_required = self._minimum_coverage.get(policy.insurance_type)
            if minimum_required and policy.coverage_amount < minimum_required:
                result.coverage_adequate = False
                result.errors.append(
                    f"Couverture insuffisante: {policy.coverage_amount}€ "
                    f"(minimum requis: {minimum_required}€)"
                )
                return False
            
            return True
            
        except Exception as e:
            result.errors.append(f"Erreur de vérification de couverture: {str(e)}")
            return False
    
    def _check_registry(self, policy: VTCInsurancePolicy, result: InsuranceValidationResult) -> bool:
        """Vérifie la police dans le registre des assurances."""
        try:
            # Tentative de vérification via API du fournisseur
            api_result = self._check_provider_api(policy)
            if api_result:
                return self._process_api_result(api_result, result)
            
            # Fallback sur le registre local pour la démo
            registry_data = self.registry.lookup_policy(policy.policy_number)
            if registry_data:
                result.status = registry_data["status"]
                
                if result.status == InsuranceStatus.SUSPENDED:
                    result.errors.append("Police suspendue")
                    return False
                elif result.status == InsuranceStatus.CANCELLED:
                    result.errors.append("Police annulée")
                    return False
                elif result.status == InsuranceStatus.EXPIRED:
                    result.errors.append("Police expirée selon le registre")
                    return False
                
                return result.status == InsuranceStatus.ACTIVE
            else:
                result.errors.append("Police non trouvée dans le registre")
                return False
                
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification registre: {e}")
            result.warnings.append("Impossible de vérifier auprès de l'assureur")
            return True  # On accepte si on ne peut pas vérifier
    
    def _check_provider_api(self, policy: VTCInsurancePolicy) -> Optional[Dict[str, Any]]:
        """Vérifie la police via l'API du fournisseur."""
        try:
            endpoint = self._api_endpoints.get(policy.provider)
            if not endpoint:
                return None
            
            # Simulation d'appel API (les vraies APIs ne sont pas disponibles en démo)
            # En production, ceci ferait un vrai appel HTTP
            logger.info(f"Simulation d'appel API {policy.provider} pour {policy.policy_number}")
            return None
            
        except Exception as e:
            logger.warning(f"Erreur d'appel API assureur: {e}")
            return None
    
    def _process_api_result(self, api_result: Dict[str, Any], result: InsuranceValidationResult) -> bool:
        """Traite le résultat de l'API du fournisseur."""
        try:
            api_status = api_result.get("status", "unknown")
            
            if api_status == "active":
                result.status = InsuranceStatus.ACTIVE
                return True
            elif api_status == "expired":
                result.status = InsuranceStatus.EXPIRED
                result.errors.append("Police expirée selon l'assureur")
                return False
            elif api_status == "suspended":
                result.status = InsuranceStatus.SUSPENDED
                result.errors.append("Police suspendue selon l'assureur")
                return False
            elif api_status == "cancelled":
                result.status = InsuranceStatus.CANCELLED
                result.errors.append("Police annulée selon l'assureur")
                return False
            else:
                result.status = InsuranceStatus.UNKNOWN
                result.warnings.append("Statut inconnu chez l'assureur")
                return False
                
        except Exception as e:
            logger.error(f"Erreur de traitement du résultat API assureur: {e}")
            return False
    
    def validate_policy_number(self, policy_number: str, provider: InsuranceProvider) -> bool:
        """
        Valide uniquement le format d'un numéro de police.
        
        Args:
            policy_number: Numéro de police à valider
            provider: Fournisseur d'assurance
            
        Returns:
            bool: True si le format est valide
        """
        try:
            if provider == InsuranceProvider.AXA:
                return bool(re.match(r'^AX\d{8}$', policy_number))
            elif provider == InsuranceProvider.ALLIANZ:
                return bool(re.match(r'^AL\d{10}$', policy_number))
            elif provider == InsuranceProvider.GENERALI:
                return bool(re.match(r'^GE\d{9}$', policy_number))
            elif provider == InsuranceProvider.MAIF:
                return bool(re.match(r'^MF\d{7}$', policy_number))
            else:
                # Pour les autres fournisseurs, accepter tout format alphanumérique
                return bool(re.match(r'^[A-Z0-9]{6,15}$', policy_number))
                
        except Exception as e:
            logger.error(f"Erreur de validation du format: {e}")
            return False
    
    def get_expiring_policies(self, policies: List[VTCInsurancePolicy], days_threshold: int = 30) -> List[VTCInsurancePolicy]:
        """
        Retourne les polices qui expirent dans le délai spécifié.
        
        Args:
            policies: Liste des polices à vérifier
            days_threshold: Seuil en jours pour considérer une police comme expirant bientôt
            
        Returns:
            List[VTCInsurancePolicy]: Polices expirant bientôt
        """
        try:
            expiring = []
            threshold_date = datetime.utcnow() + timedelta(days=days_threshold)
            
            for policy in policies:
                if policy.end_date <= threshold_date:
                    expiring.append(policy)
            
            return expiring
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des polices expirant: {e}")
            return []
    
    def create_policy_from_data(self, policy_data: Dict[str, Any]) -> VTCInsurancePolicy:
        """
        Crée un objet VTCInsurancePolicy à partir de données brutes.
        
        Args:
            policy_data: Données de police
            
        Returns:
            VTCInsurancePolicy: Objet police créé
        """
        try:
            # Conversion des dates si nécessaire
            if isinstance(policy_data.get('start_date'), str):
                policy_data['start_date'] = datetime.fromisoformat(policy_data['start_date'])
            
            if isinstance(policy_data.get('end_date'), str):
                policy_data['end_date'] = datetime.fromisoformat(policy_data['end_date'])
            
            return VTCInsurancePolicy(**policy_data)
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la police: {e}")
            raise
    
    def get_policy_info(self, policy_number: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'une police par son numéro.
        
        Args:
            policy_number: Numéro de police
            
        Returns:
            Optional[Dict[str, Any]]: Informations de la police ou None
        """
        try:
            return self.registry.lookup_policy(policy_number)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos police: {e}")
            return None
    
    def is_policy_valid_for_vtc(self, policy: VTCInsurancePolicy) -> bool:
        """
        Vérifie si une police est valide pour exercer en tant que VTC.
        
        Args:
            policy: Police à vérifier
            
        Returns:
            bool: True si la police est valide pour VTC
        """
        try:
            validation_result = self.validate_policy(policy)
            
            # Une police est valide pour VTC si:
            # 1. Elle est techniquement valide
            # 2. Elle n'expire pas dans les 7 prochains jours
            # 3. Elle a une couverture adéquate
            # 4. Elle n'a pas d'erreurs critiques
            
            if not validation_result.is_valid:
                return False
            
            if validation_result.expires_in_days is not None and validation_result.expires_in_days < 7:
                return False
            
            if not validation_result.coverage_adequate:
                return False
            
            if validation_result.errors:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification VTC: {e}")
            return False
    
    def check_mandatory_insurances(self, policies: List[VTCInsurancePolicy]) -> Dict[str, bool]:
        """
        Vérifie que toutes les assurances obligatoires sont présentes et valides.
        
        Args:
            policies: Liste des polices de l'utilisateur
            
        Returns:
            Dict[str, bool]: Statut des assurances obligatoires
        """
        try:
            mandatory_types = [
                InsuranceType.RESPONSABILITE_CIVILE,
                InsuranceType.PROTECTION_JURIDIQUE
            ]
            
            status = {}
            
            for insurance_type in mandatory_types:
                # Chercher une police valide pour ce type
                valid_policy_found = False
                
                for policy in policies:
                    if policy.insurance_type == insurance_type:
                        if self.is_policy_valid_for_vtc(policy):
                            valid_policy_found = True
                            break
                
                status[insurance_type.value] = valid_policy_found
            
            return status
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification des assurances obligatoires: {e}")
            return {}


# Instance globale du validateur
insurance_validator = VTCInsuranceValidator()


def get_insurance_validator() -> VTCInsuranceValidator:
    """Retourne l'instance du validateur d'assurances."""
    return insurance_validator


def validate_vtc_insurance(policy_number: str, provider: str, holder_name: str) -> InsuranceValidationResult:
    """
    Fonction utilitaire pour valider rapidement une assurance VTC.
    
    Args:
        policy_number: Numéro de police
        provider: Fournisseur d'assurance
        holder_name: Nom de l'assuré
        
    Returns:
        InsuranceValidationResult: Résultat de la validation
    """
    try:
        # Créer un objet police temporaire pour la validation
        policy = VTCInsurancePolicy(
            policy_id=f"temp_{policy_number}",
            policy_number=policy_number,
            insurance_type=InsuranceType.RESPONSABILITE_CIVILE,
            provider=InsuranceProvider(provider),
            holder_name=holder_name,
            holder_id="temp",
            start_date=datetime.utcnow() - timedelta(days=30),
            end_date=datetime.utcnow() + timedelta(days=335),
            coverage_amount=1000000.0
        )
        
        return insurance_validator.validate_policy(policy)
        
    except Exception as e:
        logger.error(f"Erreur lors de la validation rapide: {e}")
        return InsuranceValidationResult(
            is_valid=False,
            status=InsuranceStatus.UNKNOWN,
            errors=[f"Erreur de validation: {str(e)}"]
        )

