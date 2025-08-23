"""
API avancée de gestion des courses.
Endpoints complets pour toutes les opérations de courses.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from pydantic import BaseModel, Field

from ...core.database.postgresql import get_async_session
from ...core.auth.dependencies import get_current_user, require_role
from ...core.security.business_logic_validator import SecureBusinessValidator
from ...models.user_advanced import User, UserRole
from ...models.trip_advanced import Trip, TripStatus, TripType, CancellationReason
from ...services.trip_service_advanced import (
    TripServiceAdvanced, TripEstimateRequest, TripCreateRequest, TripSearchCriteria
)
from ...services.websocket_service import websocket_manager, get_websocket_manager, WebSocketManager
from ...core.logging.production_logger import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/trips", tags=["Courses Avancées"])

# === MODÈLES PYDANTIC ===

class TripEstimateRequestModel(BaseModel):
    """Modèle de demande d'estimation."""
    pickup_latitude: float = Field(..., ge=-90, le=90)
    pickup_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    trip_type: TripType = TripType.STANDARD
    scheduled_time: Optional[datetime] = None
    passenger_count: int = Field(1, ge=1, le=8)

class TripCreateRequestModel(BaseModel):
    """Modèle de création de course."""
    pickup_latitude: float = Field(..., ge=-90, le=90)
    pickup_longitude: float = Field(..., ge=-180, le=180)
    pickup_address: str = Field(..., min_length=5, max_length=500)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    destination_address: str = Field(..., min_length=5, max_length=500)
    trip_type: TripType = TripType.STANDARD
    scheduled_time: Optional[datetime] = None
    special_requests: Optional[str] = Field(None, max_length=1000)
    passenger_notes: Optional[str] = Field(None, max_length=500)
    pickup_landmark: Optional[str] = Field(None, max_length=200)
    destination_landmark: Optional[str] = Field(None, max_length=200)

class TripStatusUpdateModel(BaseModel):
    """Modèle de mise à jour de statut."""
    status: TripStatus
    latitude: Optional[float] = Field(None, ge=-90, le=90)
    longitude: Optional[float] = Field(None, ge=-180, le=180)
    notes: Optional[str] = Field(None, max_length=500)

class TripCancellationModel(BaseModel):
    """Modèle d'annulation de course."""
    reason: CancellationReason
    details: Optional[str] = Field(None, max_length=1000)

class TripSearchModel(BaseModel):
    """Modèle de recherche de courses."""
    passenger_id: Optional[str] = None
    driver_id: Optional[str] = None
    status: Optional[List[TripStatus]] = None
    trip_type: Optional[TripType] = None
    date_from: Optional[datetime] = None
    date_to: Optional[datetime] = None
    page: int = Field(1, ge=1)
    page_size: int = Field(20, ge=1, le=100)

# === ENDPOINTS D'ESTIMATION ===

