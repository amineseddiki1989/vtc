"""
API ETA dynamique pour calculs de temps d'arrivée.
"""

from datetime import datetime, timezone
from typing import List, Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.database.session import get_db
from ...core.auth.dependencies import get_current_user
from ...models.user import User, UserRole
from ...services.eta_service import ETAService, ETAProvider, ETAResult
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/eta", tags=["ETA Dynamique"])

# === MODÈLES PYDANTIC ===

class ETARequest(BaseModel):
    """Demande de calcul ETA."""
    origin_latitude: float = Field(..., ge=-90, le=90)
    origin_longitude: float = Field(..., ge=-180, le=180)
    destination_latitude: float = Field(..., ge=-90, le=90)
    destination_longitude: float = Field(..., ge=-180, le=180)
    provider: Optional[ETAProvider] = None

class ETAResponse(BaseModel):
    """Réponse de calcul ETA."""
    duration_seconds: int
    duration_minutes: float
    distance_meters: int
    distance_km: float
    provider: str
    confidence: float
    traffic_factor: float
    route_quality: str
    timestamp: str

class NearbyDriversRequest(BaseModel):
    """Demande de conducteurs proches avec ETA."""
    passenger_latitude: float = Field(..., ge=-90, le=90)
    passenger_longitude: float = Field(..., ge=-180, le=180)
    max_distance_km: float = Field(10, ge=1, le=50)
    max_drivers: int = Field(5, ge=1, le=20)

class DriverETAResponse(BaseModel):
    """Réponse ETA conducteur."""
    driver_id: str
    distance_km: float
    eta_minutes: float
    eta_confidence: float
    provider: str
    last_update: str

# === ENDPOINTS ===

