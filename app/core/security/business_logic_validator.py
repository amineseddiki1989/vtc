"""
Validateur de logique métier sécurisé pour l'application VTC.
Prévient les manipulations de données critiques côté client.
"""

import logging
from typing import Any, Dict, List, Optional, Union
from decimal import Decimal, InvalidOperation
from datetime import datetime, timezone
from enum import Enum

from pydantic import BaseModel, Field, validator
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)


class TripStatus(str, Enum):
    """Statuts de course autorisés."""
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class UserRole(str, Enum):
    """Rôles utilisateur autorisés."""
    PASSENGER = "passenger"
    DRIVER = "driver"
    ADMIN = "admin"


class SecureBusinessValidator:
    """Validateur de logique métier sécurisé."""
    
    # Limites de sécurité
    MAX_TRIP_DISTANCE = 1000.0  # km
    MIN_TRIP_DISTANCE = 0.1     # km
    MAX_TRIP_PRICE = 10000.0    # euros
    MIN_TRIP_PRICE = 1.0        # euros
    MAX_TRIP_DURATION = 86400   # secondes (24h)
    MIN_TRIP_DURATION = 60      # secondes (1 min)
    
    @classmethod
    def validate_trip_creation(cls, trip_data: Dict[str, Any], user_id: str, user_role: str) -> Dict[str, Any]:
        """Valide la création d'une course de manière sécurisée."""
        validated_data = {}
        
        # Validation du rôle utilisateur
        if user_role not in [UserRole.PASSENGER.value, UserRole.ADMIN.value]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls les passagers peuvent créer des courses"
            )
        
        # Validation et sécurisation des coordonnées
        validated_data.update(cls._validate_coordinates(trip_data))
        
        # Validation et calcul sécurisé de la distance
        validated_data["distance"] = cls._calculate_secure_distance(
            validated_data["pickup_latitude"],
            validated_data["pickup_longitude"],
            validated_data["destination_latitude"],
            validated_data["destination_longitude"]
        )
        
        # Validation et calcul sécurisé du prix
        validated_data["estimated_price"] = cls._calculate_secure_price(validated_data["distance"])
        
        # Sécurisation des IDs
        validated_data["passenger_id"] = cls._validate_user_id(user_id)
        validated_data["driver_id"] = None  # Assigné plus tard par le système
        
        # Statut initial sécurisé
        validated_data["status"] = TripStatus.PENDING.value
        
        # Timestamps sécurisés
        validated_data["created_at"] = datetime.now(timezone.utc)
        validated_data["updated_at"] = datetime.now(timezone.utc)
        
        # Validation des données optionnelles
        if "notes" in trip_data:
            validated_data["notes"] = cls._sanitize_text(trip_data["notes"], max_length=500)
        
        return validated_data
    
    @classmethod
    def validate_trip_update(cls, trip_data: Dict[str, Any], current_trip: Dict[str, Any], 
                           user_id: str, user_role: str) -> Dict[str, Any]:
        """Valide la mise à jour d'une course de manière sécurisée."""
        validated_data = {}
        
        # Vérification des permissions
        cls._check_trip_update_permissions(current_trip, user_id, user_role)
        
        # Validation du changement de statut
        if "status" in trip_data:
            validated_data["status"] = cls._validate_status_transition(
                current_trip.get("status"), trip_data["status"], user_role
            )
        
        # Validation du conducteur (seulement par admin ou système)
        if "driver_id" in trip_data:
            if user_role != UserRole.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Seuls les admins peuvent assigner des conducteurs"
                )
            validated_data["driver_id"] = cls._validate_user_id(trip_data["driver_id"])
        
        # Validation du prix (seulement par admin ou système)
        if "price" in trip_data:
            if user_role != UserRole.ADMIN.value:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Seuls les admins peuvent modifier le prix"
                )
            validated_data["price"] = cls._validate_price(trip_data["price"])
        
        # Validation de la distance (seulement par système)
        if "distance" in trip_data:
            # La distance ne peut être modifiée que par le système
            logger.warning(f"Tentative de modification de distance par utilisateur {user_id}")
            # On ignore cette modification
        
        # Mise à jour du timestamp
        validated_data["updated_at"] = datetime.now(timezone.utc)
        
        return validated_data
    
    @classmethod
    def validate_driver_assignment(cls, driver_id: str, trip_id: str, assigner_role: str) -> str:
        """Valide l'assignation d'un conducteur de manière sécurisée."""
        if assigner_role not in [UserRole.ADMIN.value, "system"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls les admins peuvent assigner des conducteurs"
            )
        
        return cls._validate_user_id(driver_id)
    
    @classmethod
    def validate_price_calculation(cls, distance: float, base_rate: float = 2.0, 
                                 per_km_rate: float = 1.5) -> Decimal:
        """Calcule le prix de manière sécurisée."""
        # Validation des paramètres
        if not isinstance(distance, (int, float)) or distance <= 0:
            raise ValueError("Distance invalide")
        
        if distance > cls.MAX_TRIP_DISTANCE:
            raise ValueError(f"Distance trop importante: {distance} km")
        
        # Calcul sécurisé avec Decimal pour éviter les erreurs de précision
        try:
            distance_decimal = Decimal(str(distance))
            base_rate_decimal = Decimal(str(base_rate))
            per_km_rate_decimal = Decimal(str(per_km_rate))
            
            price = base_rate_decimal + (distance_decimal * per_km_rate_decimal)
            
            # Validation du prix calculé
            if price > Decimal(str(cls.MAX_TRIP_PRICE)):
                raise ValueError(f"Prix calculé trop élevé: {price}")
            
            if price < Decimal(str(cls.MIN_TRIP_PRICE)):
                price = Decimal(str(cls.MIN_TRIP_PRICE))
            
            return price.quantize(Decimal('0.01'))  # Arrondir à 2 décimales
            
        except (InvalidOperation, ValueError) as e:
            logger.error(f"Erreur de calcul de prix: {e}")
            raise ValueError("Erreur de calcul de prix")
    
    @classmethod
    def _validate_coordinates(cls, trip_data: Dict[str, Any]) -> Dict[str, Any]:
        """Valide les coordonnées géographiques."""
        coords = {}
        
        # Validation des coordonnées de départ
        coords["pickup_latitude"] = cls._validate_latitude(trip_data.get("pickup_latitude"))
        coords["pickup_longitude"] = cls._validate_longitude(trip_data.get("pickup_longitude"))
        
        # Validation des coordonnées de destination
        coords["destination_latitude"] = cls._validate_latitude(trip_data.get("destination_latitude"))
        coords["destination_longitude"] = cls._validate_longitude(trip_data.get("destination_longitude"))
        
        return coords
    
    @classmethod
    def _validate_latitude(cls, lat: Any) -> float:
        """Valide une latitude."""
        try:
            lat_float = float(lat)
            if not -90.0 <= lat_float <= 90.0:
                raise ValueError(f"Latitude invalide: {lat_float}")
            return lat_float
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Latitude invalide"
            )
    
    @classmethod
    def _validate_longitude(cls, lon: Any) -> float:
        """Valide une longitude."""
        try:
            lon_float = float(lon)
            if not -180.0 <= lon_float <= 180.0:
                raise ValueError(f"Longitude invalide: {lon_float}")
            return lon_float
        except (TypeError, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Longitude invalide"
            )
    
    @classmethod
    def _calculate_secure_distance(cls, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calcule la distance de manière sécurisée (formule de Haversine)."""
        import math
        
        # Conversion en radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Formule de Haversine
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Rayon de la Terre en km
        earth_radius = 6371.0
        distance = earth_radius * c
        
        # Validation de la distance calculée
        if distance < cls.MIN_TRIP_DISTANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Distance trop courte: {distance:.2f} km"
            )
        
        if distance > cls.MAX_TRIP_DISTANCE:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Distance trop importante: {distance:.2f} km"
            )
        
        return round(distance, 2)
    
    @classmethod
    def _calculate_secure_price(cls, distance: float) -> Decimal:
        """Calcule le prix de manière sécurisée."""
        return cls.validate_price_calculation(distance)
    
    @classmethod
    def _validate_user_id(cls, user_id: Any) -> str:
        """Valide un ID utilisateur."""
        if not isinstance(user_id, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="ID utilisateur invalide"
            )
        
        # Validation du format UUID (exemple)
        import re
        uuid_pattern = r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$'
        if not re.match(uuid_pattern, user_id, re.IGNORECASE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format ID utilisateur invalide"
            )
        
        return user_id
    
    @classmethod
    def _validate_price(cls, price: Any) -> Decimal:
        """Valide un prix."""
        try:
            price_decimal = Decimal(str(price))
            
            if price_decimal < Decimal(str(cls.MIN_TRIP_PRICE)):
                raise ValueError(f"Prix trop bas: {price_decimal}")
            
            if price_decimal > Decimal(str(cls.MAX_TRIP_PRICE)):
                raise ValueError(f"Prix trop élevé: {price_decimal}")
            
            return price_decimal.quantize(Decimal('0.01'))
            
        except (InvalidOperation, ValueError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Prix invalide"
            )
    
    @classmethod
    def _sanitize_text(cls, text: Any, max_length: int = 1000) -> str:
        """Nettoie et valide un texte."""
        if not isinstance(text, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Texte invalide"
            )
        
        # Nettoyage des caractères dangereux
        import re
        # Supprimer les caractères de contrôle
        text = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', text)
        
        # Limiter la longueur
        if len(text) > max_length:
            text = text[:max_length]
        
        return text.strip()
    
    @classmethod
    def _check_trip_update_permissions(cls, current_trip: Dict[str, Any], 
                                     user_id: str, user_role: str):
        """Vérifie les permissions de mise à jour d'une course."""
        if user_role == UserRole.ADMIN.value:
            return  # Admin peut tout modifier
        
        # Passager ne peut modifier que ses propres courses
        if user_role == UserRole.PASSENGER.value:
            if current_trip.get("passenger_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous ne pouvez modifier que vos propres courses"
                )
        
        # Conducteur ne peut modifier que les courses qui lui sont assignées
        elif user_role == UserRole.DRIVER.value:
            if current_trip.get("driver_id") != user_id:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous ne pouvez modifier que vos courses assignées"
                )
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rôle non autorisé"
            )
    
    @classmethod
    def _validate_status_transition(cls, current_status: str, new_status: str, user_role: str) -> str:
        """Valide les transitions de statut autorisées."""
        if new_status not in [status.value for status in TripStatus]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Statut invalide: {new_status}"
            )
        
        # Définir les transitions autorisées par rôle
        allowed_transitions = {
            UserRole.PASSENGER.value: {
                TripStatus.PENDING.value: [TripStatus.CANCELLED.value],
                TripStatus.CONFIRMED.value: [TripStatus.CANCELLED.value]
            },
            UserRole.DRIVER.value: {
                TripStatus.CONFIRMED.value: [TripStatus.IN_PROGRESS.value],
                TripStatus.IN_PROGRESS.value: [TripStatus.COMPLETED.value]
            },
            UserRole.ADMIN.value: {
                # Admin peut faire toutes les transitions
                status.value: [s.value for s in TripStatus] 
                for status in TripStatus
            }
        }
        
        user_transitions = allowed_transitions.get(user_role, {})
        allowed_new_statuses = user_transitions.get(current_status, [])
        
        if new_status not in allowed_new_statuses:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Transition de {current_status} vers {new_status} non autorisée pour le rôle {user_role}"
            )
        
        return new_status


class SecureTripValidator(BaseModel):
    """Modèle Pydantic pour la validation sécurisée des courses."""
    
    pickup_latitude: float = Field(..., ge=-90, le=90)
    pickup_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('notes')
    def sanitize_notes(cls, v):
        if v:
            return SecureBusinessValidator._sanitize_text(v, 500)
        return v


class SecureTripUpdateValidator(BaseModel):
    """Modèle Pydantic pour la validation sécurisée des mises à jour de courses."""
    
    status: Optional[TripStatus] = None
    notes: Optional[str] = Field(None, max_length=500)
    
    @validator('notes')
    def sanitize_notes(cls, v):
        if v:
            return SecureBusinessValidator._sanitize_text(v, 500)
        return v

