"""
Module de conformité pour l'application VTC.
Intègre tous les modules de conformité réglementaire.
"""

# Import des modules de conformité
from .two_factor import get_totp_service
from .vtc_licensing import get_license_validator
from .gdpr import get_consent_manager
from .insurance import get_insurance_validator

__all__ = [
    "get_totp_service",
    "get_license_validator", 
    "get_consent_manager",
    "get_insurance_validator"
]

