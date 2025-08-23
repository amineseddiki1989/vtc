"""
Modèle de course VTC sécurisé avec chiffrement des données sensibles.
"""

from sqlalchemy import Column, String, Float, Integer, DateTime, Text, ForeignKey, Enum, Boolean, event
from sqlalchemy.orm import relationship
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.sql import func
import enum
from datetime import datetime
import uuid
from typing import List, Optional

from ..core.database.base import Base
from ..core.security.encryption_service import (
    encrypt_personal_data, decrypt_personal_data,
    encrypt_sensitive_data, decrypt_sensitive_data
)


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


class CancellationReason(str, enum.Enum):
    PASSENGER_CANCELLED = "passenger_cancelled"
    DRIVER_CANCELLED = "driver_cancelled"
    NO_DRIVER_FOUND = "no_driver_found"
    PAYMENT_FAILED = "payment_failed"
    SYSTEM_ERROR = "system_error"
    SAFETY_CONCERN = "safety_concern"


class SecureTrip(Base):
    """Modèle de course VTC sécurisé avec chiffrement des données sensibles."""
    __tablename__ = "secure_trips"

    id = Column(String, primary_key=True, index=True, default=lambda: f"trip_{uuid.uuid4().hex[:12]}")
    
    # Relations utilisateurs
    passenger_id = Column(String, ForeignKey("secure_users.id"), nullable=False)
    driver_id = Column(String, ForeignKey("secure_users.id"), nullable=True)
    
    # Localisation pickup (données sensibles chiffrées)
    pickup_latitude = Column(Float, nullable=False)
    pickup_longitude = Column(Float, nullable=False)
    _pickup_address_encrypted = Column("pickup_address_encrypted", String(1000), nullable=False)
    
    # Localisation destination (données sensibles chiffrées)
    destination_latitude = Column(Float, nullable=False)
    destination_longitude = Column(Float, nullable=False)
    _destination_address_encrypted = Column("destination_address_encrypted", String(1000), nullable=False)
    
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
    
    # Informations d'annulation
    cancellation_reason = Column(Enum(CancellationReason), nullable=True)
    _cancellation_details_encrypted = Column("cancellation_details_encrypted", String(1000), nullable=True)
    
    # Notes et commentaires (chiffrés)
    _passenger_notes_encrypted = Column("passenger_notes_encrypted", String(1000), nullable=True)
    _driver_notes_encrypted = Column("driver_notes_encrypted", String(1000), nullable=True)
    
    # Évaluation
    passenger_rating = Column(Integer, nullable=True)  # 1-5
    driver_rating = Column(Integer, nullable=True)     # 1-5
    _passenger_feedback_encrypted = Column("passenger_feedback_encrypted", String(1000), nullable=True)
    _driver_feedback_encrypted = Column("driver_feedback_encrypted", String(1000), nullable=True)
    
    # Timestamps du workflow (audit trail obligatoire VTC)
    requested_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    assigned_at = Column(DateTime, nullable=True)
    accepted_at = Column(DateTime, nullable=True)
    arrived_at = Column(DateTime, nullable=True)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    cancelled_at = Column(DateTime, nullable=True)
    
    # Métadonnées de sécurité et conformité
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Données de géolocalisation pour conformité légale
    _route_data_encrypted = Column("route_data_encrypted", Text, nullable=True)  # Trajet complet chiffré
    
    # Conformité RGPD
    data_retention_until = Column(DateTime, nullable=True)  # Date limite de conservation
    anonymized = Column(Boolean, default=False, nullable=False)
    
    # Relations
    passenger = relationship("SecureUser", foreign_keys=[passenger_id], back_populates="passenger_trips")
    driver = relationship("SecureUser", foreign_keys=[driver_id], back_populates="driver_trips")
    
    # Propriétés hybrides pour l'accès transparent aux données chiffrées
    @hybrid_property
    def pickup_address(self) -> str:
        """Adresse de prise en charge déchiffrée."""
        if self._pickup_address_encrypted:
            return decrypt_personal_data(self._pickup_address_encrypted)
        return ""
    
    @pickup_address.setter
    def pickup_address(self, value: str):
        """Chiffre et stocke l'adresse de prise en charge."""
        if value:
            self._pickup_address_encrypted = encrypt_personal_data(value)
        else:
            self._pickup_address_encrypted = None
    
    @hybrid_property
    def destination_address(self) -> str:
        """Adresse de destination déchiffrée."""
        if self._destination_address_encrypted:
            return decrypt_personal_data(self._destination_address_encrypted)
        return ""
    
    @destination_address.setter
    def destination_address(self, value: str):
        """Chiffre et stocke l'adresse de destination."""
        if value:
            self._destination_address_encrypted = encrypt_personal_data(value)
        else:
            self._destination_address_encrypted = None
    
    @hybrid_property
    def cancellation_details(self) -> Optional[str]:
        """Détails d'annulation déchiffrés."""
        if self._cancellation_details_encrypted:
            return decrypt_personal_data(self._cancellation_details_encrypted)
        return None
    
    @cancellation_details.setter
    def cancellation_details(self, value: Optional[str]):
        """Chiffre et stocke les détails d'annulation."""
        if value:
            self._cancellation_details_encrypted = encrypt_personal_data(value)
        else:
            self._cancellation_details_encrypted = None
    
    @hybrid_property
    def passenger_notes(self) -> Optional[str]:
        """Notes du passager déchiffrées."""
        if self._passenger_notes_encrypted:
            return decrypt_personal_data(self._passenger_notes_encrypted)
        return None
    
    @passenger_notes.setter
    def passenger_notes(self, value: Optional[str]):
        """Chiffre et stocke les notes du passager."""
        if value:
            self._passenger_notes_encrypted = encrypt_personal_data(value)
        else:
            self._passenger_notes_encrypted = None
    
    @hybrid_property
    def driver_notes(self) -> Optional[str]:
        """Notes du conducteur déchiffrées."""
        if self._driver_notes_encrypted:
            return decrypt_personal_data(self._driver_notes_encrypted)
        return None
    
    @driver_notes.setter
    def driver_notes(self, value: Optional[str]):
        """Chiffre et stocke les notes du conducteur."""
        if value:
            self._driver_notes_encrypted = encrypt_personal_data(value)
        else:
            self._driver_notes_encrypted = None
    
    @hybrid_property
    def passenger_feedback(self) -> Optional[str]:
        """Commentaire du passager déchiffré."""
        if self._passenger_feedback_encrypted:
            return decrypt_personal_data(self._passenger_feedback_encrypted)
        return None
    
    @passenger_feedback.setter
    def passenger_feedback(self, value: Optional[str]):
        """Chiffre et stocke le commentaire du passager."""
        if value:
            self._passenger_feedback_encrypted = encrypt_personal_data(value)
        else:
            self._passenger_feedback_encrypted = None
    
    @hybrid_property
    def driver_feedback(self) -> Optional[str]:
        """Commentaire du conducteur déchiffré."""
        if self._driver_feedback_encrypted:
            return decrypt_personal_data(self._driver_feedback_encrypted)
        return None
    
    @driver_feedback.setter
    def driver_feedback(self, value: Optional[str]):
        """Chiffre et stocke le commentaire du conducteur."""
        if value:
            self._driver_feedback_encrypted = encrypt_personal_data(value)
        else:
            self._driver_feedback_encrypted = None
    
    @hybrid_property
    def route_data(self) -> Optional[str]:
        """Données de trajet déchiffrées."""
        if self._route_data_encrypted:
            return decrypt_sensitive_data(self._route_data_encrypted)
        return None
    
    @route_data.setter
    def route_data(self, value: Optional[str]):
        """Chiffre et stocke les données de trajet."""
        if value:
            self._route_data_encrypted = encrypt_sensitive_data(value)
        else:
            self._route_data_encrypted = None
    
    # Propriétés calculées
    @property
    def duration_actual_minutes(self) -> Optional[int]:
        """Durée réelle de la course en minutes."""
        if self.started_at and self.completed_at:
            delta = self.completed_at - self.started_at
            return int(delta.total_seconds() / 60)
        return None
    
    @property
    def is_completed(self) -> bool:
        """Vérifie si la course est terminée."""
        return self.status == TripStatus.COMPLETED
    
    @property
    def is_cancelled(self) -> bool:
        """Vérifie si la course est annulée."""
        return self.status == TripStatus.CANCELLED
    
    @property
    def is_in_progress(self) -> bool:
        """Vérifie si la course est en cours."""
        return self.status == TripStatus.IN_PROGRESS
    
    @property
    def can_be_cancelled(self) -> bool:
        """Vérifie si la course peut être annulée."""
        return self.status in [
            TripStatus.REQUESTED,
            TripStatus.DRIVER_ASSIGNED,
            TripStatus.DRIVER_ACCEPTED,
            TripStatus.DRIVER_ARRIVED
        ]
    
    @property
    def is_paid(self) -> bool:
        """Vérifie si la course est payée."""
        return self.payment_status == PaymentStatus.PAID
    
    @property
    def needs_data_retention_check(self) -> bool:
        """Vérifie si la course nécessite une vérification de rétention."""
        if self.data_retention_until:
            return datetime.utcnow() >= self.data_retention_until
        return False
    
    # Méthodes de workflow
    def assign_driver(self, driver_id: str):
        """Assigne un conducteur à la course."""
        if self.status != TripStatus.REQUESTED:
            raise ValueError(f"Cannot assign driver to trip in status {self.status}")
        
        self.driver_id = driver_id
        self.status = TripStatus.DRIVER_ASSIGNED
        self.assigned_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def accept_by_driver(self):
        """Acceptation de la course par le conducteur."""
        if self.status != TripStatus.DRIVER_ASSIGNED:
            raise ValueError(f"Cannot accept trip in status {self.status}")
        
        self.status = TripStatus.DRIVER_ACCEPTED
        self.accepted_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def driver_arrived(self):
        """Marque l'arrivée du conducteur."""
        if self.status != TripStatus.DRIVER_ACCEPTED:
            raise ValueError(f"Cannot mark arrived for trip in status {self.status}")
        
        self.status = TripStatus.DRIVER_ARRIVED
        self.arrived_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def start_trip(self):
        """Démarre la course."""
        if self.status != TripStatus.DRIVER_ARRIVED:
            raise ValueError(f"Cannot start trip in status {self.status}")
        
        self.status = TripStatus.IN_PROGRESS
        self.started_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def complete_trip(self, final_price: Optional[float] = None):
        """Termine la course."""
        if self.status != TripStatus.IN_PROGRESS:
            raise ValueError(f"Cannot complete trip in status {self.status}")
        
        self.status = TripStatus.COMPLETED
        self.completed_at = datetime.utcnow()
        if final_price is not None:
            self.final_price = final_price
        self.updated_at = datetime.utcnow()
        
        # Définir la date de rétention des données (7 ans pour conformité VTC)
        from datetime import timedelta
        self.data_retention_until = datetime.utcnow() + timedelta(days=7*365)
    
    def cancel_trip(self, reason: CancellationReason, details: Optional[str] = None):
        """Annule la course."""
        if not self.can_be_cancelled:
            raise ValueError(f"Cannot cancel trip in status {self.status}")
        
        self.status = TripStatus.CANCELLED
        self.cancellation_reason = reason
        if details:
            self.cancellation_details = details
        self.cancelled_at = datetime.utcnow()
        self.updated_at = datetime.utcnow()
    
    def add_rating(self, rating: int, feedback: Optional[str] = None, by_passenger: bool = True):
        """Ajoute une évaluation."""
        if not self.is_completed:
            raise ValueError("Cannot rate incomplete trip")
        
        if not 1 <= rating <= 5:
            raise ValueError("Rating must be between 1 and 5")
        
        if by_passenger:
            self.passenger_rating = rating
            if feedback:
                self.passenger_feedback = feedback
        else:
            self.driver_rating = rating
            if feedback:
                self.driver_feedback = feedback
        
        self.updated_at = datetime.utcnow()
    
    def anonymize_data(self):
        """Anonymise les données personnelles (RGPD)."""
        # Supprimer les adresses exactes
        self.pickup_address = "Adresse anonymisée"
        self.destination_address = "Adresse anonymisée"
        
        # Supprimer les commentaires et notes
        self.passenger_notes = None
        self.driver_notes = None
        self.passenger_feedback = None
        self.driver_feedback = None
        self.cancellation_details = None
        self.route_data = None
        
        # Marquer comme anonymisé
        self.anonymized = True
        self.updated_at = datetime.utcnow()
    
    def to_dict(self, include_sensitive: bool = False) -> dict:
        """Convertit en dictionnaire pour l'API."""
        data = {
            "id": self.id,
            "passenger_id": self.passenger_id,
            "driver_id": self.driver_id,
            "status": self.status.value,
            "vehicle_type": self.vehicle_type.value,
            "estimated_price": self.estimated_price,
            "final_price": self.final_price,
            "distance_km": self.distance_km,
            "duration_minutes": self.duration_minutes,
            "duration_actual_minutes": self.duration_actual_minutes,
            "payment_status": self.payment_status.value,
            "passenger_rating": self.passenger_rating,
            "driver_rating": self.driver_rating,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_completed": self.is_completed,
            "is_cancelled": self.is_cancelled,
            "is_paid": self.is_paid
        }
        
        if include_sensitive and not self.anonymized:
            data.update({
                "pickup_address": self.pickup_address,
                "destination_address": self.destination_address,
                "pickup_latitude": self.pickup_latitude,
                "pickup_longitude": self.pickup_longitude,
                "destination_latitude": self.destination_latitude,
                "destination_longitude": self.destination_longitude,
                "passenger_notes": self.passenger_notes,
                "driver_notes": self.driver_notes,
                "passenger_feedback": self.passenger_feedback,
                "driver_feedback": self.driver_feedback,
                "cancellation_reason": self.cancellation_reason.value if self.cancellation_reason else None,
                "cancellation_details": self.cancellation_details
            })
        
        return data
    
    def to_public_dict(self) -> dict:
        """Convertit en dictionnaire public (données non sensibles)."""
        return {
            "id": self.id,
            "status": self.status.value,
            "vehicle_type": self.vehicle_type.value,
            "estimated_price": self.estimated_price,
            "distance_km": self.distance_km,
            "duration_minutes": self.duration_minutes,
            "requested_at": self.requested_at.isoformat() if self.requested_at else None
        }
    
    def __repr__(self):
        return f"<SecureTrip(id={self.id}, status={self.status}, passenger_id={self.passenger_id})>"


# Événements SQLAlchemy pour la sécurité et l'audit
@event.listens_for(SecureTrip, 'before_update')
def update_timestamp(mapper, connection, target):
    """Met à jour automatiquement le timestamp de modification."""
    target.updated_at = datetime.utcnow()


@event.listens_for(SecureTrip, 'before_insert')
def validate_trip_data(mapper, connection, target):
    """Valide les données de course avant insertion."""
    if not target.pickup_address or not target.destination_address:
        raise ValueError("Les adresses de prise en charge et de destination sont obligatoires")
    
    if target.estimated_price <= 0:
        raise ValueError("Le prix estimé doit être positif")
    
    if target.distance_km <= 0:
        raise ValueError("La distance doit être positive")


# Alias pour compatibilité
Trip = SecureTrip

