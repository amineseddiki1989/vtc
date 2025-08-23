"""
Service de validation des licences VTC.
Module d'amélioration VTC pour la conformité réglementaire.
"""

import re
import requests
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, validator
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class LicenseType(str, Enum):
    """Types de licences VTC."""
    CARTE_PROFESSIONNELLE = "carte_professionnelle"
    AUTORISATION_EXPLOITATION = "autorisation_exploitation"
    LICENCE_CONDUCTEUR = "licence_conducteur"


class LicenseStatus(str, Enum):
    """Statuts des licences VTC."""
    VALID = "valid"
    EXPIRED = "expired"
    SUSPENDED = "suspended"
    REVOKED = "revoked"
    PENDING = "pending"
    UNKNOWN = "unknown"


class VTCLicense(BaseModel):
    """Modèle pour une licence VTC."""
    license_id: str = Field(..., description="Identifiant unique de la licence")
    license_type: LicenseType = Field(..., description="Type de licence")
    license_number: str = Field(..., description="Numéro de licence")
    holder_name: str = Field(..., description="Nom du titulaire")
    holder_id: str = Field(..., description="Identifiant du titulaire")
    issue_date: datetime = Field(..., description="Date d'émission")
    expiry_date: datetime = Field(..., description="Date d'expiration")
    issuing_authority: str = Field(..., description="Autorité émettrice")
    status: LicenseStatus = Field(default=LicenseStatus.UNKNOWN, description="Statut de la licence")
    last_verified: Optional[datetime] = Field(default=None, description="Dernière vérification")
    
    @validator('license_number')
    def validate_license_number(cls, v, values):
        """Valide le format du numéro de licence selon le type."""
        license_type = values.get('license_type')
        
        if license_type == LicenseType.CARTE_PROFESSIONNELLE:
            # Format: 2 lettres + 6 chiffres (ex: CP123456)
            if not re.match(r'^CP\d{6}$', v):
                raise ValueError("Format de carte professionnelle invalide (attendu: CP123456)")
        
        elif license_type == LicenseType.AUTORISATION_EXPLOITATION:
            # Format: AE + département + 4 chiffres (ex: AE75001)
            if not re.match(r'^AE\d{5}$', v):
                raise ValueError("Format d'autorisation d'exploitation invalide (attendu: AE75001)")
        
        elif license_type == LicenseType.LICENCE_CONDUCTEUR:
            # Format: LC + 8 chiffres (ex: LC12345678)
            if not re.match(r'^LC\d{8}$', v):
                raise ValueError("Format de licence conducteur invalide (attendu: LC12345678)")
        
        return v


class LicenseValidationResult(BaseModel):
    """Résultat de validation d'une licence."""
    is_valid: bool
    status: LicenseStatus
    expires_in_days: Optional[int] = None
    warnings: List[str] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)
    last_check: datetime = Field(default_factory=datetime.utcnow)


class LicenseRegistry:
    """Registre des licences VTC pour simulation."""
    
    def __init__(self):
        """Initialise le registre avec des données de test."""
        self._licenses = {
            "CP123456": {
                "status": LicenseStatus.VALID,
                "holder_name": "Jean Dupont",
                "expiry_date": datetime.utcnow() + timedelta(days=365),
                "issuing_authority": "Préfecture de Paris"
            },
            "CP654321": {
                "status": LicenseStatus.EXPIRED,
                "holder_name": "Marie Martin",
                "expiry_date": datetime.utcnow() - timedelta(days=30),
                "issuing_authority": "Préfecture de Lyon"
            },
            "AE75001": {
                "status": LicenseStatus.VALID,
                "holder_name": "VTC Express SARL",
                "expiry_date": datetime.utcnow() + timedelta(days=180),
                "issuing_authority": "Préfecture de Paris"
            },
            "LC12345678": {
                "status": LicenseStatus.SUSPENDED,
                "holder_name": "Pierre Durand",
                "expiry_date": datetime.utcnow() + timedelta(days=90),
                "issuing_authority": "Préfecture de Marseille"
            }
        }
    
    def lookup_license(self, license_number: str) -> Optional[Dict[str, Any]]:
        """Recherche une licence dans le registre."""
        return self._licenses.get(license_number)


