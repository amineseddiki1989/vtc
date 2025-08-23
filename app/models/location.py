"""
Modèles de géolocalisation pour l'application VTC.
"""

from sqlalchemy import Column, String, Float, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
import uuid

from ..core.database.base import Base


class DriverLocation(Base):
    """Position et statut d'un conducteur"""
    __tablename__ = "driver_locations"
    
    id = Column(String, primary_key=True, default=lambda: f"loc_{uuid.uuid4().hex[:12]}")
    driver_id = Column(String, ForeignKey("users.id"), nullable=False, unique=True)
    
    # Position GPS
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    heading = Column(Float, nullable=True)  # Direction en degrés
    speed = Column(Float, nullable=True)    # Vitesse en km/h
    accuracy = Column(Float, nullable=True) # Précision GPS en mètres
    
    # Statut de disponibilité
    is_online = Column(Boolean, default=False, nullable=False)
    is_available = Column(Boolean, default=False, nullable=False)
    current_trip_id = Column(String, nullable=True)
    
    # Métadonnées
    last_updated = Column(DateTime, default=datetime.utcnow, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    driver = relationship("User", back_populates="location")


class TripLocation(Base):
    """Historique des positions pendant une course"""
    __tablename__ = "trip_locations"
    
    id = Column(String, primary_key=True, default=lambda: f"tloc_{uuid.uuid4().hex[:12]}")
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False)
    
    # Position GPS
    latitude = Column(Float, nullable=False)
    longitude = Column(Float, nullable=False)
    heading = Column(Float, nullable=True)
    speed = Column(Float, nullable=True)
    
    # Métadonnées
    recorded_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    trip = relationship("Trip", back_populates="locations")


class Vehicle(Base):
    """Véhicule d'un conducteur"""
    __tablename__ = "vehicles"
    
    id = Column(String, primary_key=True, default=lambda: f"veh_{uuid.uuid4().hex[:12]}")
    driver_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Informations du véhicule
    make = Column(String(50), nullable=False)        # Marque
    model = Column(String(50), nullable=False)       # Modèle
    year = Column(String(4), nullable=False)         # Année
    color = Column(String(30), nullable=False)       # Couleur
    license_plate = Column(String(20), nullable=False, unique=True)
    
    # Type et statut
    vehicle_type = Column(String(20), default="standard", nullable=False)  # standard, premium, luxury
    status = Column(String(20), default="active", nullable=False)          # active, maintenance, inactive
    
    # Capacité
    max_passengers = Column(String(1), default="4", nullable=False)
    
    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    driver = relationship("User", back_populates="vehicles")


class Rating(Base):
    """Évaluations des courses"""
    __tablename__ = "ratings"
    
    id = Column(String, primary_key=True, default=lambda: f"rat_{uuid.uuid4().hex[:12]}")
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False, unique=True)
    
    # Évaluations
    passenger_rating = Column(Float, nullable=True)  # Note du passager par le conducteur
    driver_rating = Column(Float, nullable=True)     # Note du conducteur par le passager
    
    # Commentaires
    passenger_comment = Column(Text, nullable=True)
    driver_comment = Column(Text, nullable=True)
    
    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    
    # Relations
    trip = relationship("Trip", back_populates="rating")
    
    @property
    def passenger_id(self):
        return self.trip.passenger_id if self.trip else None
    
    @property
    def driver_id(self):
        return self.trip.driver_id if self.trip else None

