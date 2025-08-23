"""
Service de géolocalisation professionnel avec métriques intégrées.
"""

from typing import List, Tuple, Optional
from sqlalchemy.orm import Session
from sqlalchemy import and_, func
from geopy.distance import geodesic
from datetime import datetime, timedelta

from ..models.location import DriverLocation, TripLocation
from ..models.user import User, UserRole
from ..services.metrics_service import get_metrics_collector
from ..models.metrics import MetricType, MetricCategory
from ..core.monitoring.decorators import monitor_business_operation, monitor_function


class LocationService:
    """Service de gestion de la géolocalisation avec monitoring intégré."""
    
    def __init__(self, db: Session):
        self.db = db
        self.collector = get_metrics_collector()
    
    @monitor_business_operation("driver_location_update", "location")
    def update_driver_location(
        self,
        driver_id: str,
        latitude: float,
        longitude: float,
        heading: Optional[float] = None,
        speed: Optional[float] = None,
        accuracy: Optional[float] = None
    ) -> DriverLocation:
        """Met à jour la position d'un conducteur avec métriques."""
        
        # Vérifier que c'est bien un conducteur
        driver = self.db.query(User).filter(
            and_(User.id == driver_id, User.role == UserRole.DRIVER)
        ).first()
        
        if not driver:
            self.collector.record_metric(
                name="location_update_invalid_driver",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={"reason": "driver_not_found"},
                user_id=driver_id,
                description="Tentative de mise à jour de position pour conducteur invalide"
            )
            raise ValueError("Conducteur non trouvé")
        
        # Chercher la localisation existante
        location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
        
        is_new_location = location is None
        previous_lat, previous_lon = None, None
        
        if location:
            # Sauvegarder position précédente pour calcul de distance
            previous_lat, previous_lon = location.latitude, location.longitude
            
            # Mettre à jour
            location.latitude = latitude
            location.longitude = longitude
            location.heading = heading
            location.speed = speed
            location.accuracy = accuracy
            location.last_updated = datetime.utcnow()
        else:
            # Créer nouvelle localisation
            location = DriverLocation(
                id=f"loc_{driver_id}",
                driver_id=driver_id,
                latitude=latitude,
                longitude=longitude,
                heading=heading,
                speed=speed,
                accuracy=accuracy
            )
            self.db.add(location)
        
        self.db.commit()
        self.db.refresh(location)
        
        return location
    
    def get_driver_location(self, driver_id: str) -> Optional[DriverLocation]:
        """Récupère la position d'un conducteur."""
        return self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
    
    def set_driver_availability(self, driver_id: str, is_available: bool) -> DriverLocation:
        """Définit la disponibilité d'un conducteur."""
        location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
        
        if not location:
            raise ValueError("Position du conducteur non trouvée")
        
        location.is_available = is_available
        location.last_updated = datetime.utcnow()
        
        self.db.commit()
        self.db.refresh(location)
        
        return location
    
    def set_driver_online_status(self, driver_id: str, is_online: bool) -> DriverLocation:
        """Définit le statut en ligne d'un conducteur."""
        location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
        
        if not location:
            raise ValueError("Position du conducteur non trouvée")
        
        location.is_online = is_online
        location.last_updated = datetime.utcnow()
        
        # Si hors ligne, marquer comme non disponible
        if not is_online:
            location.is_available = False
        
        self.db.commit()
        self.db.refresh(location)
        
        return location
    
    def find_nearby_drivers(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10,
        limit: int = 20
    ) -> List[Tuple[DriverLocation, float]]:
        """Trouve les conducteurs à proximité."""
        
        # Requête approximative pour optimiser
        lat_range = radius_km / 111.0  # 1 degré ≈ 111 km
        lon_range = radius_km / (111.0 * abs(latitude / 90.0))  # Ajustement longitude
        
        nearby_locations = self.db.query(DriverLocation).filter(
            and_(
                DriverLocation.is_online == True,
                DriverLocation.is_available == True,
                DriverLocation.latitude.between(latitude - lat_range, latitude + lat_range),
                DriverLocation.longitude.between(longitude - lon_range, longitude + lon_range),
                # Exclure les positions trop anciennes (plus de 5 minutes)
                DriverLocation.last_updated > datetime.utcnow() - timedelta(minutes=5)
            )
        ).limit(limit * 2).all()  # Prendre plus pour filtrer ensuite
        
        # Calcul précis des distances
        results = []
        target_location = (latitude, longitude)
        
        for location in nearby_locations:
            driver_location = (location.latitude, location.longitude)
            distance = geodesic(target_location, driver_location).kilometers
            
            if distance <= radius_km:
                results.append((location, distance))
        
        # Trier par distance et limiter
        results.sort(key=lambda x: x[1])
        return results[:limit]
    
    def record_trip_location(
        self,
        trip_id: str,
        latitude: float,
        longitude: float,
        heading: Optional[float] = None,
        speed: Optional[float] = None
    ) -> TripLocation:
        """Enregistre une position pendant une course."""
        
        trip_location = TripLocation(
            id=f"trip_loc_{trip_id}_{int(datetime.utcnow().timestamp())}",
            trip_id=trip_id,
            latitude=latitude,
            longitude=longitude,
            heading=heading,
            speed=speed
        )
        
        self.db.add(trip_location)
        self.db.commit()
        self.db.refresh(trip_location)
        
        return trip_location
    
    def get_trip_route(self, trip_id: str) -> List[TripLocation]:
        """Récupère l'itinéraire d'une course."""
        return self.db.query(TripLocation).filter(
            TripLocation.trip_id == trip_id
        ).order_by(TripLocation.recorded_at).all()
    
    def calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calcule la distance entre deux points en kilomètres."""
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        return geodesic(point1, point2).kilometers
    
    def get_driver_statistics(self, driver_id: str) -> dict:
        """Statistiques de localisation d'un conducteur."""
        location = self.get_driver_location(driver_id)
        
        if not location:
            return {
                "has_location": False,
                "is_online": False,
                "is_available": False,
                "last_update": None
            }
        
        # Calculer le temps depuis la dernière mise à jour
        time_since_update = datetime.utcnow() - location.last_updated
        minutes_since_update = int(time_since_update.total_seconds() / 60)
        
        return {
            "has_location": True,
            "is_online": location.is_online,
            "is_available": location.is_available,
            "last_update": location.last_updated,
            "minutes_since_update": minutes_since_update,
            "accuracy": location.accuracy,
            "speed": location.speed
        }
    
    def cleanup_old_locations(self, hours_old: int = 24) -> int:
        """Nettoie les anciennes positions de course."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        
        deleted_count = self.db.query(TripLocation).filter(
            TripLocation.recorded_at < cutoff_time
        ).delete()
        
        self.db.commit()
        
        return deleted_count


        
        # Métriques de mise à jour de position
        if is_new_location:
            self.collector.record_metric(
                name="location_driver_first_position",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={"driver_status": driver.status or "unknown"},
                user_id=driver_id,
                description="Première position enregistrée pour un conducteur"
            )
        else:
            # Calculer la distance parcourue
            if previous_lat and previous_lon:
                distance_moved = geodesic(
                    (previous_lat, previous_lon),
                    (latitude, longitude)
                ).kilometers
                
                self.collector.record_metric(
                    name="location_driver_distance_moved",
                    value=distance_moved,
                    metric_type=MetricType.GAUGE,
                    category=MetricCategory.BUSINESS,
                    labels={
                        "movement_category": self._get_movement_category(distance_moved),
                        "driver_status": driver.status or "unknown"
                    },
                    user_id=driver_id,
                    description="Distance parcourue depuis la dernière position"
                )
        
        # Métriques de vitesse si disponible
        if speed is not None:
            self.collector.record_metric(
                name="location_driver_speed",
                value=speed,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={
                    "speed_category": self._get_speed_category(speed),
                    "driver_status": driver.status or "unknown"
                },
                user_id=driver_id,
                description="Vitesse du conducteur"
            )
        
        # Métriques de précision GPS
        if accuracy is not None:
            self.collector.record_metric(
                name="location_gps_accuracy",
                value=accuracy,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.TECHNICAL,
                labels={"accuracy_level": self._get_accuracy_level(accuracy)},
                user_id=driver_id,
                description="Précision GPS de la position"
            )
        
        self.db.commit()
        self.db.refresh(location)
        
        return location
    
    def _get_movement_category(self, distance_km: float) -> str:
        """Catégorise le mouvement pour les métriques."""
        if distance_km < 0.01:  # 10 mètres
            return "stationary"
        elif distance_km < 0.1:  # 100 mètres
            return "minimal"
        elif distance_km < 0.5:  # 500 mètres
            return "local"
        elif distance_km < 2.0:  # 2 km
            return "moderate"
        else:
            return "significant"
    
    def _get_speed_category(self, speed_kmh: float) -> str:
        """Catégorise la vitesse pour les métriques."""
        if speed_kmh < 5:
            return "stationary"
        elif speed_kmh < 20:
            return "slow"
        elif speed_kmh < 50:
            return "normal"
        elif speed_kmh < 80:
            return "fast"
        else:
            return "very_fast"
    
    def _get_accuracy_level(self, accuracy_meters: float) -> str:
        """Catégorise la précision GPS."""
        if accuracy_meters < 5:
            return "excellent"
        elif accuracy_meters < 15:
            return "good"
        elif accuracy_meters < 50:
            return "fair"
        else:
            return "poor"
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def get_driver_location(self, driver_id: str) -> Optional[DriverLocation]:
        """Récupère la position d'un conducteur."""
        location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
        
        if location:
            # Métrique de récupération de position
            time_since_update = (datetime.utcnow() - location.last_updated).total_seconds()
            self.collector.record_metric(
                name="location_data_freshness",
                value=time_since_update,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.TECHNICAL,
                labels={
                    "freshness_level": self._get_freshness_level(time_since_update),
                    "is_online": str(location.is_online),
                    "is_available": str(location.is_available)
                },
                user_id=driver_id,
                description="Fraîcheur des données de position"
            )
        
        return location
    
    def _get_freshness_level(self, seconds: float) -> str:
        """Catégorise la fraîcheur des données."""
        if seconds < 30:
            return "very_fresh"
        elif seconds < 120:  # 2 minutes
            return "fresh"
        elif seconds < 300:  # 5 minutes
            return "acceptable"
        elif seconds < 900:  # 15 minutes
            return "stale"
        else:
            return "very_stale"
    
    @monitor_business_operation("driver_availability_change", "location")
    def set_driver_availability(self, driver_id: str, is_available: bool) -> DriverLocation:
        """Définit la disponibilité d'un conducteur avec métriques."""
        location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
        
        if not location:
            self.collector.record_metric(
                name="location_availability_change_no_location",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                user_id=driver_id,
                description="Tentative de changement de disponibilité sans position"
            )
            raise ValueError("Position du conducteur non trouvée")
        
        old_availability = location.is_available
        location.is_available = is_available
        location.last_updated = datetime.utcnow()
        
        # Métrique de changement de disponibilité
        if old_availability != is_available:
            self.collector.record_metric(
                name="location_driver_availability_changed",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={
                    "from_status": "available" if old_availability else "unavailable",
                    "to_status": "available" if is_available else "unavailable",
                    "is_online": str(location.is_online)
                },
                user_id=driver_id,
                description="Changement de disponibilité du conducteur"
            )
        
        self.db.commit()
        self.db.refresh(location)
        
        return location
    
    @monitor_business_operation("driver_online_status_change", "location")
    def set_driver_online_status(self, driver_id: str, is_online: bool) -> DriverLocation:
        """Définit le statut en ligne d'un conducteur avec métriques."""
        location = self.db.query(DriverLocation).filter(
            DriverLocation.driver_id == driver_id
        ).first()
        
        if not location:
            self.collector.record_metric(
                name="location_online_status_change_no_location",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                user_id=driver_id,
                description="Tentative de changement de statut en ligne sans position"
            )
            raise ValueError("Position du conducteur non trouvée")
        
        old_online_status = location.is_online
        location.is_online = is_online
        location.last_updated = datetime.utcnow()
        
        # Si hors ligne, marquer comme non disponible
        if not is_online:
            location.is_available = False
        
        # Métrique de changement de statut en ligne
        if old_online_status != is_online:
            self.collector.record_metric(
                name="location_driver_online_status_changed",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={
                    "from_status": "online" if old_online_status else "offline",
                    "to_status": "online" if is_online else "offline"
                },
                user_id=driver_id,
                description="Changement de statut en ligne du conducteur"
            )
        
        self.db.commit()
        self.db.refresh(location)
        
        return location
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def find_nearby_drivers(
        self,
        latitude: float,
        longitude: float,
        radius_km: float = 10,
        limit: int = 20
    ) -> List[Tuple[DriverLocation, float]]:
        """Trouve les conducteurs à proximité avec métriques."""
        
        # Requête approximative pour optimiser
        lat_range = radius_km / 111.0  # 1 degré ≈ 111 km
        lon_range = radius_km / (111.0 * abs(latitude / 90.0))  # Ajustement longitude
        
        nearby_locations = self.db.query(DriverLocation).filter(
            and_(
                DriverLocation.is_online == True,
                DriverLocation.is_available == True,
                DriverLocation.latitude.between(latitude - lat_range, latitude + lat_range),
                DriverLocation.longitude.between(longitude - lon_range, longitude + lon_range),
                # Exclure les positions trop anciennes (plus de 5 minutes)
                DriverLocation.last_updated > datetime.utcnow() - timedelta(minutes=5)
            )
        ).limit(limit * 2).all()  # Prendre plus pour filtrer ensuite
        
        # Calcul précis des distances
        results = []
        target_location = (latitude, longitude)
        
        for location in nearby_locations:
            driver_location = (location.latitude, location.longitude)
            distance = geodesic(target_location, driver_location).kilometers
            
            if distance <= radius_km:
                results.append((location, distance))
        
        # Trier par distance et limiter
        results.sort(key=lambda x: x[1])
        final_results = results[:limit]
        
        # Métriques de recherche de proximité
        self.collector.record_metric(
            name="location_nearby_drivers_found",
            value=len(final_results),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "radius_km": str(radius_km),
                "availability_level": self._get_availability_level(len(final_results))
            },
            description="Nombre de conducteurs trouvés à proximité"
        )
        
        if final_results:
            avg_distance = sum(distance for _, distance in final_results) / len(final_results)
            self.collector.record_metric(
                name="location_nearby_drivers_avg_distance",
                value=avg_distance,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={"radius_km": str(radius_km)},
                description="Distance moyenne des conducteurs trouvés"
            )
        
        return final_results
    
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
    
    @monitor_business_operation("trip_location_recording", "location")
    def record_trip_location(
        self,
        trip_id: str,
        latitude: float,
        longitude: float,
        heading: Optional[float] = None,
        speed: Optional[float] = None
    ) -> TripLocation:
        """Enregistre une position pendant une course avec métriques."""
        
        trip_location = TripLocation(
            id=f"trip_loc_{trip_id}_{int(datetime.utcnow().timestamp())}",
            trip_id=trip_id,
            latitude=latitude,
            longitude=longitude,
            heading=heading,
            speed=speed
        )
        
        self.db.add(trip_location)
        self.db.commit()
        self.db.refresh(trip_location)
        
        # Métriques d'enregistrement de position de course
        self.collector.record_metric(
            name="location_trip_positions_recorded",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={"trip_id": trip_id},
            description="Position de course enregistrée"
        )
        
        if speed is not None:
            self.collector.record_metric(
                name="location_trip_speed",
                value=speed,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={
                    "speed_category": self._get_speed_category(speed),
                    "trip_id": trip_id
                },
                description="Vitesse pendant la course"
            )
        
        return trip_location
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def get_trip_route(self, trip_id: str) -> List[TripLocation]:
        """Récupère l'itinéraire d'une course avec métriques."""
        locations = self.db.query(TripLocation).filter(
            TripLocation.trip_id == trip_id
        ).order_by(TripLocation.recorded_at).all()
        
        # Métriques d'itinéraire
        self.collector.record_metric(
            name="location_trip_route_points",
            value=len(locations),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "trip_id": trip_id,
                "route_detail_level": self._get_route_detail_level(len(locations))
            },
            description="Nombre de points dans l'itinéraire de course"
        )
        
        return locations
    
    def _get_route_detail_level(self, point_count: int) -> str:
        """Catégorise le niveau de détail de l'itinéraire."""
        if point_count < 5:
            return "minimal"
        elif point_count < 20:
            return "basic"
        elif point_count < 50:
            return "detailed"
        else:
            return "very_detailed"
    
    def calculate_distance(
        self,
        lat1: float, lon1: float,
        lat2: float, lon2: float
    ) -> float:
        """Calcule la distance entre deux points en kilomètres."""
        point1 = (lat1, lon1)
        point2 = (lat2, lon2)
        distance = geodesic(point1, point2).kilometers
        
        # Métrique de calcul de distance
        self.collector.record_metric(
            name="location_distance_calculations",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.TECHNICAL,
            labels={"distance_range": self._get_distance_range(distance)},
            description="Calcul de distance effectué"
        )
        
        return distance
    
    def _get_distance_range(self, distance_km: float) -> str:
        """Catégorise la distance pour les métriques."""
        if distance_km < 0.1:
            return "very_short"
        elif distance_km < 1:
            return "short"
        elif distance_km < 10:
            return "medium"
        elif distance_km < 50:
            return "long"
        else:
            return "very_long"
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def get_driver_statistics(self, driver_id: str) -> dict:
        """Statistiques de localisation d'un conducteur avec métriques."""
        location = self.get_driver_location(driver_id)
        
        if not location:
            self.collector.record_metric(
                name="location_driver_stats_no_location",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                user_id=driver_id,
                description="Demande de statistiques pour conducteur sans position"
            )
            return {
                "has_location": False,
                "is_online": False,
                "is_available": False,
                "last_update": None
            }
        
        # Calculer le temps depuis la dernière mise à jour
        time_since_update = datetime.utcnow() - location.last_updated
        minutes_since_update = int(time_since_update.total_seconds() / 60)
        
        # Métriques de statistiques
        self.collector.record_metric(
            name="location_driver_stats_requested",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={
                "is_online": str(location.is_online),
                "is_available": str(location.is_available),
                "data_freshness": self._get_freshness_level(time_since_update.total_seconds())
            },
            user_id=driver_id,
            description="Statistiques de conducteur demandées"
        )
        
        return {
            "has_location": True,
            "is_online": location.is_online,
            "is_available": location.is_available,
            "last_update": location.last_updated,
            "minutes_since_update": minutes_since_update,
            "accuracy": location.accuracy,
            "speed": location.speed
        }
    
    @monitor_business_operation("location_cleanup", "location")
    def cleanup_old_locations(self, hours_old: int = 24) -> int:
        """Nettoie les anciennes positions de course avec métriques."""
        cutoff_time = datetime.utcnow() - timedelta(hours=hours_old)
        
        deleted_count = self.db.query(TripLocation).filter(
            TripLocation.recorded_at < cutoff_time
        ).delete()
        
        self.db.commit()
        
        # Métrique de nettoyage
        self.collector.record_metric(
            name="location_cleanup_deleted_records",
            value=deleted_count,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.TECHNICAL,
            labels={"hours_old": str(hours_old)},
            description="Enregistrements de position supprimés lors du nettoyage"
        )
        
        return deleted_count