class VTCLicenseValidator:
    """Service de validation des licences VTC."""
    
    def __init__(self):
        """Initialise le validateur."""
        self.registry = LicenseRegistry()
        self._api_endpoints = {
            "carte_professionnelle": "https://api.vtc.gouv.fr/cartes",
            "autorisation_exploitation": "https://api.vtc.gouv.fr/autorisations",
            "licence_conducteur": "https://api.vtc.gouv.fr/conducteurs"
        }
        self._timeout = 10  # Timeout pour les requêtes API
    
    def validate_license(self, license: VTCLicense) -> LicenseValidationResult:
        """
        Valide une licence VTC.
        
        Args:
            license: Licence VTC à valider
            
        Returns:
            LicenseValidationResult: Résultat de la validation
        """
        try:
            result = LicenseValidationResult(
                is_valid=False,
                status=LicenseStatus.UNKNOWN
            )
            
            # Vérification du format
            format_valid = self._validate_format(license, result)
            if not format_valid:
                return result
            
            # Vérification de l'expiration
            expiry_valid = self._check_expiry(license, result)
            
            # Vérification dans le registre/API
            registry_valid = self._check_registry(license, result)
            
            # Déterminer le statut final
            if format_valid and expiry_valid and registry_valid:
                result.is_valid = True
                result.status = LicenseStatus.VALID
            
            # Calculer les jours avant expiration
            if license.expiry_date:
                days_until_expiry = (license.expiry_date - datetime.utcnow()).days
                result.expires_in_days = max(0, days_until_expiry)
                
                # Ajouter des avertissements
                if days_until_expiry <= 30:
                    result.warnings.append(f"Licence expire dans {days_until_expiry} jours")
                elif days_until_expiry <= 90:
                    result.warnings.append(f"Licence expire dans {days_until_expiry} jours - Renouvellement recommandé")
            
            logger.info(f"Validation licence {license.license_number}: {result.status}")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la validation de la licence: {e}")
            return LicenseValidationResult(
                is_valid=False,
                status=LicenseStatus.UNKNOWN,
                errors=[f"Erreur de validation: {str(e)}"]
            )
    
    def _validate_format(self, license: VTCLicense, result: LicenseValidationResult) -> bool:
        """Valide le format de la licence."""
        try:
            # La validation du format est déjà faite par Pydantic
            return True
        except Exception as e:
            result.errors.append(f"Format invalide: {str(e)}")
            return False
    
    def _check_expiry(self, license: VTCLicense, result: LicenseValidationResult) -> bool:
        """Vérifie si la licence n'est pas expirée."""
        try:
            now = datetime.utcnow()
            
            if license.expiry_date <= now:
                result.status = LicenseStatus.EXPIRED
                result.errors.append("Licence expirée")
                return False
            
            return True
            
        except Exception as e:
            result.errors.append(f"Erreur de vérification d'expiration: {str(e)}")
            return False
    
    def _check_registry(self, license: VTCLicense, result: LicenseValidationResult) -> bool:
        """Vérifie la licence dans le registre officiel."""
        try:
            # Tentative de vérification via API officielle
            api_result = self._check_official_api(license)
            if api_result:
                return self._process_api_result(api_result, result)
            
            # Fallback sur le registre local pour la démo
            registry_data = self.registry.lookup_license(license.license_number)
            if registry_data:
                result.status = registry_data["status"]
                
                if result.status == LicenseStatus.SUSPENDED:
                    result.errors.append("Licence suspendue")
                    return False
                elif result.status == LicenseStatus.REVOKED:
                    result.errors.append("Licence révoquée")
                    return False
                elif result.status == LicenseStatus.EXPIRED:
                    result.errors.append("Licence expirée selon le registre")
                    return False
                
                return result.status == LicenseStatus.VALID
            else:
                result.errors.append("Licence non trouvée dans le registre")
                return False
                
        except Exception as e:
            logger.warning(f"Erreur lors de la vérification registre: {e}")
            result.warnings.append("Impossible de vérifier dans le registre officiel")
            return True  # On accepte si on ne peut pas vérifier
    
    def _check_official_api(self, license: VTCLicense) -> Optional[Dict[str, Any]]:
        """Vérifie la licence via l'API officielle."""
        try:
            endpoint = self._api_endpoints.get(license.license_type.value)
            if not endpoint:
                return None
            
            # Simulation d'appel API (les vraies APIs ne sont pas disponibles en démo)
            # En production, ceci ferait un vrai appel HTTP
            logger.info(f"Simulation d'appel API pour {license.license_number}")
            return None
            
        except Exception as e:
            logger.warning(f"Erreur d'appel API: {e}")
            return None
    
    def _process_api_result(self, api_result: Dict[str, Any], result: LicenseValidationResult) -> bool:
        """Traite le résultat de l'API officielle."""
        try:
            api_status = api_result.get("status", "unknown")
            
            if api_status == "valid":
                result.status = LicenseStatus.VALID
                return True
            elif api_status == "expired":
                result.status = LicenseStatus.EXPIRED
                result.errors.append("Licence expirée selon l'API officielle")
                return False
            elif api_status == "suspended":
                result.status = LicenseStatus.SUSPENDED
                result.errors.append("Licence suspendue selon l'API officielle")
                return False
            elif api_status == "revoked":
                result.status = LicenseStatus.REVOKED
                result.errors.append("Licence révoquée selon l'API officielle")
                return False
            else:
                result.status = LicenseStatus.UNKNOWN
                result.warnings.append("Statut inconnu dans l'API officielle")
                return False
                
        except Exception as e:
            logger.error(f"Erreur de traitement du résultat API: {e}")
            return False
    
    def validate_license_number(self, license_number: str, license_type: LicenseType) -> bool:
        """
        Valide uniquement le format d'un numéro de licence.
        
        Args:
            license_number: Numéro de licence à valider
            license_type: Type de licence
            
        Returns:
            bool: True si le format est valide
        """
        try:
            if license_type == LicenseType.CARTE_PROFESSIONNELLE:
                return bool(re.match(r'^CP\d{6}$', license_number))
            elif license_type == LicenseType.AUTORISATION_EXPLOITATION:
                return bool(re.match(r'^AE\d{5}$', license_number))
            elif license_type == LicenseType.LICENCE_CONDUCTEUR:
                return bool(re.match(r'^LC\d{8}$', license_number))
            else:
                return False
                
        except Exception as e:
            logger.error(f"Erreur de validation du format: {e}")
            return False
    
    def get_expiring_licenses(self, licenses: List[VTCLicense], days_threshold: int = 30) -> List[VTCLicense]:
        """
        Retourne les licences qui expirent dans le délai spécifié.
        
        Args:
            licenses: Liste des licences à vérifier
            days_threshold: Seuil en jours pour considérer une licence comme expirant bientôt
            
        Returns:
            List[VTCLicense]: Licences expirant bientôt
        """
        try:
            expiring = []
            threshold_date = datetime.utcnow() + timedelta(days=days_threshold)
            
            for license in licenses:
                if license.expiry_date <= threshold_date:
                    expiring.append(license)
            
            return expiring
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche des licences expirant: {e}")
            return []
    
    def create_license_from_data(self, license_data: Dict[str, Any]) -> VTCLicense:
        """
        Crée un objet VTCLicense à partir de données brutes.
        
        Args:
            license_data: Données de licence
            
        Returns:
            VTCLicense: Objet licence créé
        """
        try:
            # Conversion des dates si nécessaire
            if isinstance(license_data.get('issue_date'), str):
                license_data['issue_date'] = datetime.fromisoformat(license_data['issue_date'])
            
            if isinstance(license_data.get('expiry_date'), str):
                license_data['expiry_date'] = datetime.fromisoformat(license_data['expiry_date'])
            
            return VTCLicense(**license_data)
            
        except Exception as e:
            logger.error(f"Erreur lors de la création de la licence: {e}")
            raise
    
    def get_license_info(self, license_number: str) -> Optional[Dict[str, Any]]:
        """
        Récupère les informations d'une licence par son numéro.
        
        Args:
            license_number: Numéro de licence
            
        Returns:
            Optional[Dict[str, Any]]: Informations de la licence ou None
        """
        try:
            return self.registry.lookup_license(license_number)
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos licence: {e}")
            return None
    
    def is_license_valid_for_vtc(self, license: VTCLicense) -> bool:
        """
        Vérifie si une licence est valide pour exercer en tant que VTC.
        
        Args:
            license: Licence à vérifier
            
        Returns:
            bool: True si la licence est valide pour VTC
        """
        try:
            validation_result = self.validate_license(license)
            
            # Une licence est valide pour VTC si:
            # 1. Elle est techniquement valide
            # 2. Elle n'expire pas dans les 7 prochains jours
            # 3. Elle n'a pas d'erreurs critiques
            
            if not validation_result.is_valid:
                return False
            
            if validation_result.expires_in_days is not None and validation_result.expires_in_days < 7:
                return False
            
            if validation_result.errors:
                return False
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification VTC: {e}")
            return False


