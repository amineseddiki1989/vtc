"""
Service de gestion des courses avancé avec workflow complet.
Logique métier sophistiquée pour toutes les opérations de courses.
"""

import asyncio
import uuid
from datetime import datetime, timezone, timedelta
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status

from ..models.trip_advanced import Trip, TripStatus, TripType, PaymentStatus, CancellationReason
from ..models.trip_event import TripEvent, TripEventType
from ..models.user import User
from ..models.vehicle import Vehicle
from ..core.database.postgresql import get_async_session
from ..core.cache.redis_manager import redis_manager
from ..core.logging.production_logger import get_logger, log_performance
from .pricing_service import PricingService
from .location_service import LocationService
from .notification_service import NotificationService

logger = get_logger(__name__)

@dataclass
class TripSearchCriteria:
    """Critères de recherche de courses."""
    passenger_id: Optional[str] = None
    driver_id: Optional[str] = None
    status: Optional[List[TripStatus]] = None
    trip_type: Optional[TripType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    pickup_area: Optional[Tuple[float, float, float]] = None  # lat, lng, radius_km
    destination_area: Optional[Tuple[float, float, float]] = None
    min_fare: Optional[Decimal] = None
    max_fare: Optional[Decimal] = None
    page: int = 1
    page_size: int = 20

@dataclass
class TripEstimateRequest:
    """Demande d'estimation de course."""
    pickup_latitude: float
    pickup_longitude: float
    destination_latitude: float
    destination_longitude: float
    trip_type: TripType = TripType.STANDARD
    scheduled_time: Optional[datetime] = None
    passenger_count: int = 1

@dataclass
class TripCreateRequest:
    """Demande de création de course."""
    passenger_id: str
    pickup_latitude: float
    pickup_longitude: float
    pickup_address: str
    destination_latitude: float
    destination_longitude: float
    destination_address: str
    trip_type: TripType = TripType.STANDARD
    scheduled_time: Optional[datetime] = None
    special_requests: Optional[str] = None
    passenger_notes: Optional[str] = None
    pickup_landmark: Optional[str] = None
    destination_landmark: Optional[str] = None

class TripServiceAdvanced:
    """Service avancé de gestion des courses."""
    
    def __init__(self):
        self.pricing_service = PricingService()
        self.location_service = LocationService()
        self.notification_service = NotificationService()
        
    # === ESTIMATION DE COURSES ===
    
    @log_performance("trip_estimate")
    async def estimate_trip(
        self,
        request: TripEstimateRequest,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Estime le coût et la durée d'une course."""
        try:
            # Calculer la distance et la durée
            route_info = await self.location_service.calculate_route(
                (request.pickup_latitude, request.pickup_longitude),
                (request.destination_latitude, request.destination_longitude)
            )
            
            # Calculer le prix
            pricing_data = await self.pricing_service.calculate_fare(
                distance_km=route_info["distance_km"],
                duration_minutes=route_info["duration_minutes"],
                trip_type=request.trip_type,
                pickup_location=(request.pickup_latitude, request.pickup_longitude),
                scheduled_time=request.scheduled_time
            )
            
            # Vérifier la disponibilité des conducteurs
            available_drivers = await self._find_available_drivers(
                pickup_location=(request.pickup_latitude, request.pickup_longitude),
                trip_type=request.trip_type,
                db=db
            )
            
            # Calculer l'ETA du conducteur le plus proche
            driver_eta = None
            if available_drivers:
                closest_driver = available_drivers[0]
                driver_eta = await self.location_service.calculate_eta(
                    from_location=(closest_driver["latitude"], closest_driver["longitude"]),
                    to_location=(request.pickup_latitude, request.pickup_longitude)
                )
            
            estimate = {
                "distance_km": route_info["distance_km"],
                "duration_minutes": route_info["duration_minutes"],
                "estimated_fare": pricing_data["total_fare"],
                "fare_breakdown": pricing_data["breakdown"],
                "surge_multiplier": pricing_data["surge_multiplier"],
                "available_drivers": len(available_drivers),
                "driver_eta_minutes": driver_eta,
                "route_polyline": route_info.get("polyline"),
                "estimated_pickup_time": datetime.now(timezone.utc) + timedelta(minutes=driver_eta or 5)
            }
            
            # Cache l'estimation pour 5 minutes
            cache_key = f"trip_estimate:{hash(str(request))}"
            await redis_manager.set(cache_key, estimate, expire=300)
            
            logger.info(f"Estimation calculée: {route_info['distance_km']}km, {pricing_data['total_fare']}DZD")
            
            return estimate
            
        except Exception as e:
            logger.error(f"Erreur lors de l'estimation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors du calcul de l'estimation"
            )
    
    # === CRÉATION DE COURSES ===
    
    @log_performance("trip_create")
    async def create_trip(
        self,
        request: TripCreateRequest,
        db: AsyncSession
    ) -> Trip:
        """Crée une nouvelle course."""
        try:
            # Vérifier que le passager existe et est actif
            passenger = await self._get_user_by_id(request.passenger_id, db)
            if not passenger or not passenger.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Passager non trouvé ou inactif"
                )
            
            # Vérifier qu'il n'y a pas de course active pour ce passager
            active_trip = await self._get_active_trip_for_passenger(request.passenger_id, db)
            if active_trip:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Une course est déjà en cours pour ce passager"
                )
            
            # Calculer l'estimation
            estimate_request = TripEstimateRequest(
                pickup_latitude=request.pickup_latitude,
                pickup_longitude=request.pickup_longitude,
                destination_latitude=request.destination_latitude,
                destination_longitude=request.destination_longitude,
                trip_type=request.trip_type,
                scheduled_time=request.scheduled_time
            )
            
            estimate = await self.estimate_trip(estimate_request, db)
            
            # Créer la course
            trip = Trip(
                trip_number=self._generate_trip_number(),
                passenger_id=request.passenger_id,
                pickup_latitude=request.pickup_latitude,
                pickup_longitude=request.pickup_longitude,
                pickup_address=request.pickup_address,
                pickup_landmark=request.pickup_landmark,
                destination_latitude=request.destination_latitude,
                destination_longitude=request.destination_longitude,
                destination_address=request.destination_address,
                destination_landmark=request.destination_landmark,
                trip_type=request.trip_type,
                estimated_distance_km=estimate["distance_km"],
                estimated_duration_minutes=estimate["duration_minutes"],
                estimated_fare=Decimal(str(estimate["estimated_fare"])),
                surge_multiplier=estimate["surge_multiplier"],
                scheduled_at=request.scheduled_time,
                special_requests=request.special_requests,
                passenger_notes=request.passenger_notes,
                status=TripStatus.REQUESTED
            )
            
            db.add(trip)
            await db.flush()  # Pour obtenir l'ID
            
            # Créer l'événement de création
            event = TripEvent.create_event(
                trip_id=str(trip.id),
                event_type=TripEventType.TRIP_CREATED,
                event_source="app",
                actor_id=request.passenger_id,
                actor_type="passenger",
                event_data={
                    "trip_type": request.trip_type,
                    "estimated_fare": float(trip.estimated_fare),
                    "pickup_address": request.pickup_address,
                    "destination_address": request.destination_address
                },
                description=f"Course créée par le passager"
            )
            
            db.add(event)
            await db.commit()
            
            # Démarrer la recherche de conducteur si course immédiate
            if not request.scheduled_time:
                asyncio.create_task(self._start_driver_search(str(trip.id)))
            
            logger.info(f"Course créée: {trip.trip_number} pour passager {request.passenger_id}")
            
            return trip
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la création de course: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la création de la course"
            )
    
    # === RECHERCHE DE CONDUCTEUR ===
    
    async def _start_driver_search(self, trip_id: str):
        """Démarre la recherche de conducteur pour une course."""
        try:
            async with get_async_session() as db:
                trip = await self._get_trip_by_id(trip_id, db)
                if not trip or trip.status != TripStatus.REQUESTED:
                    return
                
                # Changer le statut
                trip.status = TripStatus.SEARCHING
                
                # Créer l'événement
                event = TripEvent.create_event(
                    trip_id=trip_id,
                    event_type=TripEventType.DRIVER_SEARCH_STARTED,
                    event_source="system",
                    description="Recherche de conducteur démarrée"
                )
                
                db.add(event)
                await db.commit()
                
                # Rechercher des conducteurs
                drivers = await self._find_available_drivers(
                    pickup_location=(trip.pickup_latitude, trip.pickup_longitude),
                    trip_type=trip.trip_type,
                    db=db
                )
                
                if not drivers:
                    # Aucun conducteur disponible
                    await self._handle_no_driver_available(trip_id, db)
                    return
                
                # Envoyer des notifications aux conducteurs
                for driver in drivers[:5]:  # Limiter à 5 conducteurs
                    await self.notification_service.send_trip_request(
                        driver_id=driver["id"],
                        trip_id=trip_id,
                        pickup_location=(trip.pickup_latitude, trip.pickup_longitude),
                        destination_location=(trip.destination_latitude, trip.destination_longitude),
                        estimated_fare=float(trip.estimated_fare)
                    )
                
                # Programmer un timeout si aucune réponse
                asyncio.create_task(self._handle_search_timeout(trip_id, 120))  # 2 minutes
                
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de conducteur pour {trip_id}: {e}")
    
    async def _handle_search_timeout(self, trip_id: str, timeout_seconds: int):
        """Gère le timeout de recherche de conducteur."""
        await asyncio.sleep(timeout_seconds)
        
        try:
            async with get_async_session() as db:
                trip = await self._get_trip_by_id(trip_id, db)
                if trip and trip.status == TripStatus.SEARCHING:
                    # Annuler la course par le système
                    await self.cancel_trip(
                        trip_id=trip_id,
                        cancelled_by_id="system",
                        reason=CancellationReason.OTHER,
                        details="Aucun conducteur disponible",
                        db=db
                    )
                    
                    # Notifier le passager
                    await self.notification_service.send_trip_cancelled(
                        user_id=str(trip.passenger_id),
                        trip_id=trip_id,
                        reason="Aucun conducteur disponible dans votre zone"
                    )
                    
        except Exception as e:
            logger.error(f"Erreur lors du timeout de recherche pour {trip_id}: {e}")
    
    # === ASSIGNATION DE CONDUCTEUR ===
    
    @log_performance("assign_driver")
    async def assign_driver(
        self,
        trip_id: str,
        driver_id: str,
        db: AsyncSession
    ) -> Trip:
        """Assigne un conducteur à une course."""
        try:
            # Vérifier la course
            trip = await self._get_trip_by_id(trip_id, db)
            if not trip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course non trouvée"
                )
            
            if trip.status != TripStatus.SEARCHING:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La course n'est pas en recherche de conducteur"
                )
            
            # Vérifier le conducteur
            driver = await self._get_user_by_id(driver_id, db)
            if not driver or driver.role != "driver" or not driver.is_active:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conducteur non trouvé ou inactif"
                )
            
            # Vérifier que le conducteur n'a pas de course active
            active_trip = await self._get_active_trip_for_driver(driver_id, db)
            if active_trip:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="Le conducteur a déjà une course active"
                )
            
            # Assigner le conducteur
            trip.driver_id = driver_id
            trip.status = TripStatus.DRIVER_ASSIGNED
            trip.driver_assigned_at = datetime.now(timezone.utc)
            
            # Créer l'événement
            event = TripEvent.create_event(
                trip_id=trip_id,
                event_type=TripEventType.DRIVER_ASSIGNED,
                event_source="system",
                actor_id=driver_id,
                actor_type="driver",
                event_data={
                    "driver_id": driver_id,
                    "driver_name": f"{driver.first_name} {driver.last_name}",
                    "vehicle_info": "À récupérer du véhicule"
                },
                description=f"Conducteur {driver.first_name} assigné"
            )
            
            db.add(event)
            await db.commit()
            
            # Notifier le passager
            await self.notification_service.send_driver_assigned(
                passenger_id=str(trip.passenger_id),
                trip_id=trip_id,
                driver_info={
                    "id": driver_id,
                    "name": f"{driver.first_name} {driver.last_name}",
                    "phone": driver.phone,
                    "rating": 4.8  # À récupérer des vraies données
                }
            )
            
            # Notifier le conducteur
            await self.notification_service.send_trip_accepted(
                driver_id=driver_id,
                trip_id=trip_id,
                pickup_address=trip.pickup_address
            )
            
            logger.info(f"Conducteur {driver_id} assigné à la course {trip_id}")
            
            return trip
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de l'assignation du conducteur: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'assignation du conducteur"
            )
    
    # === GESTION DES STATUTS ===
    
    @log_performance("update_trip_status")
    async def update_trip_status(
        self,
        trip_id: str,
        new_status: TripStatus,
        actor_id: str,
        location: Optional[Tuple[float, float]] = None,
        notes: Optional[str] = None,
        db: AsyncSession = None
    ) -> Trip:
        """Met à jour le statut d'une course."""
        if db is None:
            async with get_async_session() as db:
                return await self.update_trip_status(trip_id, new_status, actor_id, location, notes, db)
        
        try:
            trip = await self._get_trip_by_id(trip_id, db)
            if not trip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course non trouvée"
                )
            
            old_status = trip.status
            
            # Valider la transition
            if not self._is_valid_status_transition(old_status, new_status):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Transition invalide de {old_status} vers {new_status}"
                )
            
            # Mettre à jour le statut et les timestamps
            trip.status = new_status
            self._update_status_timestamps(trip, new_status)
            
            # Créer l'événement
            event = TripEvent.create_event(
                trip_id=trip_id,
                event_type=TripEventType.STATUS_CHANGED,
                event_source="app",
                actor_id=actor_id,
                event_data={
                    "old_status": old_status,
                    "new_status": new_status,
                    "notes": notes
                },
                description=f"Statut changé de {old_status} vers {new_status}",
                location=location
            )
            
            db.add(event)
            await db.commit()
            
            # Notifications selon le statut
            await self._handle_status_change_notifications(trip, old_status, new_status)
            
            logger.info(f"Statut de la course {trip_id} changé: {old_status} -> {new_status}")
            
            return trip
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la mise à jour du statut: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la mise à jour du statut"
            )
    
    # === ANNULATION ===
    
    @log_performance("cancel_trip")
    async def cancel_trip(
        self,
        trip_id: str,
        cancelled_by_id: str,
        reason: CancellationReason,
        details: Optional[str] = None,
        db: AsyncSession = None
    ) -> Trip:
        """Annule une course."""
        if db is None:
            async with get_async_session() as db:
                return await self.cancel_trip(trip_id, cancelled_by_id, reason, details, db)
        
        try:
            trip = await self._get_trip_by_id(trip_id, db)
            if not trip:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Course non trouvée"
                )
            
            if not trip.is_active:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="La course ne peut pas être annulée"
                )
            
            # Déterminer le type d'annulation
            if cancelled_by_id == str(trip.passenger_id):
                new_status = TripStatus.CANCELLED_BY_PASSENGER
            elif cancelled_by_id == str(trip.driver_id):
                new_status = TripStatus.CANCELLED_BY_DRIVER
            else:
                new_status = TripStatus.CANCELLED_BY_SYSTEM
            
            # Calculer les frais d'annulation
            cancellation_fee = trip.calculate_cancellation_fee()
            
            # Mettre à jour la course
            trip.status = new_status
            trip.cancelled_at = datetime.now(timezone.utc)
            trip.cancelled_by_id = cancelled_by_id
            trip.cancellation_reason = reason
            trip.cancellation_details = details
            trip.cancellation_fee = cancellation_fee
            
            # Créer l'événement
            event = TripEvent.create_event(
                trip_id=trip_id,
                event_type=TripEventType.TRIP_CANCELLED,
                event_source="app",
                actor_id=cancelled_by_id,
                event_data={
                    "reason": reason,
                    "details": details,
                    "cancellation_fee": float(cancellation_fee)
                },
                description=f"Course annulée: {reason}"
            )
            
            db.add(event)
            await db.commit()
            
            # Notifications
            await self._handle_cancellation_notifications(trip, reason, details)
            
            logger.info(f"Course {trip_id} annulée par {cancelled_by_id}: {reason}")
            
            return trip
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de l'annulation: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'annulation"
            )
    
    # === RECHERCHE ET FILTRAGE ===
    
    @log_performance("search_trips")
    async def search_trips(
        self,
        criteria: TripSearchCriteria,
        db: AsyncSession
    ) -> Dict[str, Any]:
        """Recherche des courses selon des critères."""
        try:
            query = db.query(Trip)
            
            # Filtres
            if criteria.passenger_id:
                query = query.filter(Trip.passenger_id == criteria.passenger_id)
            
            if criteria.driver_id:
                query = query.filter(Trip.driver_id == criteria.driver_id)
            
            if criteria.status:
                query = query.filter(Trip.status.in_(criteria.status))
            
            if criteria.trip_type:
                query = query.filter(Trip.trip_type == criteria.trip_type)
            
            if criteria.date_from:
                query = query.filter(Trip.created_at >= criteria.date_from)
            
            if criteria.date_to:
                query = query.filter(Trip.created_at <= criteria.date_to)
            
            if criteria.min_fare:
                query = query.filter(Trip.final_fare >= criteria.min_fare)
            
            if criteria.max_fare:
                query = query.filter(Trip.final_fare <= criteria.max_fare)
            
            # Filtres géographiques
            if criteria.pickup_area:
                lat, lng, radius = criteria.pickup_area
                # Utiliser une approximation simple pour le rayon
                lat_delta = radius / 111.0  # 1 degré ≈ 111 km
                lng_delta = radius / (111.0 * abs(lat))
                
                query = query.filter(
                    and_(
                        Trip.pickup_latitude.between(lat - lat_delta, lat + lat_delta),
                        Trip.pickup_longitude.between(lng - lng_delta, lng + lng_delta)
                    )
                )
            
            # Compter le total
            total = await query.count()
            
            # Pagination
            offset = (criteria.page - 1) * criteria.page_size
            trips = await query.offset(offset).limit(criteria.page_size).all()
            
            return {
                "trips": [trip.to_dict() for trip in trips],
                "total": total,
                "page": criteria.page,
                "page_size": criteria.page_size,
                "total_pages": (total + criteria.page_size - 1) // criteria.page_size
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la recherche"
            )
    
    # === MÉTHODES UTILITAIRES ===
    
    async def _find_available_drivers(
        self,
        pickup_location: Tuple[float, float],
        trip_type: TripType,
        db: AsyncSession,
        radius_km: float = 10.0
    ) -> List[Dict[str, Any]]:
        """Trouve les conducteurs disponibles dans un rayon."""
        # Cette méthode nécessiterait une intégration avec un service de géolocalisation
        # Pour l'instant, on simule avec des données fictives
        
        # Requête pour trouver les conducteurs actifs
        lat, lng = pickup_location
        lat_delta = radius_km / 111.0
        lng_delta = radius_km / (111.0 * abs(lat))
        
        # Simuler des conducteurs disponibles
        available_drivers = [
            {
                "id": str(uuid.uuid4()),
                "name": "Ahmed Benali",
                "latitude": lat + 0.01,
                "longitude": lng + 0.01,
                "distance_km": 1.2,
                "eta_minutes": 5,
                "rating": 4.8,
                "vehicle_type": "standard"
            },
            {
                "id": str(uuid.uuid4()),
                "name": "Fatima Khelil",
                "latitude": lat - 0.02,
                "longitude": lng + 0.015,
                "distance_km": 2.1,
                "eta_minutes": 8,
                "rating": 4.9,
                "vehicle_type": "premium"
            }
        ]
        
        return sorted(available_drivers, key=lambda x: x["distance_km"])
    
    async def _get_trip_by_id(self, trip_id: str, db: AsyncSession) -> Optional[Trip]:
        """Récupère une course par son ID."""
        result = await db.execute(
            db.query(Trip)
            .options(selectinload(Trip.passenger), selectinload(Trip.driver))
            .filter(Trip.id == trip_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_id(self, user_id: str, db: AsyncSession) -> Optional[User]:
        """Récupère un utilisateur par son ID."""
        result = await db.execute(
            db.query(User).filter(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_active_trip_for_passenger(self, passenger_id: str, db: AsyncSession) -> Optional[Trip]:
        """Récupère la course active d'un passager."""
        active_statuses = [
            TripStatus.REQUESTED,
            TripStatus.SEARCHING,
            TripStatus.DRIVER_ASSIGNED,
            TripStatus.DRIVER_ARRIVING,
            TripStatus.DRIVER_ARRIVED,
            TripStatus.PASSENGER_PICKUP,
            TripStatus.IN_PROGRESS
        ]
        
        result = await db.execute(
            db.query(Trip)
            .filter(
                and_(
                    Trip.passenger_id == passenger_id,
                    Trip.status.in_(active_statuses)
                )
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_active_trip_for_driver(self, driver_id: str, db: AsyncSession) -> Optional[Trip]:
        """Récupère la course active d'un conducteur."""
        active_statuses = [
            TripStatus.DRIVER_ASSIGNED,
            TripStatus.DRIVER_ARRIVING,
            TripStatus.DRIVER_ARRIVED,
            TripStatus.PASSENGER_PICKUP,
            TripStatus.IN_PROGRESS
        ]
        
        result = await db.execute(
            db.query(Trip)
            .filter(
                and_(
                    Trip.driver_id == driver_id,
                    Trip.status.in_(active_statuses)
                )
            )
        )
        return result.scalar_one_or_none()
    
    def _generate_trip_number(self) -> str:
        """Génère un numéro de course unique."""
        timestamp = datetime.now().strftime("%Y%m%d")
        random_part = str(uuid.uuid4())[:8].upper()
        return f"TR{timestamp}{random_part}"
    
    def _is_valid_status_transition(self, from_status: TripStatus, to_status: TripStatus) -> bool:
        """Vérifie si une transition de statut est valide."""
        valid_transitions = {
            TripStatus.REQUESTED: [TripStatus.SEARCHING, TripStatus.CANCELLED_BY_PASSENGER],
            TripStatus.SEARCHING: [TripStatus.DRIVER_ASSIGNED, TripStatus.CANCELLED_BY_SYSTEM],
            TripStatus.DRIVER_ASSIGNED: [TripStatus.DRIVER_ARRIVING, TripStatus.CANCELLED_BY_DRIVER, TripStatus.CANCELLED_BY_PASSENGER],
            TripStatus.DRIVER_ARRIVING: [TripStatus.DRIVER_ARRIVED, TripStatus.CANCELLED_BY_DRIVER, TripStatus.CANCELLED_BY_PASSENGER],
            TripStatus.DRIVER_ARRIVED: [TripStatus.PASSENGER_PICKUP, TripStatus.CANCELLED_BY_DRIVER, TripStatus.CANCELLED_BY_PASSENGER],
            TripStatus.PASSENGER_PICKUP: [TripStatus.IN_PROGRESS, TripStatus.CANCELLED_BY_DRIVER],
            TripStatus.IN_PROGRESS: [TripStatus.COMPLETED, TripStatus.FAILED],
        }
        
        return to_status in valid_transitions.get(from_status, [])
    
    def _update_status_timestamps(self, trip: Trip, status: TripStatus):
        """Met à jour les timestamps selon le statut."""
        now = datetime.now(timezone.utc)
        
        if status == TripStatus.DRIVER_ASSIGNED:
            trip.driver_assigned_at = now
        elif status == TripStatus.DRIVER_ARRIVED:
            trip.driver_arrived_at = now
        elif status == TripStatus.PASSENGER_PICKUP:
            trip.pickup_at = now
        elif status == TripStatus.IN_PROGRESS:
            trip.started_at = now
        elif status == TripStatus.COMPLETED:
            trip.completed_at = now
        elif status in [TripStatus.CANCELLED_BY_PASSENGER, TripStatus.CANCELLED_BY_DRIVER, TripStatus.CANCELLED_BY_SYSTEM]:
            trip.cancelled_at = now
    
    async def _handle_status_change_notifications(self, trip: Trip, old_status: TripStatus, new_status: TripStatus):
        """Gère les notifications lors des changements de statut."""
        # Implémentation des notifications selon le statut
        pass
    
    async def _handle_cancellation_notifications(self, trip: Trip, reason: CancellationReason, details: Optional[str]):
        """Gère les notifications d'annulation."""
        # Implémentation des notifications d'annulation
        pass
    
    async def _handle_no_driver_available(self, trip_id: str, db: AsyncSession):
        """Gère le cas où aucun conducteur n'est disponible."""
        # Annuler la course et notifier le passager
        await self.cancel_trip(
            trip_id=trip_id,
            cancelled_by_id="system",
            reason=CancellationReason.OTHER,
            details="Aucun conducteur disponible",
            db=db
        )

