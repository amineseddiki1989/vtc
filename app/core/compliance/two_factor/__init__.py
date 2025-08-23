"""
Module d'authentification à deux facteurs (2FA) pour l'application VTC.
"""

from .totp_service import (
    TOTPService,
    TOTPConfig,
    TOTPSecret,
    TOTPValidationResult,
    BackupCode,
    get_totp_service
)

__all__ = [
    "TOTPService",
    "TOTPConfig", 
    "TOTPSecret",
    "TOTPValidationResult",
    "BackupCode",
    "get_totp_service"
]