# Instance globale du validateur
license_validator = VTCLicenseValidator()


def get_license_validator() -> VTCLicenseValidator:
    """Retourne l'instance du validateur de licences."""
    return license_validator


def validate_vtc_license(license_number: str, license_type: str, holder_name: str) -> LicenseValidationResult:
    """
    Fonction utilitaire pour valider rapidement une licence VTC.
    
    Args:
        license_number: Numéro de licence
        license_type: Type de licence
        holder_name: Nom du titulaire
        
    Returns:
        LicenseValidationResult: Résultat de la validation
    """
    try:
        # Créer un objet licence temporaire pour la validation
        license = VTCLicense(
            license_id=f"temp_{license_number}",
            license_type=LicenseType(license_type),
            license_number=license_number,
            holder_name=holder_name,
            holder_id="temp",
            issue_date=datetime.utcnow() - timedelta(days=365),
            expiry_date=datetime.utcnow() + timedelta(days=365),
            issuing_authority="Validation temporaire"
        )
        
        return license_validator.validate_license(license)
        
    except Exception as e:
        logger.error(f"Erreur lors de la validation rapide: {e}")
        return LicenseValidationResult(
            is_valid=False,
            status=LicenseStatus.UNKNOWN,
            errors=[f"Erreur de validation: {str(e)}"]
        )