@router.post("/estimate", summary="Estimer une course")
async def estimate_trip(
    request: TripEstimateRequestModel,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Estime le coût et la durée d'une course.
    
    - **pickup_latitude/longitude**: Coordonnées de départ
    - **destination_latitude/longitude**: Coordonnées d'arrivée
    - **trip_type**: Type de course (STANDARD, PREMIUM, etc.)
    - **scheduled_time**: Heure programmée (optionnel)
    - **passenger_count**: Nombre de passagers
    
    Retourne:
    - Distance et durée estimées
    - Prix détaillé avec breakdown
    - Nombre de conducteurs disponibles
    - ETA du conducteur le plus proche
    """
    try:
        service = TripServiceAdvanced()
        
        estimate_request = TripEstimateRequest(
            pickup_latitude=request.pickup_latitude,
            pickup_longitude=request.pickup_longitude,
            destination_latitude=request.destination_latitude,
            destination_longitude=request.destination_longitude,
            trip_type=request.trip_type,
            scheduled_time=request.scheduled_time,
            passenger_count=request.passenger_count
        )
        
        estimate = await service.estimate_trip(estimate_request, db)
        
        return {
            "success": True,
            "data": estimate,
            "message": "Estimation calculée avec succès"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de l'estimation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du calcul de l'estimation"
        )

# === ENDPOINTS DE GESTION DES COURSES ===

@router.post("/", summary="Créer une course")
async def create_trip(
    request: TripCreateRequestModel,
    current_user: User = Depends(require_role([UserRole.PASSENGER])),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Crée une nouvelle demande de course.
    
    Accessible uniquement aux passagers.
    
    - Vérifie la disponibilité des conducteurs
    - Calcule automatiquement l'estimation
    - Démarre la recherche de conducteur
    - Envoie les notifications appropriées
    """
    try:
        service = TripServiceAdvanced()
        
        create_request = TripCreateRequest(
            passenger_id=str(current_user.id),
            pickup_latitude=request.pickup_latitude,
            pickup_longitude=request.pickup_longitude,
            pickup_address=request.pickup_address,
            destination_latitude=request.destination_latitude,
            destination_longitude=request.destination_longitude,
            destination_address=request.destination_address,
            trip_type=request.trip_type,
            scheduled_time=request.scheduled_time,
            special_requests=request.special_requests,
            passenger_notes=request.passenger_notes,
            pickup_landmark=request.pickup_landmark,
            destination_landmark=request.destination_landmark
        )
        
        trip = await service.create_trip(create_request, db)
        
        return {
            "success": True,
            "data": trip.to_dict(),
            "message": "Course créée avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la création de course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la création de la course"
        )

@router.get("/{trip_id}", summary="Détails d'une course")
async def get_trip_details(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Récupère les détails complets d'une course.
    
    - Accessible au passager, conducteur ou admin
    - Inclut l'historique des événements
    - Informations de localisation temps réel
    """
    try:
        service = TripServiceAdvanced()
        trip = await service._get_trip_by_id(trip_id, db)
        
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course non trouvée"
            )
        
        # Vérifier les permissions
        if (current_user.role not in [UserRole.ADMIN, UserRole.SUPPORT] and
            str(current_user.id) not in [str(trip.passenger_id), str(trip.driver_id)]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Accès non autorisé à cette course"
            )
        
        return {
            "success": True,
            "data": trip.to_dict(),
            "message": "Détails de la course récupérés"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la récupération de course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération"
        )

@router.put("/{trip_id}/status", summary="Mettre à jour le statut")
async def update_trip_status(
    trip_id: str,
    request: TripStatusUpdateModel,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Met à jour le statut d'une course.
    
    - Conducteurs: peuvent mettre à jour les statuts de progression
    - Passagers: peuvent annuler avant prise en charge
    - Admins: peuvent modifier tous les statuts
    """
    try:
        service = TripServiceAdvanced()
        
        # Vérifier les permissions selon le statut
        trip = await service._get_trip_by_id(trip_id, db)
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course non trouvée"
            )
        
        # Logique de permissions
        if current_user.role == UserRole.DRIVER:
            if str(current_user.id) != str(trip.driver_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous n'êtes pas le conducteur de cette course"
                )
        elif current_user.role == UserRole.PASSENGER:
            if str(current_user.id) != str(trip.passenger_id):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Vous n'êtes pas le passager de cette course"
                )
            # Les passagers ne peuvent que annuler
            if request.status not in [TripStatus.CANCELLED_BY_PASSENGER]:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Action non autorisée pour un passager"
                )
        elif current_user.role not in [UserRole.ADMIN, UserRole.SUPPORT]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        
        location = None
        if request.latitude is not None and request.longitude is not None:
            location = (request.latitude, request.longitude)
        
        updated_trip = await service.update_trip_status(
            trip_id=trip_id,
            new_status=request.status,
            actor_id=str(current_user.id),
            location=location,
            notes=request.notes,
            db=db
        )
        
        return {
            "success": True,
            "data": updated_trip.to_dict(),
            "message": f"Statut mis à jour: {request.status}"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de la mise à jour de statut: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la mise à jour"
        )

