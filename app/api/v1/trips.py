"""
API professionnelle de gestion des courses avec sécurité renforcée.
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from typing import List, Optional

from ...core.database.base import get_db
from ...core.auth.dependencies import get_current_user
from ...core.security.business_logic_validator import (
    SecureBusinessValidator, SecureTripValidator, SecureTripUpdateValidator
)
from ...models.user import User
from ...models.trip import TripStatus
from ...schemas.trip import (
    TripCreate, TripUpdate, TripResponse, TripEstimate, 
    TripListResponse, TripStats
)
from ...services.trip_service import TripService

router = APIRouter(prefix="/trips", tags=["Courses"], redirect_slashes=False)


@router.post("/estimate", response_model=TripEstimate, summary="Estimer une course")
async def estimate_trip(
    trip_data: SecureTripValidator,
    db: Session = Depends(get_db)
):
    """
    Estime le coût et la durée d'une course de manière sécurisée.
    
    - **pickup_latitude/longitude**: Coordonnées de prise en charge (validées)
    - **destination_latitude/longitude**: Coordonnées de destination (validées)
    - **vehicle_type**: Type de véhicule souhaité
    """
    try:
        # Validation sécurisée des coordonnées
        validated_coords = SecureBusinessValidator._validate_coordinates(trip_data.dict())
        
        # Calcul sécurisé de la distance
        distance = SecureBusinessValidator._calculate_secure_distance(
            validated_coords["pickup_latitude"],
            validated_coords["pickup_longitude"],
            validated_coords["destination_latitude"],
            validated_coords["destination_longitude"]
        )
        
        # Calcul sécurisé du prix
        estimated_price = SecureBusinessValidator._calculate_secure_price(distance)
        
        return TripEstimate(
            distance=distance,
            estimated_price=float(estimated_price),
            estimated_duration=int(distance * 60 / 30)  # Estimation: 30 km/h moyenne
        )
        
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Erreur lors de l'estimation de la course"
        )


@router.post("/request", response_model=TripResponse, summary="Demander une course")
async def request_trip(
    trip_data: SecureTripValidator,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Demande une nouvelle course avec validation sécurisée et recherche automatique de conducteur.
    
    Endpoint spécialisé pour les demandes de course avec matching automatique.
    """
    try:
        # Validation que l'utilisateur est un passager
        if current_user.role != "passenger":
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls les passagers peuvent demander des courses"
            )
        
        # Validation sécurisée de la demande de course
        validated_data = SecureBusinessValidator.validate_trip_creation(
            trip_data.dict(), 
            str(current_user.id), 
            current_user.role
        )
        
        trip_service = TripService(db)
        
        # Créer la course avec statut "requested"
        trip = trip_service.create_trip_secure(validated_data)
        
        # Rechercher automatiquement des conducteurs disponibles
        available_drivers = trip_service.find_available_drivers(trip, radius_km=15.0)
        
        if available_drivers:
            # Notifier les conducteurs disponibles (simulation)
            import logging
            logger = logging.getLogger(__name__)
            logger.info(f"Course {trip.id} créée - {len(available_drivers)} conducteurs notifiés")
            
            # Mettre à jour le statut pour indiquer que des conducteurs ont été notifiés
            trip.status = TripStatus.PENDING
            db.commit()
            db.refresh(trip)
        
        return TripResponse(
            id=trip.id,
            passenger_id=trip.passenger_id,
            driver_id=trip.driver_id,
            pickup_address=trip.pickup_address,
            destination_address=trip.destination_address,
            pickup_latitude=trip.pickup_latitude,
            pickup_longitude=trip.pickup_longitude,
            destination_latitude=trip.destination_latitude,
            destination_longitude=trip.destination_longitude,
            status=trip.status,
            estimated_price=trip.estimated_price,
            final_price=trip.final_price,
            distance=trip.distance,
            estimated_duration=trip.estimated_duration,
            actual_duration=trip.actual_duration,
            vehicle_type=trip.vehicle_type,
            created_at=trip.created_at,
            updated_at=trip.updated_at,
            started_at=trip.started_at,
            completed_at=trip.completed_at,
            cancelled_at=trip.cancelled_at,
            cancellation_reason=trip.cancellation_reason
        )
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Erreur lors de la demande de course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la demande de course"
        )


