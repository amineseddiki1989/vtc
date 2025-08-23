"""
Modèle utilisateur pour l'API Uber.
"""

import uuid
from datetime import datetime
from enum import Enum
from sqlalchemy import Column, String, DateTime, Boolean, Enum as SQLEnum
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy import String as SQLString
from sqlalchemy.orm import relationship

from ..core.database.base import Base


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


class User(Base):
    """Modèle utilisateur."""
    
    __tablename__ = "users"
    
    id = Column(
        String(36),
        primary_key=True,
        default=lambda: str(uuid.uuid4()),
        unique=True,
        nullable=False
    )
    
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    
    # Informations personnelles
    first_name = Column(String(100), nullable=False)
    last_name = Column(String(100), nullable=False)
    phone = Column(String(20), nullable=False)
    
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
    
    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_login_at = Column(DateTime, nullable=True)
    
    # Sécurité
    failed_login_attempts = Column(String(10), default="0", nullable=False)
    locked_until = Column(DateTime, nullable=True)
    
    # Relations
    location = relationship("DriverLocation", back_populates="driver", uselist=False)
    vehicles = relationship("Vehicle", back_populates="driver")
    passenger_trips = relationship("Trip", foreign_keys="Trip.passenger_id", back_populates="passenger")
    driver_trips = relationship("Trip", foreign_keys="Trip.driver_id", back_populates="driver")
    
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
    
    def __repr__(self):
        return f"<User(id={self.id}, email={self.email}, role={self.role})>"

