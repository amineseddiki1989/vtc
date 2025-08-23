"""
Schémas Pydantic pour les courses.
"""

from pydantic import BaseModel, Field, validator, ConfigDict
from typing import Optional, List
from datetime import datetime
from enum import Enum

from ..models.trip import TripStatus, VehicleType


class TripEstimate(BaseModel):
    """Estimation de course."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "distance_km": 12.5,
                "duration_minutes": 25,
                "price": 850.0,
                "currency": "DZD"
            }
        }
    )
    
    distance_km: float = Field(..., description="Distance en kilomètres")
    duration_minutes: int = Field(..., description="Durée estimée en minutes")
    price: float = Field(..., description="Prix estimé")
    currency: str = Field(default="DZD", description="Devise")


class TripCreate(BaseModel):
    """Données pour créer une course."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "pickup_latitude": 36.7538,
                "pickup_longitude": 3.0588,
                "pickup_address": "Place des Martyrs, Alger Centre",
                "destination_latitude": 36.7755,
                "destination_longitude": 3.0597,
                "destination_address": "Aéroport Houari Boumediene, Alger",
                "vehicle_type": "standard",
                "notes": "Merci d'attendre devant l'entrée principale"
            }
        }
    )
    
    pickup_latitude: float = Field(..., ge=-90, le=90, description="Latitude de prise en charge")
    pickup_longitude: float = Field(..., ge=-180, le=180, description="Longitude de prise en charge")
    pickup_address: str = Field(..., min_length=5, max_length=500, description="Adresse de prise en charge")
    
    destination_latitude: float = Field(..., ge=-90, le=90, description="Latitude de destination")
    destination_longitude: float = Field(..., ge=-180, le=180, description="Longitude de destination")
    destination_address: str = Field(..., min_length=5, max_length=500, description="Adresse de destination")
    
    vehicle_type: VehicleType = Field(default=VehicleType.STANDARD, description="Type de véhicule")
    notes: Optional[str] = Field(None, max_length=1000, description="Notes additionnelles")
    
    @validator('pickup_address', 'destination_address')
    def validate_addresses(cls, v):
        if not v or v.strip() == "":
            raise ValueError("L'adresse ne peut pas être vide")
        return v.strip()


class TripUpdate(BaseModel):
    """Mise à jour d'une course."""
    status: Optional[TripStatus] = None
    notes: Optional[str] = Field(None, max_length=1000)
    cancellation_reason: Optional[str] = Field(None, max_length=500)


class TripResponse(BaseModel):
    """Réponse course complète."""
    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": "trip_123456789",
                "passenger_id": "user_passenger_123",
                "driver_id": "user_driver_456",
                "pickup_latitude": 36.7538,
                "pickup_longitude": 3.0588,
                "pickup_address": "Place des Martyrs, Alger Centre",
                "destination_latitude": 36.7755,
                "destination_longitude": 3.0597,
                "destination_address": "Aéroport Houari Boumediene, Alger",
                "status": "completed",
                "vehicle_type": "standard",
                "estimated_price": 850.0,
                "final_price": 850.0,
                "distance_km": 12.5,
                "duration_minutes": 25,
                "requested_at": "2024-01-15T10:30:00Z",
                "accepted_at": "2024-01-15T10:31:00Z",
                "started_at": "2024-01-15T10:35:00Z",
                "completed_at": "2024-01-15T11:00:00Z"
            }
        }
    )
    
    id: str
    
    # Relations
    passenger_id: str
    driver_id: Optional[str] = None
    
    # Localisation
    pickup_latitude: float
    pickup_longitude: float
    pickup_address: str
    destination_latitude: float
    destination_longitude: float
    destination_address: str
    
    # Informations course
    status: TripStatus
    vehicle_type: VehicleType
    
    # Tarification
    estimated_price: float
    final_price: Optional[float] = None
    distance_km: float
    duration_minutes: int
    
    # Timestamps
    requested_at: datetime
    accepted_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    cancelled_at: Optional[datetime] = None
    
    # Informations additionnelles
    cancellation_reason: Optional[str] = None
    notes: Optional[str] = None


class TripListResponse(BaseModel):
    """Liste de courses avec pagination."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "trips": [],
                "total": 150,
                "page": 1,
                "per_page": 20,
                "has_next": True,
                "has_prev": False
            }
        }
    )
    
    trips: List[TripResponse]
    total: int
    page: int
    per_page: int
    has_next: bool
    has_prev: bool


class TripStats(BaseModel):
    """Statistiques de courses."""
    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "total_trips": 150,
                "completed_trips": 142,
                "cancelled_trips": 8,
                "total_distance_km": 1250.5,
                "total_earnings": 45600.0,
                "average_rating": 4.7
            }
        }
    )
    
    total_trips: int
    completed_trips: int
    cancelled_trips: int
    total_distance_km: float
    total_earnings: float
    average_rating: float