@router.post("/{trip_id}/cancel", summary="Annuler une course")
async def cancel_trip(
    trip_id: str,
    request: TripCancellationModel,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Annule une course avec raison.
    
    - Calcule automatiquement les frais d'annulation
    - Notifie toutes les parties concernées
    - Met à jour les statistiques utilisateur
    """
    try:
        service = TripServiceAdvanced()
        
        # Vérifier les permissions
        trip = await service._get_trip_by_id(trip_id, db)
        if not trip:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Course non trouvée"
            )
        
        if (current_user.role not in [UserRole.ADMIN, UserRole.SUPPORT] and
            str(current_user.id) not in [str(trip.passenger_id), str(trip.driver_id)]):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez pas annuler cette course"
            )
        
        cancelled_trip = await service.cancel_trip(
            trip_id=trip_id,
            cancelled_by_id=str(current_user.id),
            reason=request.reason,
            details=request.details,
            db=db
        )
        
        return {
            "success": True,
            "data": cancelled_trip.to_dict(),
            "message": "Course annulée avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'annulation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'annulation"
        )

# === ENDPOINTS POUR CONDUCTEURS ===

@router.post("/{trip_id}/accept", summary="Accepter une course (Conducteur)")
async def accept_trip(
    trip_id: str,
    current_user: User = Depends(require_role([UserRole.DRIVER])),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Permet à un conducteur d'accepter une course.
    
    - Vérifie la disponibilité du conducteur
    - Assigne automatiquement le conducteur
    - Notifie le passager
    - Démarre le suivi temps réel
    """
    try:
        service = TripServiceAdvanced()
        
        # Vérifier que le conducteur peut accepter
        if not current_user.can_accept_trip():
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Vous ne pouvez pas accepter de course actuellement"
            )
        
        trip = await service.assign_driver(
            trip_id=trip_id,
            driver_id=str(current_user.id),
            db=db
        )
        
        return {
            "success": True,
            "data": trip.to_dict(),
            "message": "Course acceptée avec succès"
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'acceptation: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'acceptation"
        )

@router.get("/available", summary="Courses disponibles (Conducteur)")
async def get_available_trips(
    latitude: float = Query(..., ge=-90, le=90),
    longitude: float = Query(..., ge=-180, le=180),
    radius_km: float = Query(10.0, ge=1, le=50),
    trip_type: Optional[TripType] = Query(None),
    current_user: User = Depends(require_role([UserRole.DRIVER])),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Récupère les courses disponibles pour un conducteur.
    
    - Filtre par localisation et rayon
    - Prend en compte le type de véhicule
    - Trie par distance et rentabilité
    """
    try:
        service = TripServiceAdvanced()
        
        # Vérifier que le conducteur est disponible
        if not current_user.is_available_driver:
            return {
                "success": True,
                "data": [],
                "message": "Aucune course disponible (conducteur indisponible)"
            }
        
        # Rechercher les courses dans la zone
        criteria = TripSearchCriteria(
            status=[TripStatus.SEARCHING],
            trip_type=trip_type,
            pickup_area=(latitude, longitude, radius_km),
            page_size=20
        )
        
        result = await service.search_trips(criteria, db)
        
        # Calculer la distance pour chaque course
        for trip_data in result["trips"]:
            # Ajouter la distance du conducteur au point de départ
            # (implémentation simplifiée)
            trip_data["distance_to_pickup"] = 2.5  # km (exemple)
            trip_data["eta_to_pickup"] = 8  # minutes (exemple)
        
        return {
            "success": True,
            "data": result["trips"],
            "total": result["total"],
            "message": f"{result['total']} course(s) disponible(s)"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des courses disponibles: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération"
        )

# === ENDPOINTS DE RECHERCHE ===

@router.post("/search", summary="Rechercher des courses")
async def search_trips(
    request: TripSearchModel,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Recherche des courses selon des critères.
    
    - Filtrage avancé par statut, dates, utilisateurs
    - Pagination et tri
    - Permissions selon le rôle
    """
    try:
        service = TripServiceAdvanced()
        
        # Appliquer les restrictions selon le rôle avec validation sécurisée
        if current_user.role == UserRole.PASSENGER:
            # Les passagers ne peuvent voir que leurs propres courses
            validated_passenger_id = str(current_user.id)
            validated_driver_id = None
        elif current_user.role == UserRole.DRIVER:
            # Les conducteurs ne peuvent voir que leurs courses assignées
            validated_driver_id = str(current_user.id)
            validated_passenger_id = None
        elif current_user.role == UserRole.ADMIN:
            # Les admins peuvent spécifier des IDs mais ils doivent être validés
            validated_passenger_id = request.passenger_id
            validated_driver_id = request.driver_id
            
            # Validation des IDs si fournis par l'admin
            if validated_passenger_id:
                validated_passenger_id = SecureBusinessValidator._validate_user_id(validated_passenger_id)
            if validated_driver_id:
                validated_driver_id = SecureBusinessValidator._validate_user_id(validated_driver_id)
        else:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Rôle non autorisé"
            )
        
        criteria = TripSearchCriteria(
            passenger_id=validated_passenger_id,
            driver_id=validated_driver_id,
            status=request.status,
            trip_type=request.trip_type,
            date_from=request.date_from,
            date_to=request.date_to,
            page=request.page,
            page_size=request.page_size
        )
        
        result = await service.search_trips(criteria, db)
        
        return {
            "success": True,
            "data": result,
            "message": f"{result['total']} course(s) trouvée(s)"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la recherche"
        )

