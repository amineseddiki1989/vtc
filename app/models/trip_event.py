"""
Modèle d'événements de course pour traçabilité complète.
Audit trail de toutes les actions sur une course.
"""

import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any
from enum import Enum

from sqlalchemy import (
    Column, String, DateTime, Text, ForeignKey, JSON, Index
)
from sqlalchemy.orm import relationship

from ..core.database.base import Base

class TripEventType(str, Enum):
    """Types d'événements de course."""
    # Création et recherche
    TRIP_CREATED = "trip_created"
    DRIVER_SEARCH_STARTED = "driver_search_started"
    DRIVER_FOUND = "driver_found"
    DRIVER_ASSIGNED = "driver_assigned"
    
    # Mouvement du conducteur
    DRIVER_MOVING_TO_PICKUP = "driver_moving_to_pickup"
    DRIVER_ARRIVED_AT_PICKUP = "driver_arrived_at_pickup"
    PASSENGER_CONTACTED = "passenger_contacted"
    
    # Prise en charge
    PASSENGER_PICKUP_STARTED = "passenger_pickup_started"
    PASSENGER_ONBOARD = "passenger_onboard"
    TRIP_STARTED = "trip_started"
    
    # Pendant la course
    ROUTE_UPDATED = "route_updated"
    DESTINATION_CHANGED = "destination_changed"
    STOP_ADDED = "stop_added"
    TRAFFIC_DETECTED = "traffic_detected"
    
    # Fin de course
    ARRIVED_AT_DESTINATION = "arrived_at_destination"
    TRIP_COMPLETED = "trip_completed"
    PAYMENT_PROCESSED = "payment_processed"
    
    # Annulations
    TRIP_CANCELLED = "trip_cancelled"
    CANCELLATION_FEE_APPLIED = "cancellation_fee_applied"
    
    # Évaluations
    PASSENGER_RATED = "passenger_rated"
    DRIVER_RATED = "driver_rated"
    
    # Problèmes
    ISSUE_REPORTED = "issue_reported"
    EMERGENCY_ACTIVATED = "emergency_activated"
    SUPPORT_CONTACTED = "support_contacted"
    
    # Système
    STATUS_CHANGED = "status_changed"
    LOCATION_UPDATED = "location_updated"
    FARE_CALCULATED = "fare_calculated"
    SURGE_APPLIED = "surge_applied"

class TripEvent(Base):
    """Événement de course pour audit trail."""
    
    __tablename__ = "trip_events"
    
    # === IDENTIFIANTS ===
    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False, index=True)
    
    # === ÉVÉNEMENT ===
    event_type = Column(String(50), nullable=False, index=True)
    event_source = Column(String(30), nullable=False)  # app, driver_app, admin, system
    
    # === ACTEUR ===
    actor_id = Column(String, ForeignKey("users.id"), nullable=True)
    actor_type = Column(String(20), nullable=True)  # passenger, driver, admin, system
    
    # === DONNÉES ===
    event_data = Column(JSON, nullable=True)
    previous_value = Column(JSON, nullable=True)
    new_value = Column(JSON, nullable=True)
    
    # === CONTEXTE ===
    description = Column(Text, nullable=True)
    location_latitude = Column(String(20), nullable=True)
    location_longitude = Column(String(20), nullable=True)
    
    # === MÉTADONNÉES ===
    device_info = Column(JSON, nullable=True)
    app_version = Column(String(20), nullable=True)
    ip_address = Column(String(45), nullable=True)
    user_agent = Column(Text, nullable=True)
    
    # === TIMESTAMP ===
    created_at = Column(DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc))
    
    # === RELATIONS ===
    trip = relationship("Trip", back_populates="trip_events")
    actor = relationship("User", foreign_keys=[actor_id])
    
    # === INDEX ===
    __table_args__ = (
        Index('idx_trip_event_trip_type', 'trip_id', 'event_type'),
        Index('idx_trip_event_created', 'created_at'),
        Index('idx_trip_event_actor', 'actor_id', 'event_type'),
    )
    
    @classmethod
    def create_event(
        cls,
        trip_id: str,
        event_type: TripEventType,
        event_source: str = "system",
        actor_id: Optional[str] = None,
        actor_type: Optional[str] = None,
        event_data: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None,
        location: Optional[tuple] = None,
        device_info: Optional[Dict[str, Any]] = None
    ) -> "TripEvent":
        """Crée un nouvel événement de course."""
        
        event = cls(
            trip_id=trip_id,
            event_type=event_type,
            event_source=event_source,
            actor_id=actor_id,
            actor_type=actor_type,
            event_data=event_data or {},
            description=description
        )
        
        if location:
            event.location_latitude = str(location[0])
            event.location_longitude = str(location[1])
        
        if device_info:
            event.device_info = device_info
            
        return event
    
    def to_dict(self) -> Dict[str, Any]:
        """Convertit en dictionnaire."""
        return {
            "id": str(self.id),
            "trip_id": str(self.trip_id),
            "event_type": self.event_type,
            "event_source": self.event_source,
            "actor_id": str(self.actor_id) if self.actor_id else None,
            "actor_type": self.actor_type,
            "event_data": self.event_data,
            "description": self.description,
            "location": {
                "latitude": self.location_latitude,
                "longitude": self.location_longitude
            } if self.location_latitude else None,
            "created_at": self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f"<TripEvent {self.event_type} for trip {self.trip_id}>"

