"""
Validateur de logique métier - Fix Pydantic V2
Module de validation des règles métier avec support Pydantic V2
"""

from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta, time
from decimal import Decimal
from pydantic import BaseModel, Field, validator, root_validator
from enum import Enum
import re
from app.utils.production_logger import ProductionLogger

logger = ProductionLogger(__name__)

class BookingStatus(str, Enum):
    """Statuts de réservation"""
    PENDING = "pending"
    CONFIRMED = "confirmed" 
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"

class VehicleType(str, Enum):
    """Types de véhicules"""
    STANDARD = "standard"
    PREMIUM = "premium"
    VAN = "van"
    LUXURY = "luxury"

class BookingValidationModel(BaseModel):
    """
    Modèle de validation pour les réservations
    Compatible Pydantic V2
    """
    pickup_address: str = Field(..., min_length=5, max_length=500)
    destination_address: str = Field(..., min_length=5, max_length=500)
    pickup_datetime: datetime = Field(...)
    passenger_count: int = Field(..., ge=1, le=8)
    vehicle_type: VehicleType = Field(default=VehicleType.STANDARD)
    special_requirements: Optional[str] = Field(None, max_length=1000)
    estimated_price: Optional[Decimal] = Field(None, ge=0)

    class Config:
        # Pydantic V2 compatibility
        json_encoders = {
            datetime: lambda v: v.isoformat(),
            Decimal: lambda v: float(v)
        }
        use_enum_values = True

    @validator('pickup_datetime')
    def validate_pickup_time(cls, v):
        """Validation de la date/heure de prise en charge"""
        now = datetime.now()

        # Minimum 15 minutes dans le futur
        min_time = now + timedelta(minutes=15)
        if v < min_time:
            raise ValueError("La réservation doit être au minimum 15 minutes dans le futur")

        # Maximum 30 jours dans le futur
        max_time = now + timedelta(days=30)
        if v > max_time:
            raise ValueError("La réservation ne peut pas être plus de 30 jours dans le futur")

        # Vérifier les heures de service (5h00 - 1h00)
        pickup_time = v.time()
        service_start = time(5, 0)
        service_end = time(1, 0)

        if not (pickup_time >= service_start or pickup_time <= service_end):
            raise ValueError("Les réservations ne sont acceptées qu'entre 5h00 et 1h00")

        return v

    @validator('pickup_address', 'destination_address')
    def validate_addresses(cls, v):
        """Validation des adresses"""
        if not v or v.strip() == "":
            raise ValueError("L'adresse ne peut pas être vide")

        # Vérification basique du format d'adresse française
        if not re.search(r'\d', v):  # Doit contenir au moins un chiffre
            raise ValueError("L'adresse doit contenir un numéro")

        return v.strip()

    @validator('passenger_count')
    def validate_passenger_count(cls, v, values):
        """Validation du nombre de passagers selon le type de véhicule"""
        vehicle_type = values.get('vehicle_type', VehicleType.STANDARD)

        max_passengers = {
            VehicleType.STANDARD: 4,
            VehicleType.PREMIUM: 4,
            VehicleType.VAN: 8,
            VehicleType.LUXURY: 4
        }

        max_allowed = max_passengers.get(vehicle_type, 4)
        if v > max_allowed:
            raise ValueError(f"Le véhicule {vehicle_type} accepte maximum {max_allowed} passagers")

        return v

    @root_validator
    def validate_booking_logic(cls, values):
        """Validation globale de la logique de réservation"""
        pickup_addr = values.get('pickup_address', '')
        dest_addr = values.get('destination_address', '')

        # Vérifier que les adresses sont différentes
        if pickup_addr.strip().lower() == dest_addr.strip().lower():
            raise ValueError("L'adresse de départ et de destination doivent être différentes")

        # Validation de distance minimum (simulation)
        if len(pickup_addr) + len(dest_addr) < 20:  # Heuristique simple
            raise ValueError("La distance semble trop courte pour justifier un VTC")

        return values

class PriceValidationModel(BaseModel):
    """Modèle de validation pour les tarifs"""
    base_price: Decimal = Field(..., ge=5.0, le=1000.0)
    distance_km: Decimal = Field(..., ge=0.1, le=500.0)
    duration_minutes: int = Field(..., ge=5, le=480)  # Max 8h
    vehicle_type: VehicleType
    time_multiplier: Decimal = Field(default=Decimal('1.0'), ge=0.8, le=3.0)

    @validator('base_price')
    def validate_base_price(cls, v, values):
        """Validation du prix de base selon le type de véhicule"""
        vehicle_type = values.get('vehicle_type', VehicleType.STANDARD)

        min_prices = {
            VehicleType.STANDARD: Decimal('5.0'),
            VehicleType.PREMIUM: Decimal('8.0'),
            VehicleType.VAN: Decimal('12.0'),
            VehicleType.LUXURY: Decimal('15.0')
        }

        min_price = min_prices.get(vehicle_type, Decimal('5.0'))
        if v < min_price:
            raise ValueError(f"Prix minimum pour {vehicle_type}: {min_price}€")

        return v

    @validator('time_multiplier')
    def validate_time_multiplier(cls, v, values):
        """Validation du multiplicateur temporel"""
        pickup_time = values.get('pickup_datetime')
        if pickup_time:
            hour = pickup_time.hour

            # Heures de pointe: 7-9h et 17-19h
            if hour in [7, 8, 17, 18] and v < 1.2:
                raise ValueError("Multiplicateur minimum de 1.2 en heures de pointe")

            # Nuit (22h-6h): multiplicateur nuit
            if (hour >= 22 or hour < 6) and v < 1.5:
                raise ValueError("Multiplicateur minimum de 1.5 la nuit")

        return v

