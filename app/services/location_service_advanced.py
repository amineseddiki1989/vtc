"""
Service de géolocalisation avancé avec calculs temps réel.
Intégration avec APIs externes et optimisations de performance.
"""

import asyncio
import math
import json
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass
from enum import Enum

import aiohttp
from geopy.distance import geodesic
from geopy.geocoders import Nominatim

from ..core.cache.redis_manager import redis_manager
from ..core.config.production_settings import get_settings
from ..core.logging.production_logger import get_logger, log_performance

logger = get_logger(__name__)

class LocationProvider(str, Enum):
    """Fournisseurs de services de géolocalisation."""
    GOOGLE_MAPS = "google_maps"
    MAPBOX = "mapbox"
    OPENSTREETMAP = "openstreetmap"
    HERE_MAPS = "here_maps"

@dataclass
class LocationPoint:
    """Point de géolocalisation."""
    latitude: float
    longitude: float
    address: Optional[str] = None
    landmark: Optional[str] = None
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None

@dataclass
class RouteInfo:
    """Informations de trajet."""
    distance_km: float
    duration_minutes: int
    polyline: Optional[str] = None
    steps: Optional[List[Dict[str, Any]]] = None
    traffic_info: Optional[Dict[str, Any]] = None
    toll_info: Optional[Dict[str, Any]] = None

@dataclass
class DriverLocation:
    """Position d'un conducteur."""
    driver_id: str
    location: LocationPoint
    heading: Optional[float] = None
    speed_kmh: Optional[float] = None
    is_available: bool = True
    last_update: Optional[datetime] = None

class LocationServiceAdvanced:
    """Service de géolocalisation avancé."""
    
    def __init__(self):
        self.settings = get_settings()
        self.geocoder = Nominatim(user_agent="uber_api_v1")
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Initialise la session HTTP."""
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Ferme la session HTTP."""
        if self.session:
            await self.session.close()
    
    # === CALCULS DE DISTANCE ET TRAJET ===
    
    @log_performance("calculate_route")
    async def calculate_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None,
        provider: LocationProvider = LocationProvider.OPENSTREETMAP,
        avoid_tolls: bool = False,
        avoid_highways: bool = False
    ) -> RouteInfo:
        """Calcule un itinéraire entre deux points."""
        try:
            # Vérifier le cache
            cache_key = f"route:{origin}:{destination}:{provider}:{avoid_tolls}:{avoid_highways}"
            cached_route = await redis_manager.get(cache_key)
            if cached_route:
                logger.debug(f"Route trouvée en cache: {cache_key}")
                return RouteInfo(**cached_route)
            
            # Calculer selon le fournisseur
            if provider == LocationProvider.GOOGLE_MAPS:
                route_info = await self._calculate_route_google(origin, destination, waypoints, avoid_tolls, avoid_highways)
            elif provider == LocationProvider.MAPBOX:
                route_info = await self._calculate_route_mapbox(origin, destination, waypoints, avoid_tolls, avoid_highways)
            elif provider == LocationProvider.HERE_MAPS:
                route_info = await self._calculate_route_here(origin, destination, waypoints, avoid_tolls, avoid_highways)
            else:
                # Fallback sur calcul simple
                route_info = await self._calculate_route_simple(origin, destination, waypoints)
            
            # Mettre en cache pour 15 minutes
            await redis_manager.set(cache_key, route_info.__dict__, expire=900)
            
            logger.info(f"Route calculée: {route_info.distance_km}km, {route_info.duration_minutes}min")
            return route_info
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul de route: {e}")
            # Fallback sur calcul simple
            return await self._calculate_route_simple(origin, destination, waypoints)
    
    async def _calculate_route_simple(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None
    ) -> RouteInfo:
        """Calcul de route simple basé sur la distance géodésique."""
        try:
            # Calculer la distance directe
            distance_km = geodesic(origin, destination).kilometers
            
            # Estimer la durée (vitesse moyenne 40 km/h en ville)
            average_speed_kmh = 40
            duration_minutes = int((distance_km / average_speed_kmh) * 60)
            
            # Ajouter du temps pour les waypoints
            if waypoints:
                for i, waypoint in enumerate(waypoints):
                    if i == 0:
                        segment_distance = geodesic(origin, waypoint).kilometers
                    else:
                        segment_distance = geodesic(waypoints[i-1], waypoint).kilometers
                    
                    distance_km += segment_distance
                    duration_minutes += int((segment_distance / average_speed_kmh) * 60)
                
                # Distance finale
                final_distance = geodesic(waypoints[-1], destination).kilometers
                distance_km += final_distance
                duration_minutes += int((final_distance / average_speed_kmh) * 60)
            
            # Ajouter une marge pour les conditions de circulation
            duration_minutes = int(duration_minutes * 1.2)  # +20% pour le trafic
            
            return RouteInfo(
                distance_km=round(distance_km, 2),
                duration_minutes=max(duration_minutes, 5),  # Minimum 5 minutes
                polyline=self._create_simple_polyline(origin, destination, waypoints),
                traffic_info={"level": "moderate", "estimated": True}
            )
            
        except Exception as e:
            logger.error(f"Erreur dans le calcul simple: {e}")
            # Valeurs par défaut
            return RouteInfo(
                distance_km=10.0,
                duration_minutes=20,
                traffic_info={"level": "unknown", "estimated": True}
            )
    
    async def _calculate_route_google(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None,
        avoid_tolls: bool = False,
        avoid_highways: bool = False
    ) -> RouteInfo:
        """Calcul de route avec Google Maps API."""
        if not self.settings.google_maps_api_key:
            return await self._calculate_route_simple(origin, destination, waypoints)
        
        try:
            url = "https://maps.googleapis.com/maps/api/directions/json"
            
            params = {
                "origin": f"{origin[0]},{origin[1]}",
                "destination": f"{destination[0]},{destination[1]}",
                "key": self.settings.google_maps_api_key,
                "mode": "driving",
                "departure_time": "now",
                "traffic_model": "best_guess"
            }
            
            if waypoints:
                waypoints_str = "|".join([f"{wp[0]},{wp[1]}" for wp in waypoints])
                params["waypoints"] = waypoints_str
            
            if avoid_tolls:
                params["avoid"] = "tolls"
            elif avoid_highways:
                params["avoid"] = "highways"
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                
                if data["status"] == "OK" and data["routes"]:
                    route = data["routes"][0]
                    leg = route["legs"][0]
                    
                    return RouteInfo(
                        distance_km=leg["distance"]["value"] / 1000,
                        duration_minutes=leg["duration_in_traffic"]["value"] // 60 if "duration_in_traffic" in leg else leg["duration"]["value"] // 60,
                        polyline=route["overview_polyline"]["points"],
                        steps=[{
                            "instruction": step["html_instructions"],
                            "distance": step["distance"]["text"],
                            "duration": step["duration"]["text"]
                        } for step in leg["steps"]],
                        traffic_info={
                            "level": "real_time",
                            "source": "google_maps"
                        }
                    )
                else:
                    logger.warning(f"Google Maps API error: {data.get('status', 'Unknown')}")
                    return await self._calculate_route_simple(origin, destination, waypoints)
                    
        except Exception as e:
            logger.error(f"Erreur Google Maps API: {e}")
            return await self._calculate_route_simple(origin, destination, waypoints)
    
    async def _calculate_route_mapbox(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None,
        avoid_tolls: bool = False,
        avoid_highways: bool = False
    ) -> RouteInfo:
        """Calcul de route avec Mapbox API."""
        if not self.settings.mapbox_api_key:
            return await self._calculate_route_simple(origin, destination, waypoints)
        
        try:
            # Construire les coordonnées
            coordinates = [f"{origin[1]},{origin[0]}"]  # Mapbox utilise lng,lat
            
            if waypoints:
                coordinates.extend([f"{wp[1]},{wp[0]}" for wp in waypoints])
            
            coordinates.append(f"{destination[1]},{destination[0]}")
            coordinates_str = ";".join(coordinates)
            
            url = f"https://api.mapbox.com/directions/v5/mapbox/driving-traffic/{coordinates_str}"
            
            params = {
                "access_token": self.settings.mapbox_api_key,
                "geometries": "polyline",
                "steps": "true",
                "annotations": "duration,distance"
            }
            
            if avoid_tolls:
                params["exclude"] = "toll"
            elif avoid_highways:
                params["exclude"] = "motorway"
            
            async with self.session.get(url, params=params) as response:
                data = await response.json()
                
                if data.get("routes"):
                    route = data["routes"][0]
                    
                    return RouteInfo(
                        distance_km=route["distance"] / 1000,
                        duration_minutes=route["duration"] // 60,
                        polyline=route["geometry"],
                        steps=[{
                            "instruction": step["maneuver"]["instruction"],
                            "distance": f"{step['distance']}m",
                            "duration": f"{step['duration']}s"
                        } for leg in route["legs"] for step in leg["steps"]],
                        traffic_info={
                            "level": "real_time",
                            "source": "mapbox"
                        }
                    )
                else:
                    logger.warning(f"Mapbox API error: {data.get('message', 'Unknown')}")
                    return await self._calculate_route_simple(origin, destination, waypoints)
                    
        except Exception as e:
            logger.error(f"Erreur Mapbox API: {e}")
            return await self._calculate_route_simple(origin, destination, waypoints)
    
    async def _calculate_route_here(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None,
        avoid_tolls: bool = False,
        avoid_highways: bool = False
    ) -> RouteInfo:
        """Calcul de route avec HERE Maps API."""
        # Implémentation similaire pour HERE Maps
        return await self._calculate_route_simple(origin, destination, waypoints)
    
    def _create_simple_polyline(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: Optional[List[Tuple[float, float]]] = None
    ) -> str:
        """Crée une polyline simple pour visualisation."""
        points = [origin]
        if waypoints:
            points.extend(waypoints)
        points.append(destination)
        
        # Encoder en polyline simple (format Google)
        # Pour simplifier, on retourne une chaîne JSON
        return json.dumps([{"lat": p[0], "lng": p[1]} for p in points])
    
    # === GÉOCODAGE ===
    
    @log_performance("geocode_address")
    async def geocode_address(self, address: str) -> Optional[LocationPoint]:
        """Convertit une adresse en coordonnées."""
        try:
            # Vérifier le cache
            cache_key = f"geocode:{address}"
            cached_result = await redis_manager.get(cache_key)
            if cached_result:
                return LocationPoint(**cached_result)
            
            # Géocoder l'adresse
            location = self.geocoder.geocode(address)
            if location:
                point = LocationPoint(
                    latitude=location.latitude,
                    longitude=location.longitude,
                    address=location.address,
                    accuracy=95.0  # Estimation
                )
                
                # Mettre en cache pour 24 heures
                await redis_manager.set(cache_key, point.__dict__, expire=86400)
                
                logger.debug(f"Adresse géocodée: {address} -> {point.latitude}, {point.longitude}")
                return point
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors du géocodage: {e}")
            return None
    
    @log_performance("reverse_geocode")
    async def reverse_geocode(self, latitude: float, longitude: float) -> Optional[str]:
        """Convertit des coordonnées en adresse."""
        try:
            # Vérifier le cache
            cache_key = f"reverse_geocode:{latitude}:{longitude}"
            cached_result = await redis_manager.get(cache_key)
            if cached_result:
                return cached_result
            
            # Géocodage inverse
            location = self.geocoder.reverse((latitude, longitude))
            if location:
                address = location.address
                
                # Mettre en cache pour 24 heures
                await redis_manager.set(cache_key, address, expire=86400)
                
                logger.debug(f"Coordonnées géocodées: {latitude}, {longitude} -> {address}")
                return address
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors du géocodage inverse: {e}")
            return None
    
    # === GESTION DES POSITIONS DE CONDUCTEURS ===
    
    @log_performance("update_driver_location")
    async def update_driver_location(
        self,
        driver_id: str,
        latitude: float,
        longitude: float,
        heading: Optional[float] = None,
        speed_kmh: Optional[float] = None,
        is_available: bool = True
    ) -> bool:
        """Met à jour la position d'un conducteur."""
        try:
            driver_location = DriverLocation(
                driver_id=driver_id,
                location=LocationPoint(
                    latitude=latitude,
                    longitude=longitude,
                    timestamp=datetime.now(timezone.utc)
                ),
                heading=heading,
                speed_kmh=speed_kmh,
                is_available=is_available,
                last_update=datetime.now(timezone.utc)
            )
            
            # Stocker dans Redis avec expiration de 5 minutes
            cache_key = f"driver_location:{driver_id}"
            await redis_manager.set(cache_key, driver_location.__dict__, expire=300)
            
            # Publier la mise à jour pour les abonnés
            await redis_manager.publish(
                f"driver_location_updates",
                {
                    "driver_id": driver_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "heading": heading,
                    "speed_kmh": speed_kmh,
                    "is_available": is_available,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            logger.debug(f"Position conducteur mise à jour: {driver_id} -> {latitude}, {longitude}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour de position: {e}")
            return False
    
    @log_performance("get_driver_location")
    async def get_driver_location(self, driver_id: str) -> Optional[DriverLocation]:
        """Récupère la position actuelle d'un conducteur."""
        try:
            cache_key = f"driver_location:{driver_id}"
            cached_data = await redis_manager.get(cache_key)
            
            if cached_data:
                # Reconstituer l'objet
                location_data = cached_data["location"]
                location = LocationPoint(**location_data)
                
                return DriverLocation(
                    driver_id=cached_data["driver_id"],
                    location=location,
                    heading=cached_data.get("heading"),
                    speed_kmh=cached_data.get("speed_kmh"),
                    is_available=cached_data.get("is_available", True),
                    last_update=datetime.fromisoformat(cached_data["last_update"]) if cached_data.get("last_update") else None
                )
            
            return None
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération de position: {e}")
            return None
    
    @log_performance("find_nearby_drivers")
    async def find_nearby_drivers(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10.0,
        max_drivers: int = 20,
        only_available: bool = True
    ) -> List[DriverLocation]:
        """Trouve les conducteurs proches d'une position."""
        try:
            # Récupérer toutes les positions de conducteurs
            pattern = "driver_location:*"
            keys = await redis_manager.redis.keys(pattern)
            
            nearby_drivers = []
            
            for key in keys:
                try:
                    cached_data = await redis_manager.get(key.decode())
                    if not cached_data:
                        continue
                    
                    # Filtrer par disponibilité
                    if only_available and not cached_data.get("is_available", True):
                        continue
                    
                    # Calculer la distance
                    driver_lat = cached_data["location"]["latitude"]
                    driver_lng = cached_data["location"]["longitude"]
                    
                    distance_km = geodesic(
                        (latitude, longitude),
                        (driver_lat, driver_lng)
                    ).kilometers
                    
                    # Filtrer par rayon
                    if distance_km <= radius_km:
                        location_data = cached_data["location"]
                        location = LocationPoint(**location_data)
                        
                        driver_location = DriverLocation(
                            driver_id=cached_data["driver_id"],
                            location=location,
                            heading=cached_data.get("heading"),
                            speed_kmh=cached_data.get("speed_kmh"),
                            is_available=cached_data.get("is_available", True),
                            last_update=datetime.fromisoformat(cached_data["last_update"]) if cached_data.get("last_update") else None
                        )
                        
                        # Ajouter la distance pour le tri
                        driver_location.distance_km = distance_km
                        nearby_drivers.append(driver_location)
                        
                except Exception as e:
                    logger.warning(f"Erreur lors du traitement du conducteur {key}: {e}")
                    continue
            
            # Trier par distance et limiter
            nearby_drivers.sort(key=lambda d: getattr(d, 'distance_km', float('inf')))
            result = nearby_drivers[:max_drivers]
            
            logger.info(f"Trouvé {len(result)} conducteurs dans un rayon de {radius_km}km")
            return result
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche de conducteurs: {e}")
            return []
    
    # === CALCULS D'ETA ===
    
    @log_performance("calculate_eta")
    async def calculate_eta(
        self,
        from_location: Tuple[float, float],
        to_location: Tuple[float, float],
        current_time: Optional[datetime] = None
    ) -> int:
        """Calcule l'ETA en minutes entre deux points."""
        try:
            # Utiliser le calcul de route pour obtenir une estimation précise
            route_info = await self.calculate_route(from_location, to_location)
            
            # Ajouter des facteurs de correction selon l'heure
            if current_time is None:
                current_time = datetime.now(timezone.utc)
            
            hour = current_time.hour
            
            # Facteurs de correction selon l'heure (heures de pointe)
            if 7 <= hour <= 9 or 17 <= hour <= 19:
                # Heures de pointe
                correction_factor = 1.4
            elif 22 <= hour or hour <= 6:
                # Nuit
                correction_factor = 0.8
            else:
                # Heures normales
                correction_factor = 1.0
            
            eta_minutes = int(route_info.duration_minutes * correction_factor)
            
            # Minimum 2 minutes, maximum 120 minutes
            return max(2, min(eta_minutes, 120))
            
        except Exception as e:
            logger.error(f"Erreur lors du calcul d'ETA: {e}")
            # Fallback sur calcul simple
            distance_km = geodesic(from_location, to_location).kilometers
            return max(2, int((distance_km / 30) * 60))  # 30 km/h moyenne
    
    # === ZONES ET GÉOFENCING ===
    
    def is_point_in_polygon(
        self,
        point: Tuple[float, float],
        polygon: List[Tuple[float, float]]
    ) -> bool:
        """Vérifie si un point est dans un polygone."""
        x, y = point
        n = len(polygon)
        inside = False
        
        p1x, p1y = polygon[0]
        for i in range(1, n + 1):
            p2x, p2y = polygon[i % n]
            if y > min(p1y, p2y):
                if y <= max(p1y, p2y):
                    if x <= max(p1x, p2x):
                        if p1y != p2y:
                            xinters = (y - p1y) * (p2x - p1x) / (p2y - p1y) + p1x
                        if p1x == p2x or x <= xinters:
                            inside = not inside
            p1x, p1y = p2x, p2y
        
        return inside
    
    def is_point_in_circle(
        self,
        point: Tuple[float, float],
        center: Tuple[float, float],
        radius_km: float
    ) -> bool:
        """Vérifie si un point est dans un cercle."""
        distance_km = geodesic(point, center).kilometers
        return distance_km <= radius_km
    
    # === OPTIMISATION DE TRAJETS ===
    
    @log_performance("optimize_route")
    async def optimize_route(
        self,
        origin: Tuple[float, float],
        destination: Tuple[float, float],
        waypoints: List[Tuple[float, float]]
    ) -> List[Tuple[float, float]]:
        """Optimise l'ordre des waypoints pour minimiser la distance."""
        if not waypoints:
            return []
        
        try:
            # Algorithme simple du plus proche voisin
            remaining_waypoints = waypoints.copy()
            optimized_order = []
            current_point = origin
            
            while remaining_waypoints:
                # Trouver le waypoint le plus proche
                closest_waypoint = None
                min_distance = float('inf')
                
                for waypoint in remaining_waypoints:
                    distance = geodesic(current_point, waypoint).kilometers
                    if distance < min_distance:
                        min_distance = distance
                        closest_waypoint = waypoint
                
                # Ajouter le waypoint le plus proche
                optimized_order.append(closest_waypoint)
                remaining_waypoints.remove(closest_waypoint)
                current_point = closest_waypoint
            
            logger.info(f"Route optimisée avec {len(optimized_order)} waypoints")
            return optimized_order
            
        except Exception as e:
            logger.error(f"Erreur lors de l'optimisation: {e}")
            return waypoints  # Retourner l'ordre original en cas d'erreur
    
    # === MÉTRIQUES ET STATISTIQUES ===
    
    async def get_location_stats(self) -> Dict[str, Any]:
        """Récupère les statistiques de géolocalisation."""
        try:
            # Compter les conducteurs actifs
            pattern = "driver_location:*"
            keys = await redis_manager.redis.keys(pattern)
            
            total_drivers = len(keys)
            available_drivers = 0
            
            for key in keys:
                try:
                    cached_data = await redis_manager.get(key.decode())
                    if cached_data and cached_data.get("is_available", True):
                        available_drivers += 1
                except:
                    continue
            
            return {
                "total_tracked_drivers": total_drivers,
                "available_drivers": available_drivers,
                "unavailable_drivers": total_drivers - available_drivers,
                "last_updated": datetime.now(timezone.utc).isoformat()
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des stats: {e}")
            return {
                "total_tracked_drivers": 0,
                "available_drivers": 0,
                "unavailable_drivers": 0,
                "error": str(e)
            }