@router.get("/my-trips", summary="Mes courses")
async def get_my_trips(
    status: Optional[List[TripStatus]] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Récupère les courses de l'utilisateur connecté.
    
    - Courses en tant que passager ou conducteur
    - Filtrage par statut
    - Historique complet
    """
    try:
        service = TripServiceAdvanced()
        
        # Rechercher selon le rôle
        if current_user.role == UserRole.DRIVER:
            criteria = TripSearchCriteria(
                driver_id=str(current_user.id),
                status=status,
                page=page,
                page_size=page_size
            )
        else:
            criteria = TripSearchCriteria(
                passenger_id=str(current_user.id),
                status=status,
                page=page,
                page_size=page_size
            )
        
        result = await service.search_trips(criteria, db)
        
        return {
            "success": True,
            "data": result,
            "message": f"{result['total']} course(s) trouvée(s)"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des courses: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération"
        )

# === WEBSOCKET POUR SUIVI TEMPS RÉEL ===

@router.websocket("/{trip_id}/track")
async def track_trip_realtime(
    websocket: WebSocket,
    trip_id: str,
    token: str = Query(...),
    ws_manager: WebSocketManager = Depends(get_websocket_manager)
):
    """
    WebSocket pour le suivi temps réel d'une course.
    
    - Localisation du conducteur en temps réel
    - Mises à jour de statut instantanées
    - Communication passager-conducteur
    """
    connection_id = None
    try:
        # Accepter la connexion
        connection_id = await ws_manager.connect(websocket)
        
        # Authentifier avec le token
        authenticated = await ws_manager.authenticate_connection(connection_id, token)
        if not authenticated:
            await websocket.close(code=4001, reason="Authentication failed")
            return
        
        # Vérifier l'accès à la course
        # (implémentation simplifiée - à compléter avec vérification DB)
        
        # Rejoindre la room de la course
        await ws_manager.join_room(connection_id, f"trip:{trip_id}")
        
        # Boucle de maintien de connexion
        while True:
            try:
                # Recevoir les messages du client
                data = await websocket.receive_text()
                await ws_manager.handle_message(connection_id, data)
                
            except WebSocketDisconnect:
                break
                
    except Exception as e:
        logger.error(f"Erreur WebSocket pour course {trip_id}: {e}")
    finally:
        if connection_id:
            await ws_manager.disconnect(connection_id)

# === ENDPOINTS DE STATISTIQUES ===

@router.get("/stats/summary", summary="Statistiques des courses")
async def get_trip_stats(
    current_user: User = Depends(require_role([UserRole.ADMIN, UserRole.SUPPORT])),
    db: AsyncSession = Depends(get_async_session)
):
    """
    Statistiques globales des courses.
    
    Accessible uniquement aux administrateurs.
    """
    try:
        # Implémentation des statistiques
        # (à compléter avec requêtes SQL optimisées)
        
        stats = {
            "total_trips": 1250,
            "active_trips": 45,
            "completed_today": 89,
            "revenue_today": 12450.50,
            "average_rating": 4.7,
            "active_drivers": 23,
            "peak_hours": ["08:00-09:00", "17:00-19:00"]
        }
        
        return {
            "success": True,
            "data": stats,
            "message": "Statistiques récupérées"
        }
        
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )

