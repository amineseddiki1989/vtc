"""
Service professionnel de gestion des courses avec métriques intégrées.
"""

import uuid
from datetime import datetime, timedelta
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_, func
from geopy.distance import geodesic
import math

from ..models.trip import Trip, TripStatus, VehicleType
from ..models.user import User, UserRole
from ..models.location import DriverLocation
from ..schemas.trip import TripCreate, TripUpdate, TripEstimate
from .pricing_service import PricingService
from .location_service import LocationService
from ..services.metrics_service import get_metrics_collector
from ..models.metrics import MetricType, MetricCategory
from ..core.monitoring.decorators import monitor_business_operation, monitor_function, MetricsContext


class TripService:
    """Service de gestion des courses avec monitoring intégré."""
    
    def __init__(self, db: Session):
        self.db = db
        self.pricing_service = PricingService()
        self.location_service = LocationService(db)
        self.collector = get_metrics_collector()
    
    @monitor_business_operation("trip_estimation", "trip", track_value=True, value_field="price")
    def estimate_trip(self, trip_data: TripCreate) -> TripEstimate:
        """Estime le coût et la durée d'une course."""
        # Calcul de la distance
        pickup = (trip_data.pickup_latitude, trip_data.pickup_longitude)
        destination = (trip_data.destination_latitude, trip_data.destination_longitude)
        distance_km = geodesic(pickup, destination).kilometers
        
        # Estimation de la durée (vitesse moyenne 30 km/h en ville)
        duration_minutes = max(int(distance_km * 2), 5)  # Minimum 5 minutes
        
        # Calcul du prix
        price = self.pricing_service.calculate_price(
            distance_km=distance_km,
            duration_minutes=duration_minutes,
            vehicle_type=trip_data.vehicle_type
        )
        
        # Métriques spécifiques à l'estimation
        self.collector.record_metric(
            name="trip_estimation_distance_km",
            value=distance_km,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "vehicle_type": trip_data.vehicle_type.value,
                "distance_range": self._get_distance_range(distance_km)
            },
            description="Distance estimée pour une course"
        )
        
        self.collector.record_metric(
            name="trip_estimation_price",
            value=price,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "vehicle_type": trip_data.vehicle_type.value,
                "price_range": self._get_price_range(price)
            },
            description="Prix estimé pour une course"
        )
        
        return TripEstimate(
            distance_km=round(distance_km, 2),
            duration_minutes=duration_minutes,
            price=round(price, 2)
        )
    
    def create_trip(self, trip_data: TripCreate, passenger_id: str) -> Trip:
        """Crée une nouvelle course."""
        # Vérifier que l'utilisateur est un passager
        passenger = self.db.query(User).filter(
            and_(User.id == passenger_id, User.role == UserRole.PASSENGER)
        ).first()
        
        if not passenger:
            raise ValueError("Utilisateur non trouvé ou non autorisé")
        
        # Estimer la course
        estimate = self.estimate_trip(trip_data)
        
        # Créer la course
        trip = Trip(
            id=f"trip_{uuid.uuid4().hex[:12]}",
            passenger_id=passenger_id,
            pickup_latitude=trip_data.pickup_latitude,
            pickup_longitude=trip_data.pickup_longitude,
            pickup_address=trip_data.pickup_address,
            destination_latitude=trip_data.destination_latitude,
            destination_longitude=trip_data.destination_longitude,
            destination_address=trip_data.destination_address,
            vehicle_type=trip_data.vehicle_type,
            estimated_price=estimate.price,
            distance_km=estimate.distance_km,
            duration_minutes=estimate.duration_minutes,
            notes=trip_data.notes,
            status=TripStatus.REQUESTED
        )
        
        self.db.add(trip)
        self.db.commit()
        self.db.refresh(trip)
        
        return trip
    
    def find_available_drivers(self, trip: Trip, radius_km: float = 10) -> List[User]:
        """Trouve les conducteurs disponibles dans un rayon donné."""
        # Coordonnées de prise en charge
        pickup_lat = trip.pickup_latitude
        pickup_lon = trip.pickup_longitude
        
        # Requête pour trouver les conducteurs disponibles
        drivers = self.db.query(User).join(DriverLocation).filter(
            and_(
                User.role == UserRole.DRIVER,
                User.status == "active",
                DriverLocation.is_available == True,
                DriverLocation.is_online == True,
                # Filtre approximatif par coordonnées (optimisation)
                DriverLocation.latitude.between(pickup_lat - 0.1, pickup_lat + 0.1),
                DriverLocation.longitude.between(pickup_lon - 0.1, pickup_lon + 0.1)
            )
        ).all()
        
        # Filtrage précis par distance
        available_drivers = []
        for driver in drivers:
            driver_location = (driver.location.latitude, driver.location.longitude)
            pickup_location = (pickup_lat, pickup_lon)
            distance = geodesic(driver_location, pickup_location).kilometers
            
            if distance <= radius_km:
                available_drivers.append((driver, distance))
        
        # Trier par distance
        available_drivers.sort(key=lambda x: x[1])
        
        return [driver for driver, _ in available_drivers[:10]]  # Max 10 conducteurs
    
    def assign_driver(self, trip_id: str, driver_id: str) -> Trip:
        """Assigne un conducteur à une course."""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.status != TripStatus.REQUESTED:
            raise ValueError("Course déjà assignée ou terminée")
        
        # Vérifier que le conducteur est disponible
        driver = self.db.query(User).filter(
            and_(User.id == driver_id, User.role == UserRole.DRIVER)
        ).first()
        
        if not driver or not driver.location or not driver.location.is_available:
            raise ValueError("Conducteur non disponible")
        
        # Assigner le conducteur
        trip.driver_id = driver_id
        trip.status = TripStatus.ACCEPTED
        trip.accepted_at = datetime.utcnow()
        
        # Marquer le conducteur comme occupé
        driver.location.is_available = False
        
        self.db.commit()
        self.db.refresh(trip)
        
        return trip
    
    def start_trip(self, trip_id: str, driver_id: str) -> Trip:
        """Démarre une course."""
        trip = self.db.query(Trip).filter(
            and_(Trip.id == trip_id, Trip.driver_id == driver_id)
        ).first()
        
        if not trip:
            raise ValueError("Course non trouvée ou non autorisée")
        
        if trip.status != TripStatus.ACCEPTED:
            raise ValueError("Course non acceptée")
        
        trip.status = TripStatus.IN_PROGRESS
        trip.started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(trip)
        
        return trip
    
    def complete_trip(self, trip_id: str, driver_id: str) -> Trip:
        """Termine une course."""
        trip = self.db.query(Trip).filter(
            and_(Trip.id == trip_id, Trip.driver_id == driver_id)
        ).first()
        
        if not trip:
            raise ValueError("Course non trouvée ou non autorisée")
        
        if trip.status != TripStatus.IN_PROGRESS:
            raise ValueError("Course non en cours")
        
        # Calculer le prix final (peut différer de l'estimation)
        actual_duration = (datetime.utcnow() - trip.started_at).total_seconds() / 60
        final_price = self.pricing_service.calculate_final_price(
            estimated_price=trip.estimated_price,
            actual_duration_minutes=actual_duration,
            distance_km=trip.distance_km
        )
        
        trip.status = TripStatus.COMPLETED
        trip.completed_at = datetime.utcnow()
        trip.final_price = final_price
        
        # Libérer le conducteur
        if trip.driver and trip.driver.location:
            trip.driver.location.is_available = True
        
        self.db.commit()
        self.db.refresh(trip)
        
        return trip
    
    def cancel_trip(self, trip_id: str, user_id: str, reason: str) -> Trip:
        """Annule une course."""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        # Vérifier les permissions
        if trip.passenger_id != user_id and trip.driver_id != user_id:
            raise ValueError("Non autorisé à annuler cette course")
        
        if trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
            raise ValueError("Course déjà terminée ou annulée")
        
        trip.status = TripStatus.CANCELLED
        trip.cancelled_at = datetime.utcnow()
        trip.cancellation_reason = reason
        
        # Libérer le conducteur si assigné
        if trip.driver_id and trip.driver and trip.driver.location:
            trip.driver.location.is_available = True
        
        self.db.commit()
        self.db.refresh(trip)
        
        return trip
    
    def get_user_trips(
        self, 
        user_id: str, 
        status: Optional[TripStatus] = None,
        limit: int = 20,
        offset: int = 0
    ) -> Tuple[List[Trip], int]:
        """Récupère les courses d'un utilisateur."""
        query = self.db.query(Trip).filter(
            or_(Trip.passenger_id == user_id, Trip.driver_id == user_id)
        )
        
        if status:
            query = query.filter(Trip.status == status)
        
        total = query.count()
        trips = query.order_by(Trip.requested_at.desc()).offset(offset).limit(limit).all()
        
        return trips, total
    
    def get_trip_by_id(self, trip_id: str, user_id: str) -> Optional[Trip]:
        """Récupère une course par ID."""
        return self.db.query(Trip).filter(
            and_(
                Trip.id == trip_id,
                or_(Trip.passenger_id == user_id, Trip.driver_id == user_id)
            )
        ).first()
    
    def update_trip(self, trip_id: str, trip_update: TripUpdate, user_id: str) -> Trip:
        """Met à jour une course."""
        trip = self.get_trip_by_id(trip_id, user_id)
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        # Mise à jour des champs autorisés
        if trip_update.notes is not None:
            trip.notes = trip_update.notes
        
        if trip_update.cancellation_reason is not None:
            trip.cancellation_reason = trip_update.cancellation_reason
        
        self.db.commit()
        self.db.refresh(trip)
        
        return trip


    
    def _get_distance_range(self, distance_km: float) -> str:
        """Catégorise la distance pour les métriques."""
        if distance_km < 2:
            return "very_short"
        elif distance_km < 5:
            return "short"
        elif distance_km < 15:
            return "medium"
        elif distance_km < 30:
            return "long"
        else:
            return "very_long"
    
    def _get_price_range(self, price: float) -> str:
        """Catégorise le prix pour les métriques."""
        if price < 10:
            return "low"
        elif price < 25:
            return "medium"
        elif price < 50:
            return "high"
        else:
            return "premium"
    
    @monitor_business_operation("trip_creation", "trip", track_value=True, value_field="estimated_price")
    def create_trip(self, trip_data: TripCreate, passenger_id: str) -> Trip:
        """Crée une nouvelle course avec métriques."""
        with MetricsContext("trip_creation", MetricCategory.BUSINESS, 
                           labels={"vehicle_type": trip_data.vehicle_type.value},
                           description="Création d'une course") as ctx:
            
            # Vérifier que l'utilisateur est un passager
            passenger = self.db.query(User).filter(
                and_(User.id == passenger_id, User.role == UserRole.PASSENGER)
            ).first()
            
            if not passenger:
                self.collector.record_metric(
                    name="trip_creation_unauthorized",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels={"reason": "invalid_passenger"},
                    user_id=passenger_id,
                    description="Tentative de création de course non autorisée"
                )
                raise ValueError("Utilisateur non trouvé ou non autorisé")
            
            # Estimer la course
            estimate = self.estimate_trip(trip_data)
            
            # Créer la course
            trip = Trip(
                id=f"trip_{uuid.uuid4().hex[:12]}",
                passenger_id=passenger_id,
                pickup_latitude=trip_data.pickup_latitude,
                pickup_longitude=trip_data.pickup_longitude,
                pickup_address=trip_data.pickup_address,
                destination_latitude=trip_data.destination_latitude,
                destination_longitude=trip_data.destination_longitude,
                destination_address=trip_data.destination_address,
                vehicle_type=trip_data.vehicle_type,
                estimated_price=estimate.price,
                distance_km=estimate.distance_km,
                duration_minutes=estimate.duration_minutes,
                notes=trip_data.notes,
                status=TripStatus.REQUESTED
            )
            
            self.db.add(trip)
            self.db.commit()
            self.db.refresh(trip)
            
            # Métriques de création réussie
            ctx.record_value("estimated_price", estimate.price)
            ctx.record_value("distance_km", estimate.distance_km)
            ctx.record_value("duration_minutes", estimate.duration_minutes)
            
            self.collector.record_metric(
                name="trip_requests_by_vehicle_type",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={
                    "vehicle_type": trip_data.vehicle_type.value,
                    "distance_range": self._get_distance_range(estimate.distance_km),
                    "price_range": self._get_price_range(estimate.price)
                },
                user_id=passenger_id,
                description="Demande de course par type de véhicule"
            )
            
            return trip
    
    @monitor_business_operation("driver_assignment", "trip")
    def assign_driver(self, trip_id: str, driver_id: str) -> Trip:
        """Assigne un conducteur à une course."""
        with MetricsContext("driver_assignment", MetricCategory.BUSINESS,
                           labels={"trip_id": trip_id},
                           description="Attribution d'un conducteur") as ctx:
            
            # Récupérer la course
            trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
            if not trip:
                raise ValueError("Course non trouvée")
            
            if trip.status != TripStatus.REQUESTED:
                self.collector.record_metric(
                    name="trip_assignment_invalid_status",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels={"current_status": trip.status.value},
                    user_id=driver_id,
                    description="Tentative d'attribution sur course avec statut invalide"
                )
                raise ValueError(f"Course dans un état invalide: {trip.status}")
            
            # Vérifier le conducteur
            driver = self.db.query(User).filter(
                and_(User.id == driver_id, User.role == UserRole.DRIVER)
            ).first()
            
            if not driver:
                raise ValueError("Conducteur non trouvé")
            
            # Calculer le temps d'attente
            wait_time = (datetime.utcnow() - trip.requested_at).total_seconds()
            
            # Assigner le conducteur
            trip.driver_id = driver_id
            trip.status = TripStatus.ACCEPTED
            trip.accepted_at = datetime.utcnow()
            
            self.db.commit()
            self.db.refresh(trip)
            
            # Métriques d'attribution
            ctx.record_value("wait_time_seconds", wait_time)
            
            self.collector.record_metric(
                name="trip_assignment_wait_time",
                value=wait_time,
                metric_type=MetricType.TIMER,
                category=MetricCategory.BUSINESS,
                labels={
                    "vehicle_type": trip.vehicle_type.value,
                    "wait_time_range": self._get_wait_time_range(wait_time)
                },
                user_id=trip.passenger_id,
                description="Temps d'attente pour attribution de conducteur"
            )
            
            return trip
    
    def _get_wait_time_range(self, wait_time_seconds: float) -> str:
        """Catégorise le temps d'attente."""
        if wait_time_seconds < 60:
            return "very_fast"
        elif wait_time_seconds < 300:  # 5 minutes
            return "fast"
        elif wait_time_seconds < 600:  # 10 minutes
            return "normal"
        elif wait_time_seconds < 1200:  # 20 minutes
            return "slow"
        else:
            return "very_slow"
    
    @monitor_business_operation("trip_start", "trip")
    def start_trip(self, trip_id: str, driver_id: str) -> Trip:
        """Démarre une course."""
        trip = self.db.query(Trip).filter(
            and_(Trip.id == trip_id, Trip.driver_id == driver_id)
        ).first()
        
        if not trip:
            raise ValueError("Course non trouvée ou conducteur non autorisé")
        
        if trip.status != TripStatus.ACCEPTED:
            raise ValueError(f"Course dans un état invalide: {trip.status}")
        
        trip.status = TripStatus.IN_PROGRESS
        trip.started_at = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(trip)
        
        # Métrique de démarrage
        self.collector.record_metric(
            name="trip_started_by_vehicle_type",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={"vehicle_type": trip.vehicle_type.value},
            user_id=trip.passenger_id,
            description="Course démarrée par type de véhicule"
        )
        
        return trip
    
    @monitor_business_operation("trip_completion", "trip", track_value=True, value_field="final_price")
    def complete_trip(self, trip_id: str, driver_id: str) -> Trip:
        """Termine une course."""
        with MetricsContext("trip_completion", MetricCategory.BUSINESS,
                           description="Finalisation d'une course") as ctx:
            
            trip = self.db.query(Trip).filter(
                and_(Trip.id == trip_id, Trip.driver_id == driver_id)
            ).first()
            
            if not trip:
                raise ValueError("Course non trouvée ou conducteur non autorisé")
            
            if trip.status != TripStatus.IN_PROGRESS:
                raise ValueError(f"Course dans un état invalide: {trip.status}")
            
            # Calculer la durée réelle
            actual_duration = (datetime.utcnow() - trip.started_at).total_seconds() / 60
            
            trip.status = TripStatus.COMPLETED
            trip.completed_at = datetime.utcnow()
            trip.final_price = trip.estimated_price  # Pour l'instant, prix final = prix estimé
            
            self.db.commit()
            self.db.refresh(trip)
            
            # Métriques de finalisation
            ctx.record_value("final_price", trip.final_price)
            ctx.record_value("actual_duration_minutes", actual_duration)
            
            self.collector.record_metric(
                name="trip_completion_revenue",
                value=trip.final_price,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={
                    "vehicle_type": trip.vehicle_type.value,
                    "price_range": self._get_price_range(trip.final_price)
                },
                user_id=trip.passenger_id,
                description="Revenus générés par course terminée"
            )
            
            self.collector.record_metric(
                name="trip_actual_duration",
                value=actual_duration,
                metric_type=MetricType.TIMER,
                category=MetricCategory.BUSINESS,
                labels={"vehicle_type": trip.vehicle_type.value},
                user_id=trip.passenger_id,
                description="Durée réelle de la course"
            )
            
            return trip
    
    @monitor_business_operation("trip_cancellation", "trip")
    def cancel_trip(self, trip_id: str, user_id: str, reason: str) -> Trip:
        """Annule une course."""
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        # Vérifier les autorisations
        if trip.passenger_id != user_id and trip.driver_id != user_id:
            raise ValueError("Non autorisé à annuler cette course")
        
        if trip.status in [TripStatus.COMPLETED, TripStatus.CANCELLED]:
            raise ValueError(f"Impossible d'annuler une course {trip.status.value}")
        
        # Déterminer qui annule
        canceller_role = "passenger" if trip.passenger_id == user_id else "driver"
        
        trip.status = TripStatus.CANCELLED
        trip.cancelled_at = datetime.utcnow()
        trip.cancellation_reason = reason
        
        self.db.commit()
        self.db.refresh(trip)
        
        # Métriques d'annulation
        self.collector.record_metric(
            name="trip_cancellations_by_role",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={
                "cancelled_by": canceller_role,
                "trip_status": trip.status.value,
                "vehicle_type": trip.vehicle_type.value,
                "reason_category": self._categorize_cancellation_reason(reason)
            },
            user_id=user_id,
            description="Annulation de course par rôle"
        )
        
        return trip
    
    def _categorize_cancellation_reason(self, reason: str) -> str:
        """Catégorise la raison d'annulation."""
        reason_lower = reason.lower()
        if any(word in reason_lower for word in ["retard", "temps", "attente"]):
            return "delay"
        elif any(word in reason_lower for word in ["prix", "coût", "cher"]):
            return "price"
        elif any(word in reason_lower for word in ["urgence", "emergency"]):
            return "emergency"
        elif any(word in reason_lower for word in ["erreur", "mistake"]):
            return "mistake"
        else:
            return "other"
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def find_available_drivers(self, trip: Trip, radius_km: float = 10) -> List[User]:
        """Trouve les conducteurs disponibles dans un rayon donné."""
        # Coordonnées de prise en charge
        pickup_lat = trip.pickup_latitude
        pickup_lon = trip.pickup_longitude
        
        # Requête pour trouver les conducteurs disponibles
        drivers = self.db.query(User).join(DriverLocation).filter(
            and_(
                User.role == UserRole.DRIVER,
                User.status == "active",
                DriverLocation.is_available == True,
                DriverLocation.is_online == True,
                # Filtre approximatif par coordonnées (optimisation)
                DriverLocation.latitude.between(pickup_lat - 0.1, pickup_lat + 0.1),
                DriverLocation.longitude.between(pickup_lon - 0.1, pickup_lon + 0.1)
            )
        ).all()
        
        # Filtrage précis par distance
        available_drivers = []
        for driver in drivers:
            if hasattr(driver, 'location') and driver.location:
                driver_location = (driver.location.latitude, driver.location.longitude)
                pickup_location = (pickup_lat, pickup_lon)
                distance = geodesic(driver_location, pickup_location).kilometers
                
                if distance <= radius_km:
                    available_drivers.append((driver, distance))
        
        # Trier par distance
        available_drivers.sort(key=lambda x: x[1])
        
        # Métriques de recherche de conducteurs
        self.collector.record_metric(
            name="driver_search_results",
            value=len(available_drivers),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "radius_km": str(radius_km),
                "vehicle_type": trip.vehicle_type.value,
                "availability_level": self._get_availability_level(len(available_drivers))
            },
            description="Nombre de conducteurs disponibles trouvés"
        )
        
        return [driver for driver, _ in available_drivers]
    
    def _get_availability_level(self, driver_count: int) -> str:
        """Catégorise le niveau de disponibilité des conducteurs."""
        if driver_count == 0:
            return "none"
        elif driver_count < 3:
            return "low"
        elif driver_count < 8:
            return "medium"
        else:
            return "high"

