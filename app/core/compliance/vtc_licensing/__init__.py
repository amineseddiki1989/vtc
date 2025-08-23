"""
Module de gestion et validation des licences VTC pour l'application VTC.
"""

from .license_validator import (
    VTCLicenseValidator,
    VTCLicense,
    LicenseType,
    LicenseStatus,
    LicenseValidationResult,
    get_license_validator,
    validate_vtc_license
)

__all__ = [
    "VTCLicenseValidator",
    "VTCLicense",
    "LicenseType",
    "LicenseStatus", 
    "LicenseValidationResult",
    "get_license_validator",
    "validate_vtc_license"
]

