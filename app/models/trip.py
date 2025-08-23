"""
Modèle de course VTC avec workflow complet.
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
import enum
from datetime import datetime
import uuid
from typing import List

from ..core.database.base import Base


class TripStatus(str, enum.Enum):
    REQUESTED = "requested"
    DRIVER_ASSIGNED = "driver_assigned"
    DRIVER_ACCEPTED = "driver_accepted"
    DRIVER_ARRIVED = "driver_arrived"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    DRIVER_DECLINED = "driver_declined"
    NO_DRIVER_AVAILABLE = "no_driver_available"


class VehicleType(str, enum.Enum):
    STANDARD = "standard"
    COMFORT = "comfort"
    PREMIUM = "premium"
    XL = "xl"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    FAILED = "failed"
    REFUNDED = "refunded"


class Trip(Base):
    """Modèle de course VTC avec workflow complet"""
    __tablename__ = "trips"

    id = Column(String, primary_key=True, index=True, default=lambda: f"trip_{uuid.uuid4().hex[:12]}")
    
    # Relations utilisateurs
    passenger_id = Column(String, ForeignKey("users.id"), nullable=False)
    driver_id = Column(String, ForeignKey("users.id"), nullable=True)
    
    # Localisation pickup
    pickup_latitude = Column(Float, nullable=False)
    pickup_longitude = Column(Float, nullable=False)
    pickup_address = Column(Text, nullable=False)
    
    # Localisation destination
    destination_latitude = Column(Float, nullable=False)
    destination_longitude = Column(Float, nullable=False)
    destination_address = Column(Text, nullable=False)
    
    # Informations de course
    status = Column(Enum(TripStatus), default=TripStatus.REQUESTED, nullable=False)
    vehicle_type = Column(Enum(VehicleType), default=VehicleType.STANDARD, nullable=False)
    
    # Tarification
    estimated_price = Column(Float, nullable=False)
    final_price = Column(Float, nullable=True)
    distance_km = Column(Float, nullable=False)
    duration_minutes = Column(Integer, nullable=False)
    
    # Statut de paiement
    payment_status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Timestamps du workflow
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Informations supplémentaires
    cancellation_reason = Column(Text, nullable=True)
    notes = Column(Text, nullable=True)
    
    # Métadonnées
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relations
    passenger = relationship("User", foreign_keys=[passenger_id], back_populates="passenger_trips")
    driver = relationship("User", foreign_keys=[driver_id], back_populates="driver_trips")
    locations = relationship("TripLocation", back_populates="trip", cascade="all, delete-orphan")
    rating = relationship("Rating", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    payment = relationship("Payment", back_populates="trip", uselist=False, cascade="all, delete-orphan")
    
    @property
    def duration_actual_minutes(self):
        """Durée réelle de la course en minutes"""
        if self.started_at and self.completed_at:
            duration = self.completed_at - self.started_at
            return int(duration.total_seconds() / 60)
        return None
    
    @property
    def wait_time_minutes(self):
        """Temps d'attente du passager en minutes"""
        if self.requested_at and self.arrived_at:
            wait_time = self.arrived_at - self.requested_at
            return int(wait_time.total_seconds() / 60)
        return None
    
    @property
    def is_active(self):
        """Vérifie si la course est active (en cours)"""
        active_statuses = [
            TripStatus.REQUESTED,
            TripStatus.DRIVER_ASSIGNED,
            TripStatus.DRIVER_ACCEPTED,
            TripStatus.DRIVER_ARRIVED,
            TripStatus.IN_PROGRESS
        ]
        return self.status in active_statuses
    
    @property
    def is_completed(self):
        """Vérifie si la course est terminée"""
        return self.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]
    
    def can_be_cancelled_by(self, user_id: str) -> bool:
        """Vérifie si un utilisateur peut annuler cette course"""
        if self.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
            return False
        
        # Le passager peut toujours annuler
        if user_id == self.passenger_id:
            return True
        
        # Le conducteur peut annuler avant d'arriver
        if user_id == self.driver_id and self.status in [
            TripStatus.DRIVER_ASSIGNED,
            TripStatus.DRIVER_ACCEPTED
        ]:
            return True
        
        return False
    
    def get_next_valid_statuses(self) -> List[TripStatus]:
        """Retourne les statuts valides suivants selon le statut actuel"""
        transitions = {
            TripStatus.REQUESTED: [TripStatus.DRIVER_ASSIGNED, TripStatus.NO_DRIVER_AVAILABLE, TripStatus.CANCELLED],
            TripStatus.DRIVER_ASSIGNED: [TripStatus.DRIVER_ACCEPTED, TripStatus.DRIVER_DECLINED, TripStatus.CANCELLED],
            TripStatus.DRIVER_ACCEPTED: [TripStatus.DRIVER_ARRIVED, TripStatus.CANCELLED],
            TripStatus.DRIVER_ARRIVED: [TripStatus.IN_PROGRESS, TripStatus.CANCELLED],
            TripStatus.IN_PROGRESS: [TripStatus.COMPLETED, TripStatus.CANCELLED],
            TripStatus.DRIVER_DECLINED: [TripStatus.DRIVER_ASSIGNED, TripStatus.NO_DRIVER_AVAILABLE],
            TripStatus.NO_DRIVER_AVAILABLE: [TripStatus.DRIVER_ASSIGNED, TripStatus.CANCELLED]
        }
        return transitions.get(self.status, [])
    
    def __repr__(self):
        return f"<Trip {self.id}: {self.status}>"

