"""
Module de conformité RGPD pour l'application VTC.
"""

from .consent_manager import (
    GDPRConsentManager,
    ConsentType,
    ConsentStatus,
    ConsentRecord,
    DataProcessingPurpose,
    LegalBasis,
    DataProcessingRecord,
    UserDataRequest,
    get_consent_manager,
    check_user_consent
)

__all__ = [
    "GDPRConsentManager",
    "ConsentType",
    "ConsentStatus",
    "ConsentRecord",
    "DataProcessingPurpose",
    "LegalBasis",
    "DataProcessingRecord",
    "UserDataRequest",
    "get_consent_manager",
    "check_user_consent"
]

