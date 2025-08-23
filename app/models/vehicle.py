from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, Enum, ForeignKey, Float
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum

from ..core.database.base import Base

class VehicleStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    SUSPENDED = "suspended"

class VehicleType(str, enum.Enum):
    STANDARD = "standard"
    COMFORT = "comfort"
    PREMIUM = "premium"
    XL = "xl"
    ELECTRIC = "electric"

class Vehicle(Base):
    __tablename__ = "vehicles"

    id = Column(String, primary_key=True, index=True)
    driver_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Informations véhicule
    make = Column(String(50), nullable=False)  # Marque
    model = Column(String(50), nullable=False)  # Modèle
    year = Column(Integer, nullable=False)
    color = Column(String(30), nullable=False)
    license_plate = Column(String(20), nullable=False, unique=True)
    
    # Classification
    vehicle_type = Column(Enum(VehicleType), default=VehicleType.STANDARD, nullable=False)
    capacity = Column(Integer, default=4, nullable=False)  # Nombre de passagers
    
    # Documents et certifications
    registration_number = Column(String(50), nullable=False)
    insurance_policy = Column(String(100), nullable=False)
    insurance_expiry = Column(DateTime(timezone=True), nullable=False)
    inspection_expiry = Column(DateTime(timezone=True), nullable=False)
    
    # Statut et disponibilité
    status = Column(Enum(VehicleStatus), default=VehicleStatus.ACTIVE, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    
    # Métadonnées
    photos = Column(Text, nullable=True)  # JSON array of photo URLs
    features = Column(Text, nullable=True)  # JSON array of features
    notes = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    verified_at = Column(DateTime(timezone=True), nullable=True)
    
    # Relations
    driver = relationship("User", back_populates="vehicles")

    def __repr__(self):
        return f"<Vehicle {self.license_plate}: {self.make} {self.model}>"