class DriverValidationModel(BaseModel):
    """Validation pour les chauffeurs"""
    license_number: str = Field(..., min_length=8, max_length=20)
    phone_number: str = Field(..., regex=r'^(\+33|0)[1-9](\d{8})$')
    vehicle_registration: str = Field(..., min_length=7, max_length=10)
    insurance_expiry: datetime = Field(...)
    medical_certificate_expiry: datetime = Field(...)

    @validator('license_number')
    def validate_license(cls, v):
        """Validation du numéro de permis"""
        # Format français basique
        if not re.match(r'^[0-9]{12}$|^[A-Z0-9]{8,15}$', v.upper()):
            raise ValueError("Format de permis de conduire invalide")
        return v.upper()

    @validator('insurance_expiry', 'medical_certificate_expiry')
    def validate_expiry_dates(cls, v):
        """Validation des dates d'expiration"""
        if v <= datetime.now():
            raise ValueError("Le document doit être valide (non expiré)")

        # Maximum 5 ans dans le futur
        max_date = datetime.now() + timedelta(days=5*365)
        if v > max_date:
            raise ValueError("Date d'expiration trop éloignée")

        return v

class BusinessLogicValidator:
    """Validateur principal de la logique métier"""

    @staticmethod
    def validate_booking(booking_data: Dict) -> Dict[str, Any]:
        """Valide une réservation complète"""
        try:
            # Validation du modèle
            validated_booking = BookingValidationModel(**booking_data)

            # Validations métier supplémentaires
            validation_result = {
                "valid": True,
                "data": validated_booking.dict(),
                "warnings": [],
                "errors": []
            }

            # Vérification de disponibilité (simulation)
            if BusinessLogicValidator._check_driver_availability(validated_booking.pickup_datetime):
                validation_result["warnings"].append("Peu de chauffeurs disponibles à cette heure")

            logger.info("Réservation validée avec succès", booking_id=booking_data.get('id'))
            return validation_result

        except Exception as e:
            logger.error(f"Erreur de validation de réservation: {e}")
            return {
                "valid": False,
                "errors": [str(e)],
                "data": None
            }

    @staticmethod
    def validate_price(price_data: Dict) -> Dict[str, Any]:
        """Valide un calcul de prix"""
        try:
            validated_price = PriceValidationModel(**price_data)

            # Calcul du prix final
            final_price = (
                validated_price.base_price +
                (validated_price.distance_km * Decimal('1.5')) +  # 1.5€/km
                (Decimal(validated_price.duration_minutes) / 60 * Decimal('25'))  # 25€/h
            ) * validated_price.time_multiplier

            return {
                "valid": True,
                "final_price": final_price,
                "breakdown": {
                    "base": validated_price.base_price,
                    "distance": validated_price.distance_km * Decimal('1.5'),
                    "time": Decimal(validated_price.duration_minutes) / 60 * Decimal('25'),
                    "multiplier": validated_price.time_multiplier
                }
            }

        except Exception as e:
            logger.error(f"Erreur de validation de prix: {e}")
            return {
                "valid": False,
                "error": str(e)
            }

    @staticmethod
    def validate_driver(driver_data: Dict) -> Dict[str, Any]:
        """Valide les données d'un chauffeur"""
        try:
            validated_driver = DriverValidationModel(**driver_data)

            return {
                "valid": True,
                "data": validated_driver.dict(),
                "eligibility_status": "approved"
            }

        except Exception as e:
            logger.error(f"Erreur de validation de chauffeur: {e}")
            return {
                "valid": False,
                "error": str(e),
                "eligibility_status": "rejected"
            }

    @staticmethod
    def _check_driver_availability(pickup_time: datetime) -> bool:
        """Vérifie la disponibilité des chauffeurs (simulation)"""
        # Simulation basique
        hour = pickup_time.hour
        # Moins de chauffeurs disponibles la nuit et aux heures de pointe
        return hour < 6 or hour > 22 or hour in [8, 9, 17, 18, 19]

# Fonctions utilitaires
def validate_booking_request(booking_data: Dict) -> Dict:
    """Fonction de convenance pour valider une réservation"""
    return BusinessLogicValidator.validate_booking(booking_data)

def calculate_trip_price(distance: float, duration: int, vehicle_type: str, pickup_time: datetime) -> Dict:
    """Calcule et valide le prix d'un trajet"""
    price_data = {
        "base_price": 8.0,
        "distance_km": distance,
        "duration_minutes": duration,
        "vehicle_type": vehicle_type,
        "pickup_datetime": pickup_time
    }

    return BusinessLogicValidator.validate_price(price_data)
