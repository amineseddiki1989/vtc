"""
Validateur de logique métier sécurisé pour l'application VTC.
Valide toutes les données critiques côté serveur pour éviter les manipulations.
"""

import re
import math
from typing import Any, Dict, List, Optional, Union, Tuple
from decimal import Decimal, InvalidOperation
from datetime import datetime, timedelta
from fastapi import HTTPException, status
from pydantic import BaseModel, validator
import phonenumbers
from phonenumbers import NumberParseException


class ValidationError(Exception):
    """Exception personnalisée pour les erreurs de validation."""
    pass


class BusinessValidator:
    """Validateur centralisé pour la logique métier VTC."""
    
    # === CONSTANTES DE VALIDATION ===
    
    # Limites géographiques (France métropolitaine + DOM-TOM)
    MIN_LATITUDE = -21.4  # Réunion
    MAX_LATITUDE = 51.1   # Nord de la France
    MIN_LONGITUDE = -63.2 # Martinique
    MAX_LONGITUDE = 9.6   # Est de la France
    
    # Limites de distance et prix
    MIN_DISTANCE_KM = 0.1
    MAX_DISTANCE_KM = 1000.0
    MIN_PRICE_EUR = 1.0
    MAX_PRICE_EUR = 10000.0
    
    # Limites temporelles
    MAX_TRIP_DURATION_HOURS = 24
    MAX_BOOKING_ADVANCE_DAYS = 30
    
    # Patterns de validation
    PHONE_PATTERN = re.compile(r'^\+?[1-9]\d{1,14}$')
    EMAIL_PATTERN = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')
    LICENSE_PATTERN = re.compile(r'^[A-Z0-9]{8,15}$')
    
    @staticmethod
    def validate_coordinates(latitude: float, longitude: float, field_name: str = "coordonnées") -> Tuple[float, float]:
        """
        Valide des coordonnées GPS.
        
        Args:
            latitude: Latitude à valider
            longitude: Longitude à valider
            field_name: Nom du champ pour les erreurs
            
        Returns:
            Tuple des coordonnées validées
            
        Raises:
            HTTPException: Si les coordonnées sont invalides
        """
        try:
            lat = float(latitude)
            lon = float(longitude)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: coordonnées invalides (format numérique requis)"
            )
        
        # Validation des limites générales
        if not (-90 <= lat <= 90):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: latitude invalide ({lat}). Doit être entre -90 et 90"
            )
        
        if not (-180 <= lon <= 180):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: longitude invalide ({lon}). Doit être entre -180 et 180"
            )
        
        # Validation des limites géographiques pour la France
        if not (BusinessValidator.MIN_LATITUDE <= lat <= BusinessValidator.MAX_LATITUDE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: latitude hors zone de service ({lat})"
            )
        
        if not (BusinessValidator.MIN_LONGITUDE <= lon <= BusinessValidator.MAX_LONGITUDE):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: longitude hors zone de service ({lon})"
            )
        
        return lat, lon
    
    @staticmethod
    def validate_distance(distance: Union[int, float], field_name: str = "distance") -> float:
        """
        Valide une distance.
        
        Args:
            distance: Distance à valider (en km)
            field_name: Nom du champ pour les erreurs
            
        Returns:
            Distance validée
            
        Raises:
            HTTPException: Si la distance est invalide
        """
        try:
            dist = float(distance)
        except (ValueError, TypeError):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: format invalide (nombre requis)"
            )
        
        if dist < BusinessValidator.MIN_DISTANCE_KM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: trop courte ({dist} km). Minimum: {BusinessValidator.MIN_DISTANCE_KM} km"
            )
        
        if dist > BusinessValidator.MAX_DISTANCE_KM:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: trop longue ({dist} km). Maximum: {BusinessValidator.MAX_DISTANCE_KM} km"
            )
        
        return round(dist, 2)
    
    @staticmethod
    def validate_price(price: Union[int, float, str, Decimal], field_name: str = "prix") -> Decimal:
        """
        Valide un prix.
        
        Args:
            price: Prix à valider (en EUR)
            field_name: Nom du champ pour les erreurs
            
        Returns:
            Prix validé en Decimal
            
        Raises:
            HTTPException: Si le prix est invalide
        """
        try:
            if isinstance(price, str):
                # Nettoyer la chaîne (enlever espaces, symboles)
                price_clean = re.sub(r'[^\d.,]', '', price)
                price_clean = price_clean.replace(',', '.')
                price_decimal = Decimal(price_clean)
            else:
                price_decimal = Decimal(str(price))
        except (ValueError, TypeError, InvalidOperation):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: format invalide (nombre requis)"
            )
        
        if price_decimal < Decimal(str(BusinessValidator.MIN_PRICE_EUR)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: trop bas ({price_decimal} €). Minimum: {BusinessValidator.MIN_PRICE_EUR} €"
            )
        
        if price_decimal > Decimal(str(BusinessValidator.MAX_PRICE_EUR)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: trop élevé ({price_decimal} €). Maximum: {BusinessValidator.MAX_PRICE_EUR} €"
            )
        
        return price_decimal.quantize(Decimal('0.01'))
    
    @staticmethod
    def validate_user_id(user_id: Union[str, int], field_name: str = "ID utilisateur") -> str:
        """
        Valide un ID utilisateur.
        
        Args:
            user_id: ID à valider
            field_name: Nom du champ pour les erreurs
            
        Returns:
            ID validé
            
        Raises:
            HTTPException: Si l'ID est invalide
        """
        if not user_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: requis"
            )
        
        user_id_str = str(user_id).strip()
        
        # Validation du format UUID ou ID numérique
        if not (user_id_str.isdigit() or 
                re.match(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$', user_id_str)):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"{field_name}: format invalide"
            )
        
        return user_id_str
    
    @staticmethod
    def validate_phone_number(phone: str, country_code: str = "FR") -> str:
        """
        Valide un numéro de téléphone.
        
        Args:
            phone: Numéro de téléphone
            country_code: Code pays (défaut: FR)
            
        Returns:
            Numéro validé au format international
            
        Raises:
            HTTPException: Si le numéro est invalide
        """
        if not phone:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Numéro de téléphone requis"
            )
        
        try:
            # Parser le numéro avec phonenumbers
            parsed_number = phonenumbers.parse(phone, country_code)
            
            # Vérifier la validité
            if not phonenumbers.is_valid_number(parsed_number):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Numéro de téléphone invalide"
                )
            
            # Retourner au format international
            return phonenumbers.format_number(parsed_number, phonenumbers.PhoneNumberFormat.E164)
            
        except NumberParseException:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Format de numéro de téléphone invalide"
            )
    
    @staticmethod
    def calculate_distance_haversine(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calcule la distance entre deux points GPS avec la formule de Haversine.
        
        Args:
            lat1, lon1: Coordonnées du point 1
            lat2, lon2: Coordonnées du point 2
            
        Returns:
            Distance en kilomètres
        """
        # Rayon de la Terre en km
        R = 6371.0
        
        # Convertir en radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Différences
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        # Formule de Haversine
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        distance = R * c
        return round(distance, 2)
    
    @staticmethod
    def validate_trip_distance(pickup_lat: float, pickup_lon: float, 
                             dropoff_lat: float, dropoff_lon: float,
                             declared_distance: float = None) -> float:
        """
        Valide la distance d'une course en calculant la distance réelle.
        
        Args:
            pickup_lat, pickup_lon: Coordonnées de prise en charge
            dropoff_lat, dropoff_lon: Coordonnées de destination
            declared_distance: Distance déclarée (optionnelle)
            
        Returns:
            Distance calculée et validée
            
        Raises:
            HTTPException: Si la distance est incohérente
        """
        # Valider les coordonnées
        BusinessValidator.validate_coordinates(pickup_lat, pickup_lon, "point de prise en charge")
        BusinessValidator.validate_coordinates(dropoff_lat, dropoff_lon, "point de destination")
        
        # Calculer la distance réelle
        calculated_distance = BusinessValidator.calculate_distance_haversine(
            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon
        )
        
        # Valider la distance calculée
        validated_distance = BusinessValidator.validate_distance(calculated_distance)
        
        # Si une distance est déclarée, vérifier la cohérence
        if declared_distance is not None:
            declared_validated = BusinessValidator.validate_distance(declared_distance, "distance déclarée")
            
            # Tolérance de 20% pour les variations de route
            tolerance = 0.20
            min_expected = calculated_distance * (1 - tolerance)
            max_expected = calculated_distance * (1 + tolerance)
            
            if not (min_expected <= declared_validated <= max_expected):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Distance déclarée incohérente ({declared_validated} km). "
                           f"Distance calculée: {calculated_distance} km (±{tolerance*100}%)"
                )
        
        return validated_distance
    
    @staticmethod
    def validate_trip_request(pickup_lat: float, pickup_lon: float,
                            dropoff_lat: float, dropoff_lon: float,
                            passenger_id: str, driver_id: str = None,
                            declared_distance: float = None,
                            declared_price: float = None) -> Dict[str, Any]:
        """
        Valide une demande de course complète.
        
        Args:
            pickup_lat, pickup_lon: Coordonnées de prise en charge
            dropoff_lat, dropoff_lon: Coordonnées de destination
            passenger_id: ID du passager
            driver_id: ID du conducteur (optionnel)
            declared_distance: Distance déclarée (optionnelle)
            declared_price: Prix déclaré (optionnel)
            
        Returns:
            Dictionnaire avec les données validées
        """
        # Valider les IDs
        validated_passenger_id = BusinessValidator.validate_user_id(passenger_id, "ID passager")
        validated_driver_id = None
        if driver_id:
            validated_driver_id = BusinessValidator.validate_user_id(driver_id, "ID conducteur")
        
        # Valider la distance
        validated_distance = BusinessValidator.validate_trip_distance(
            pickup_lat, pickup_lon, dropoff_lat, dropoff_lon, declared_distance
        )
        
        # Valider le prix si fourni
        validated_price = None
        if declared_price is not None:
            validated_price = BusinessValidator.validate_price(declared_price)
        
        return {
            "pickup_coordinates": (pickup_lat, pickup_lon),
            "dropoff_coordinates": (dropoff_lat, dropoff_lon),
            "passenger_id": validated_passenger_id,
            "driver_id": validated_driver_id,
            "distance_km": validated_distance,
            "price_eur": validated_price,
            "validation_timestamp": datetime.utcnow().isoformat()
        }


# Fonctions utilitaires pour l'intégration
def validate_coordinates_endpoint(latitude: float, longitude: float) -> Tuple[float, float]:
    """Fonction utilitaire pour valider des coordonnées dans un endpoint."""
    return BusinessValidator.validate_coordinates(latitude, longitude)


def validate_distance_endpoint(distance: Union[int, float]) -> float:
    """Fonction utilitaire pour valider une distance dans un endpoint."""
    return BusinessValidator.validate_distance(distance)


def validate_price_endpoint(price: Union[int, float, str, Decimal]) -> Decimal:
    """Fonction utilitaire pour valider un prix dans un endpoint."""
    return BusinessValidator.validate_price(price)


def validate_user_id_endpoint(user_id: Union[str, int]) -> str:
    """Fonction utilitaire pour valider un ID utilisateur dans un endpoint."""
    return BusinessValidator.validate_user_id(user_id)

