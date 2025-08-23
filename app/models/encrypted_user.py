"""
Modèle utilisateur sécurisé avec chiffrement des données sensibles.
"""

import uuid
from datetime import datetime
from enum import Enum
from typing import Optional

from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum, event
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property

from ..core.database.base import Base
from ..core.security.encryption_service import (
    encrypt_personal_data, decrypt_personal_data,
    encrypt_sensitive_data, decrypt_sensitive_data
)


class UserRole(str, Enum):
    """Rôles utilisateur."""
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class UserStatus(str, Enum):
    """Statuts utilisateur."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    SUSPENDED = "suspended"
    BANNED = "banned"


class SecureUser(Base):
    """Modèle utilisateur sécurisé avec chiffrement des données sensibles."""
    
    __tablename__ = "secure_users"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    # Email (indexé mais non chiffré pour les recherches)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Informations personnelles chiffrées
    _first_name_encrypted = Column("first_name_encrypted", String(500), nullable=False)
    _last_name_encrypted = Column("last_name_encrypted", String(500), nullable=False)
    _phone_encrypted = Column("phone_encrypted", String(500), nullable=False)
    
    # Données sensibles supplémentaires (chiffrées)
    _address_encrypted = Column("address_encrypted", String(1000), nullable=True)
    _license_number_encrypted = Column("license_number_encrypted", String(500), nullable=True)
    _bank_account_encrypted = Column("bank_account_encrypted", String(500), nullable=True)
    
    role = Column(
        SQLEnum(UserRole),
        default=UserRole.PASSENGER,
        nullable=False
    )
    
    status = Column(
        SQLEnum(UserStatus),
        default=UserStatus.ACTIVE,
        nullable=False
    )
    
    # Métadonnées de sécurité
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    last_password_change = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Sécurité et audit
    failed_login_attempts = Column(String(10), default="0", nullable=False)
    locked_until = Column(DateTime, nullable=True)
    security_flags = Column(String(500), nullable=True)  # Flags de sécurité chiffrés
    
    # Consentements RGPD
    data_processing_consent = Column(Boolean, default=False, nullable=False)
    marketing_consent = Column(Boolean, default=False, nullable=False)
    consent_date = Column(DateTime, nullable=True)
    
    # Relations
    location = relationship("DriverLocation", back_populates="driver", uselist=False)
    vehicles = relationship("Vehicle", back_populates="driver")
    passenger_trips = relationship("Trip", foreign_keys="Trip.passenger_id", back_populates="passenger")
    driver_trips = relationship("Trip", foreign_keys="Trip.driver_id", back_populates="driver")
    
    # Propriétés hybrides pour l'accès transparent aux données chiffrées
    @hybrid_property
    def first_name(self) -> str:
        """Prénom déchiffré."""
        if self._first_name_encrypted:
            return decrypt_personal_data(self._first_name_encrypted)
        return ""
    
    @first_name.setter
    def first_name(self, value: str):
        """Chiffre et stocke le prénom."""
        if value:
            self._first_name_encrypted = encrypt_personal_data(value)
        else:
            self._first_name_encrypted = None
    
    @hybrid_property
    def last_name(self) -> str:
        """Nom de famille déchiffré."""
        if self._last_name_encrypted:
            return decrypt_personal_data(self._last_name_encrypted)
        return ""
    
    @last_name.setter
    def last_name(self, value: str):
        """Chiffre et stocke le nom de famille."""
        if value:
            self._last_name_encrypted = encrypt_personal_data(value)
        else:
            self._last_name_encrypted = None
    
    @hybrid_property
    def phone(self) -> str:
        """Téléphone déchiffré."""
        if self._phone_encrypted:
            return decrypt_personal_data(self._phone_encrypted)
        return ""
    
    @phone.setter
    def phone(self, value: str):
        """Chiffre et stocke le téléphone."""
        if value:
            self._phone_encrypted = encrypt_personal_data(value)
        else:
            self._phone_encrypted = None
    
    @hybrid_property
    def address(self) -> Optional[str]:
        """Adresse déchiffrée."""
        if self._address_encrypted:
            return decrypt_personal_data(self._address_encrypted)
        return None
    
    @address.setter
    def address(self, value: Optional[str]):
        """Chiffre et stocke l'adresse."""
        if value:
            self._address_encrypted = encrypt_personal_data(value)
        else:
            self._address_encrypted = None
    
    @hybrid_property
    def license_number(self) -> Optional[str]:
        """Numéro de licence déchiffré."""
        if self._license_number_encrypted:
            return decrypt_sensitive_data(self._license_number_encrypted)
        return None
    
    @license_number.setter
    def license_number(self, value: Optional[str]):
        """Chiffre et stocke le numéro de licence."""
        if value:
            self._license_number_encrypted = encrypt_sensitive_data(value)
        else:
            self._license_number_encrypted = None
    
    @hybrid_property
    def bank_account(self) -> Optional[str]:
        """Compte bancaire déchiffré."""
        if self._bank_account_encrypted:
            return decrypt_sensitive_data(self._bank_account_encrypted)
        return None
    
    @bank_account.setter
    def bank_account(self, value: Optional[str]):
        """Chiffre et stocke le compte bancaire."""
        if value:
            self._bank_account_encrypted = encrypt_sensitive_data(value)
        else:
            self._bank_account_encrypted = None
    
    @property
    def full_name(self) -> str:
        """Nom complet."""
        return f"{self.first_name} {self.last_name}".strip()
    
    @property
    def is_active(self) -> bool:
        """Vérifie si l'utilisateur est actif."""
        return self.status == UserStatus.ACTIVE
    
    @property
    def is_locked(self) -> bool:
        """Vérifie si l'utilisateur est verrouillé."""
        if self.locked_until is None:
            return False
        return datetime.utcnow() < self.locked_until
    
    @property
    def is_driver(self) -> bool:
        """Vérifie si l'utilisateur est un conducteur."""
        return self.role == UserRole.DRIVER
    
    @property
    def is_admin(self) -> bool:
        """Vérifie si l'utilisateur est un administrateur."""
        return self.role == UserRole.ADMIN
    
    @property
    def has_valid_consent(self) -> bool:
        """Vérifie si l'utilisateur a donné son consentement valide."""
        return self.data_processing_consent and self.consent_date is not None
    
    def update_consent(self, data_processing: bool, marketing: bool = False):
        """Met à jour les consentements RGPD."""
        self.data_processing_consent = data_processing
        self.marketing_consent = marketing
        self.consent_date = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def lock_account(self, duration_minutes: int = 30):
        """Verrouille le compte utilisateur."""
        from datetime import timedelta
        self.locked_until = datetime.utcnow() + timedelta(minutes=duration_minutes)
        self.updated_at = datetime.utcnow()
    
    def unlock_account(self):
        """Déverrouille le compte utilisateur."""
        self.locked_until = None
        self.failed_login_attempts = "0"
        self.updated_at = datetime.utcnow()
    
    def increment_failed_login(self):
        """Incrémente le compteur d'échecs de connexion."""
        current_attempts = int(self.failed_login_attempts or "0")
        self.failed_login_attempts = str(current_attempts + 1)
        self.updated_at = datetime.utcnow()
    
    def reset_failed_login(self):
        """Remet à zéro le compteur d'échecs de connexion."""
        self.failed_login_attempts = "0"
        self.last_login_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def change_password_hash(self, new_password_hash: str):
        """Change le hash du mot de passe et met à jour la date."""
        self.password_hash = new_password_hash
        self.last_password_change = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convertit en dictionnaire pour l'API."""
        data = {
            "id": self.id,
            "email": self.email,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "full_name": self.full_name,
            "role": self.role.value,
            "status": self.status.value,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "last_login_at": self.last_login_at.isoformat() if self.last_login_at else None,
            "is_active": self.is_active,
            "is_locked": self.is_locked,
            "has_valid_consent": self.has_valid_consent
        }
        
        if include_sensitive:
            data.update({
                "phone": self.phone,
                "address": self.address,
                "license_number": self.license_number if self.is_driver else None,
                "data_processing_consent": self.data_processing_consent,
                "marketing_consent": self.marketing_consent,
                "consent_date": self.consent_date.isoformat() if self.consent_date else None
            })
        
        return data
    
    def to_public_dict(self) -> dict:
        """Convertit en dictionnaire public (données non sensibles)."""
        return {
            "id": self.id,
            "first_name": self.first_name,
            "role": self.role.value,
            "is_active": self.is_active
        }
    
    def __repr__(self):
        return f"<SecureUser(id={self.id}, email={self.email}, role={self.role})>"


# Événements SQLAlchemy pour la sécurité
@event.listens_for(SecureUser, 'before_update')
def update_timestamp(mapper, connection, target):
    """Met à jour automatiquement le timestamp de modification."""
    target.updated_at = datetime.utcnow()


@event.listens_for(SecureUser, 'before_insert')
def validate_consent(mapper, connection, target):
    """Valide le consentement avant insertion."""
    if not target.data_processing_consent:
        raise ValueError("Le consentement au traitement des données est obligatoire")


# Alias pour compatibilité
User = SecureUser

