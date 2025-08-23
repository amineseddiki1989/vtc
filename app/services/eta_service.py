"""
Service ETA dynamique avec APIs externes.
Calcul des temps d'arrivée en temps réel avec trafic et conditions routières.
"""

import asyncio
import aiohttp
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from enum import Enum

from geopy.distance import geodesic
from sqlalchemy.orm import Session

from ..models.location import DriverLocation
from ..models.trip import Trip
from ..services.metrics_service import get_metrics_collector
from ..core.config.settings import get_settings
import logging

logger = logging.getLogger(__name__)
settings = get_settings()

class ETAProvider(str, Enum):
    """Fournisseurs d'API ETA."""
    OPENROUTE = "openroute"
    OSRM = "osrm"
    MAPBOX = "mapbox"
    GOOGLE = "google"
    FALLBACK = "fallback"

@dataclass
class ETAResult:
    """Résultat de calcul ETA."""
    duration_seconds: int
    distance_meters: int
    provider: ETAProvider
    confidence: float
    traffic_factor: float
    route_quality: str
    timestamp: datetime
    
    @property
    def duration_minutes(self) -> float:
        """Durée en minutes."""
        return self.duration_seconds / 60
    
    @property
    def distance_km(self) -> float:
        """Distance en kilomètres."""
        return self.distance_meters / 1000

class ETAService:
    """Service de calcul ETA dynamique avec APIs externes."""
    
    def __init__(self, db: Session):
        self.db = db
        self.metrics_collector = get_metrics_collector()
        self.session = None
        
        # Configuration des APIs
        self.api_configs = {
            ETAProvider.OSRM: {
                "base_url": "http://router.project-osrm.org/route/v1/driving",
                "timeout": 5,
                "enabled": True
            },
            ETAProvider.OPENROUTE: {
                "base_url": "https://api.openrouteservice.org/v2/directions/driving-car",
                "timeout": 5,
                "enabled": False,  # Nécessite une clé API
                "api_key": None
            },
            ETAProvider.MAPBOX: {
                "base_url": "https://api.mapbox.com/directions/v5/mapbox/driving",
                "timeout": 5,
                "enabled": False,  # Nécessite une clé API
                "api_key": None
            }
        }
    
    async def __aenter__(self):
        """Initialiser la session HTTP."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Fermer la session HTTP."""
        if self.session:
            await self.session.close()
    
    async def calculate_eta(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float,
        provider: Optional[ETAProvider] = None
    ) -> ETAResult:
        """
        Calculer l'ETA entre deux points.
        
        Args:
            origin_lat: Latitude d'origine
            origin_lng: Longitude d'origine
            dest_lat: Latitude de destination
            dest_lng: Longitude de destination
            provider: Fournisseur d'API spécifique (optionnel)
            
        Returns:
            ETAResult: Résultat du calcul ETA
        """
        start_time = datetime.now(timezone.utc)
        
        try:
            # Essayer les fournisseurs dans l'ordre de priorité
            providers_to_try = [provider] if provider else [
                ETAProvider.OSRM,
                ETAProvider.OPENROUTE,
                ETAProvider.MAPBOX,
                ETAProvider.FALLBACK
            ]
            
            for api_provider in providers_to_try:
                if api_provider == ETAProvider.FALLBACK:
                    # Calcul de fallback basé sur la distance
                    return self._calculate_fallback_eta(
                        origin_lat, origin_lng, dest_lat, dest_lng
                    )
                
                config = self.api_configs.get(api_provider)
                if not config or not config["enabled"]:
                    continue
                
                try:
                    result = await self._call_api(
                        api_provider, origin_lat, origin_lng, dest_lat, dest_lng
                    )
                    
                    if result:
                        # Enregistrer les métriques de succès
                        self.metrics_collector.record_metric(
                            name="eta_calculation_success",
                            value=1,
                            metric_type="counter",
                            category="geolocation",
                            labels={
                                "provider": api_provider.value,
                                "duration_ms": int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
                            },
                            description=f"Calcul ETA réussi avec {api_provider.value}"
                        )
                        
                        return result
                        
                except Exception as e:
                    logger.warning(f"Erreur API {api_provider.value}: {e}")
                    
                    # Enregistrer les métriques d'erreur
                    self.metrics_collector.record_metric(
                        name="eta_calculation_error",
                        value=1,
                        metric_type="counter",
                        category="geolocation",
                        labels={
                            "provider": api_provider.value,
                            "error_type": type(e).__name__
                        },
                        description=f"Erreur calcul ETA avec {api_provider.value}"
                    )
                    
                    continue
            
            # Si tous les fournisseurs échouent, utiliser le fallback
            return self._calculate_fallback_eta(
                origin_lat, origin_lng, dest_lat, dest_lng
            )
            
        except Exception as e:
            logger.error(f"Erreur critique calcul ETA: {e}")
            return self._calculate_fallback_eta(
                origin_lat, origin_lng, dest_lat, dest_lng
            )
    
    async def _call_api(
        self,
        provider: ETAProvider,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> Optional[ETAResult]:
        """Appeler une API spécifique pour le calcul ETA."""
        
        if provider == ETAProvider.OSRM:
            return await self._call_osrm_api(origin_lat, origin_lng, dest_lat, dest_lng)
        elif provider == ETAProvider.OPENROUTE:
            return await self._call_openroute_api(origin_lat, origin_lng, dest_lat, dest_lng)
        elif provider == ETAProvider.MAPBOX:
            return await self._call_mapbox_api(origin_lat, origin_lng, dest_lat, dest_lng)
        
        return None
    
    async def _call_osrm_api(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> Optional[ETAResult]:
        """Appeler l'API OSRM (Open Source Routing Machine)."""
        
        config = self.api_configs[ETAProvider.OSRM]
        url = f"{config['base_url']}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        
        params = {
            "overview": "false",
            "geometries": "geojson",
            "steps": "false"
        }
        
        async with self.session.get(
            url, 
            params=params, 
            timeout=aiohttp.ClientTimeout(total=config["timeout"])
        ) as response:
            
            if response.status != 200:
                raise Exception(f"OSRM API error: {response.status}")
            
            data = await response.json()
            
            if data.get("code") != "Ok" or not data.get("routes"):
                raise Exception("OSRM: No route found")
            
            route = data["routes"][0]
            duration = route["duration"]  # en secondes
            distance = route["distance"]  # en mètres
            
            # Calculer le facteur de trafic (estimation basée sur l'heure)
            traffic_factor = self._estimate_traffic_factor()
            
            return ETAResult(
                duration_seconds=int(duration * traffic_factor),
                distance_meters=int(distance),
                provider=ETAProvider.OSRM,
                confidence=0.85,
                traffic_factor=traffic_factor,
                route_quality="good",
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _call_openroute_api(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> Optional[ETAResult]:
        """Appeler l'API OpenRouteService."""
        
        config = self.api_configs[ETAProvider.OPENROUTE]
        
        if not config.get("api_key"):
            raise Exception("OpenRouteService API key not configured")
        
        url = config["base_url"]
        
        headers = {
            "Authorization": config["api_key"],
            "Content-Type": "application/json"
        }
        
        data = {
            "coordinates": [[origin_lng, origin_lat], [dest_lng, dest_lat]],
            "format": "json"
        }
        
        async with self.session.post(
            url,
            headers=headers,
            json=data,
            timeout=aiohttp.ClientTimeout(total=config["timeout"])
        ) as response:
            
            if response.status != 200:
                raise Exception(f"OpenRouteService API error: {response.status}")
            
            data = await response.json()
            
            if not data.get("routes"):
                raise Exception("OpenRouteService: No route found")
            
            route = data["routes"][0]
            summary = route["summary"]
            duration = summary["duration"]  # en secondes
            distance = summary["distance"]  # en mètres
            
            traffic_factor = self._estimate_traffic_factor()
            
            return ETAResult(
                duration_seconds=int(duration * traffic_factor),
                distance_meters=int(distance),
                provider=ETAProvider.OPENROUTE,
                confidence=0.90,
                traffic_factor=traffic_factor,
                route_quality="excellent",
                timestamp=datetime.now(timezone.utc)
            )
    
    async def _call_mapbox_api(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> Optional[ETAResult]:
        """Appeler l'API Mapbox Directions."""
        
        config = self.api_configs[ETAProvider.MAPBOX]
        
        if not config.get("api_key"):
            raise Exception("Mapbox API key not configured")
        
        url = f"{config['base_url']}/{origin_lng},{origin_lat};{dest_lng},{dest_lat}"
        
        params = {
            "access_token": config["api_key"],
            "overview": "false",
            "geometries": "geojson",
            "steps": "false"
        }
        
        async with self.session.get(
            url,
            params=params,
            timeout=aiohttp.ClientTimeout(total=config["timeout"])
        ) as response:
            
            if response.status != 200:
                raise Exception(f"Mapbox API error: {response.status}")
            
            data = await response.json()
            
            if data.get("code") != "Ok" or not data.get("routes"):
                raise Exception("Mapbox: No route found")
            
            route = data["routes"][0]
            duration = route["duration"]  # en secondes
            distance = route["distance"]  # en mètres
            
            traffic_factor = self._estimate_traffic_factor()
            
            return ETAResult(
                duration_seconds=int(duration * traffic_factor),
                distance_meters=int(distance),
                provider=ETAProvider.MAPBOX,
                confidence=0.95,
                traffic_factor=traffic_factor,
                route_quality="excellent",
                timestamp=datetime.now(timezone.utc)
            )
    
    def _calculate_fallback_eta(
        self,
        origin_lat: float,
        origin_lng: float,
        dest_lat: float,
        dest_lng: float
    ) -> ETAResult:
        """Calcul ETA de fallback basé sur la distance à vol d'oiseau."""
        
        # Distance à vol d'oiseau
        distance_km = geodesic(
            (origin_lat, origin_lng),
            (dest_lat, dest_lng)
        ).kilometers
        
        # Estimation de la vitesse moyenne en ville (25 km/h)
        avg_speed_kmh = 25
        
        # Facteur de détour pour les routes réelles (1.3x la distance directe)
        detour_factor = 1.3
        
        # Facteur de trafic
        traffic_factor = self._estimate_traffic_factor()
        
        # Calcul du temps
        real_distance_km = distance_km * detour_factor
        duration_hours = real_distance_km / avg_speed_kmh
        duration_seconds = int(duration_hours * 3600 * traffic_factor)
        
        return ETAResult(
            duration_seconds=duration_seconds,
            distance_meters=int(real_distance_km * 1000),
            provider=ETAProvider.FALLBACK,
            confidence=0.60,
            traffic_factor=traffic_factor,
            route_quality="estimated",
            timestamp=datetime.now(timezone.utc)
        )
    
    def _estimate_traffic_factor(self) -> float:
        """Estimer le facteur de trafic basé sur l'heure."""
        
        now = datetime.now()
        hour = now.hour
        weekday = now.weekday()  # 0 = lundi, 6 = dimanche
        
        # Facteurs de trafic par heure (1.0 = normal, >1.0 = plus lent)
        if weekday < 5:  # Jours de semaine
            if 7 <= hour <= 9 or 17 <= hour <= 19:  # Heures de pointe
                return 1.5
            elif 10 <= hour <= 16:  # Journée normale
                return 1.1
            elif 20 <= hour <= 22:  # Soirée
                return 1.2
            else:  # Nuit/tôt le matin
                return 0.8
        else:  # Week-end
            if 10 <= hour <= 18:  # Journée week-end
                return 1.2
            else:
                return 0.9
    
    async def calculate_driver_eta_to_passenger(
        self,
        driver_id: str,
        passenger_lat: float,
        passenger_lng: float
    ) -> Optional[ETAResult]:
        """Calculer l'ETA d'un conducteur vers un passager."""
        
        # Récupérer la position actuelle du conducteur
        driver_location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).order_by(DriverLocation.updated_at.desc()).first()
        
        if not driver_location:
            logger.warning(f"Position conducteur {driver_id} non trouvée")
            return None
        
        # Calculer l'ETA
        eta_result = await self.calculate_eta(
            driver_location.latitude,
            driver_location.longitude,
            passenger_lat,
            passenger_lng
        )
        
        # Enregistrer les métriques
        self.metrics_collector.record_metric(
            name="driver_eta_calculated",
            value=eta_result.duration_minutes,
            metric_type="gauge",
            category="geolocation",
            labels={
                "provider": eta_result.provider.value,
                "confidence": str(eta_result.confidence)
            },
            user_id=driver_id,
            description="ETA conducteur vers passager calculé"
        )
        
        return eta_result
    
    async def update_trip_eta(self, trip_id: str) -> Optional[ETAResult]:
        """Mettre à jour l'ETA d'une course en cours."""
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip or not trip.driver_id:
            return None
        
        # Calculer l'ETA vers la destination
        eta_result = await self.calculate_driver_eta_to_passenger(
            trip.driver_id,
            trip.destination_latitude,
            trip.destination_longitude
        )
        
        if eta_result:
            # Mettre à jour la durée estimée dans la base
            trip.duration_minutes = int(eta_result.duration_minutes)
            self.db.commit()
            
            logger.info(f"ETA course {trip_id} mis à jour: {eta_result.duration_minutes:.1f} min")
        
        return eta_result
    
    async def get_nearby_drivers_with_eta(
        self,
        passenger_lat: float,
        passenger_lng: float,
        max_distance_km: float = 10,
        max_drivers: int = 5
    ) -> List[Dict[str, Any]]:
        """Obtenir les conducteurs proches avec leur ETA."""
        
        # Récupérer les conducteurs proches
        nearby_drivers = self.db.query(DriverLocation).filter(
            # Filtre approximatif par coordonnées (à améliorer avec PostGIS)
            DriverLocation.latitude.between(
                passenger_lat - 0.1, passenger_lat + 0.1
            ),
            DriverLocation.longitude.between(
                passenger_lng - 0.1, passenger_lng + 0.1
            )
        ).limit(max_drivers * 2).all()  # Récupérer plus pour filtrer ensuite
        
        drivers_with_eta = []
        
        # Calculer l'ETA pour chaque conducteur
        for driver_location in nearby_drivers:
            # Vérifier la distance réelle
            distance_km = geodesic(
                (passenger_lat, passenger_lng),
                (driver_location.latitude, driver_location.longitude)
            ).kilometers
            
            if distance_km > max_distance_km:
                continue
            
            # Calculer l'ETA
            eta_result = await self.calculate_eta(
                driver_location.latitude,
                driver_location.longitude,
                passenger_lat,
                passenger_lng
            )
            
            drivers_with_eta.append({
                "driver_id": driver_location.driver_id,
                "distance_km": round(distance_km, 2),
                "eta_minutes": round(eta_result.duration_minutes, 1),
                "eta_confidence": eta_result.confidence,
                "provider": eta_result.provider.value,
                "last_update": driver_location.updated_at.isoformat()
            })
        
        # Trier par ETA croissant
        drivers_with_eta.sort(key=lambda x: x["eta_minutes"])
        
        return drivers_with_eta[:max_drivers]