@router.post("/calculate", response_model=ETAResponse)
async def calculate_eta(
    request: ETARequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calculer l'ETA entre deux points.
    
    - **origin_latitude/longitude**: Coordonnées de départ
    - **destination_latitude/longitude**: Coordonnées d'arrivée
    - **provider**: Fournisseur d'API spécifique (optionnel)
    
    Retourne:
    - Durée en secondes et minutes
    - Distance en mètres et kilomètres
    - Fournisseur utilisé et niveau de confiance
    - Facteur de trafic appliqué
    """
    
    try:
        async with ETAService(db) as eta_service:
            eta_result = await eta_service.calculate_eta(
                origin_lat=request.origin_latitude,
                origin_lng=request.origin_longitude,
                dest_lat=request.destination_latitude,
                dest_lng=request.destination_longitude,
                provider=request.provider
            )
            
            return ETAResponse(
                duration_seconds=eta_result.duration_seconds,
                duration_minutes=eta_result.duration_minutes,
                distance_meters=eta_result.distance_meters,
                distance_km=eta_result.distance_km,
                provider=eta_result.provider.value,
                confidence=eta_result.confidence,
                traffic_factor=eta_result.traffic_factor,
                route_quality=eta_result.route_quality,
                timestamp=eta_result.timestamp.isoformat()
            )
            
    except Exception as e:
        logger.error(f"Erreur calcul ETA: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul ETA: {str(e)}"
        )

@router.get("/driver/{driver_id}/to-passenger")
async def get_driver_eta_to_passenger(
    driver_id: str,
    passenger_latitude: float = Query(..., ge=-90, le=90),
    passenger_longitude: float = Query(..., ge=-180, le=180),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Calculer l'ETA d'un conducteur vers un passager.
    
    - **driver_id**: ID du conducteur
    - **passenger_latitude/longitude**: Position du passager
    
    Retourne l'ETA du conducteur vers le passager.
    """
    
    try:
        async with ETAService(db) as eta_service:
            eta_result = await eta_service.calculate_driver_eta_to_passenger(
                driver_id=driver_id,
                passenger_lat=passenger_latitude,
                passenger_lng=passenger_longitude
            )
            
            if not eta_result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Position du conducteur {driver_id} non trouvée"
                )
            
            return ETAResponse(
                duration_seconds=eta_result.duration_seconds,
                duration_minutes=eta_result.duration_minutes,
                distance_meters=eta_result.distance_meters,
                distance_km=eta_result.distance_km,
                provider=eta_result.provider.value,
                confidence=eta_result.confidence,
                traffic_factor=eta_result.traffic_factor,
                route_quality=eta_result.route_quality,
                timestamp=eta_result.timestamp.isoformat()
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur calcul ETA conducteur {driver_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du calcul ETA: {str(e)}"
        )

@router.post("/nearby-drivers", response_model=List[DriverETAResponse])
async def get_nearby_drivers_with_eta(
    request: NearbyDriversRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Obtenir les conducteurs proches avec leur ETA.
    
    - **passenger_latitude/longitude**: Position du passager
    - **max_distance_km**: Distance maximale de recherche
    - **max_drivers**: Nombre maximum de conducteurs
    
    Retourne la liste des conducteurs proches triés par ETA.
    """
    
    try:
        async with ETAService(db) as eta_service:
            drivers_with_eta = await eta_service.get_nearby_drivers_with_eta(
                passenger_lat=request.passenger_latitude,
                passenger_lng=request.passenger_longitude,
                max_distance_km=request.max_distance_km,
                max_drivers=request.max_drivers
            )
            
            return [
                DriverETAResponse(**driver_data)
                for driver_data in drivers_with_eta
            ]
            
    except Exception as e:
        logger.error(f"Erreur recherche conducteurs proches: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la recherche: {str(e)}"
        )

@router.put("/trip/{trip_id}/update")
async def update_trip_eta(
    trip_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Mettre à jour l'ETA d'une course en cours.
    
    - **trip_id**: ID de la course
    
    Recalcule et met à jour l'ETA de la course.
    """
    
    try:
        async with ETAService(db) as eta_service:
            eta_result = await eta_service.update_trip_eta(trip_id)
            
            if not eta_result:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Course {trip_id} non trouvée ou sans conducteur assigné"
                )
            
            return {
                "trip_id": trip_id,
                "updated_eta": {
                    "duration_minutes": eta_result.duration_minutes,
                    "provider": eta_result.provider.value,
                    "confidence": eta_result.confidence,
                    "timestamp": eta_result.timestamp.isoformat()
                },
                "message": "ETA de la course mis à jour"
            }
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur mise à jour ETA course {trip_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la mise à jour: {str(e)}"
        )

@router.get("/providers")
async def get_eta_providers(
    current_user: User = Depends(get_current_user)
):
    """
    Obtenir la liste des fournisseurs ETA disponibles.
    
    Retourne les fournisseurs d'API ETA configurés et leur statut.
    """
    
    providers = []
    
    for provider in ETAProvider:
        if provider == ETAProvider.FALLBACK:
            providers.append({
                "name": provider.value,
                "display_name": "Calcul de fallback",
                "enabled": True,
                "description": "Calcul basé sur la distance géodésique",
                "confidence": 0.60
            })
        elif provider == ETAProvider.OSRM:
            providers.append({
                "name": provider.value,
                "display_name": "OSRM (Open Source)",
                "enabled": True,
                "description": "Open Source Routing Machine",
                "confidence": 0.85
            })
        elif provider == ETAProvider.OPENROUTE:
            providers.append({
                "name": provider.value,
                "display_name": "OpenRouteService",
                "enabled": False,
                "description": "Service de routage OpenStreetMap",
                "confidence": 0.90
            })
        elif provider == ETAProvider.MAPBOX:
            providers.append({
                "name": provider.value,
                "display_name": "Mapbox Directions",
                "enabled": False,
                "description": "API Mapbox avec données de trafic",
                "confidence": 0.95
            })
    
    return {
        "providers": providers,
        "default_fallback": ETAProvider.FALLBACK.value,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