@router.post("/", response_model=TripResponse, summary="Créer une course")
async def create_trip(
    trip_data: SecureTripValidator,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Crée une nouvelle demande de course avec validation sécurisée.
    
    Seuls les passagers peuvent créer des courses.
    """
    try:
        # Validation sécurisée de la création de course
        validated_data = SecureBusinessValidator.validate_trip_creation(
            trip_data.dict(), 
            str(current_user.id), 
            current_user.role
        )
        
        trip_service = TripService(db)
        trip = trip_service.create_trip_secure(validated_data)
        return trip
        
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de la course"
        )


@router.get("/", response_model=TripListResponse, summary="Lister mes courses")
async def get_my_trips(
    status: Optional[TripStatus] = Query(None, description="Filtrer par statut"),
    page: int = Query(1, ge=1, description="Numéro de page"),
    per_page: int = Query(20, ge=1, le=100, description="Éléments par page"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère la liste des courses de l'utilisateur connecté.
    
    - **status**: Filtrer par statut (optionnel)
    - **page**: Numéro de page pour la pagination
    - **per_page**: Nombre d'éléments par page (max 100)
    """
    try:
        trip_service = TripService(db)
        offset = (page - 1) * per_page
        
        trips, total = trip_service.get_user_trips(
            user_id=current_user.id,
            status=status,
            limit=per_page,
            offset=offset
        )
        
        return TripListResponse(
            trips=trips,
            total=total,
            page=page,
            per_page=per_page,
            has_next=(offset + per_page) < total,
            has_prev=page > 1
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.get("/{trip_id}", response_model=TripResponse, summary="Détails d'une course")
async def get_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Récupère les détails d'une course spécifique.
    
    L'utilisateur ne peut voir que ses propres courses.
    """
    try:
        trip_service = TripService(db)
        trip = trip_service.get_trip_by_id(trip_id, current_user.id)
        
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course non trouvée"
            )
        
        return trip
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération: {str(e)}"
        )


@router.patch("/{trip_id}", response_model=TripResponse, summary="Modifier une course")
async def update_trip(
    trip_id: str,
    trip_update: TripUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Met à jour une course existante.
    
    Seuls certains champs peuvent être modifiés selon le statut.
    """
    try:
        trip_service = TripService(db)
        trip = trip_service.update_trip(trip_id, trip_update, current_user.id)
        return trip
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la modification: {str(e)}"
        )


@router.post("/{trip_id}/accept", response_model=TripResponse, summary="Accepter une course (Conducteur)")
async def accept_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Permet à un conducteur d'accepter une course.
    
    Seuls les conducteurs peuvent accepter des courses.
    """
    if current_user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les conducteurs peuvent accepter des courses"
        )
    
    try:
        trip_service = TripService(db)
        trip = trip_service.assign_driver(trip_id, current_user.id)
        return trip
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'acceptation: {str(e)}"
        )


@router.post("/{trip_id}/start", response_model=TripResponse, summary="Démarrer une course")
async def start_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Démarre une course acceptée.
    
    Seul le conducteur assigné peut démarrer la course.
    """
    if current_user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les conducteurs peuvent démarrer des courses"
        )
    
    try:
        trip_service = TripService(db)
        trip = trip_service.start_trip(trip_id, current_user.id)
        return trip
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du démarrage: {str(e)}"
        )


@router.post("/{trip_id}/complete", response_model=TripResponse, summary="Terminer une course")
async def complete_trip(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Termine une course en cours.
    
    Seul le conducteur assigné peut terminer la course.
    """
    if current_user.role != "driver":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les conducteurs peuvent terminer des courses"
        )
    
    try:
        trip_service = TripService(db)
        trip = trip_service.complete_trip(trip_id, current_user.id)
        return trip
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la finalisation: {str(e)}"
        )


@router.post("/{trip_id}/cancel", response_model=TripResponse, summary="Annuler une course")
async def cancel_trip(
    trip_id: str,
    reason: str = Query(..., description="Raison de l'annulation"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Annule une course.
    
    Le passager ou le conducteur peuvent annuler selon le statut.
    """
    try:
        trip_service = TripService(db)
        trip = trip_service.cancel_trip(trip_id, current_user.id, reason)
        return trip
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'annulation: {str(e)}"
        )


@router.get("/available/drivers", summary="Conducteurs disponibles")
async def get_available_drivers(
    latitude: float = Query(..., description="Latitude de recherche"),
    longitude: float = Query(..., description="Longitude de recherche"),
    radius_km: float = Query(10, description="Rayon de recherche en km"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Trouve les conducteurs disponibles dans un rayon donné.
    
    Utilisé pour estimer le temps d'attente.
    """
    if current_user.role != "passenger":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Seuls les passagers peuvent rechercher des conducteurs"
        )
    
    try:
        trip_service = TripService(db)
        
        # Créer un objet trip temporaire pour la recherche
        from ...models.trip import Trip
        temp_trip = Trip(
            pickup_latitude=latitude,
            pickup_longitude=longitude
        )
        
        drivers = trip_service.find_available_drivers(temp_trip, radius_km)
        
        return {
            "available_drivers": len(drivers),
            "estimated_wait_time": min(len(drivers) * 2, 15),  # Estimation simple
            "radius_km": radius_km
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

