"""
Service de matching intelligent conducteur-passager.
"""

from typing import Optional, List, Tuple, Dict
from sqlalchemy.orm import Session
from sqlalchemy import and_, func, or_
from datetime import datetime, timedelta
import math
import logging

from ..models.user import User
from ..models.location import DriverLocation, Vehicle, Rating
from ..models.trip import Trip, TripStatus

logger = logging.getLogger(__name__)


class DriverMatchingService:
    """Service de matching intelligent conducteur-passager"""
    
    def __init__(self, db: Session):
        self.db = db
        self.max_search_radius_km = 15.0
        self.max_wait_time_minutes = 20
        self.min_driver_rating = 3.5
    
    def find_best_driver(self, 
                        pickup_lat: float, 
                        pickup_lng: float, 
                        vehicle_type: str = "standard") -> Optional[Dict]:
        """
        Trouve le meilleur conducteur disponible selon plusieurs critères :
        - Distance (priorité 40%)
        - Note du conducteur (priorité 30%)
        - Temps d'inactivité (priorité 20%)
        - Historique d'acceptation (priorité 10%)
        """
        
        logger.info(
            "Recherche du meilleur conducteur",
            pickup_lat=pickup_lat,
            pickup_lng=pickup_lng,
            vehicle_type=vehicle_type
        )
        
        # 1. Trouver tous les conducteurs disponibles dans un rayon
        available_drivers = self._get_available_drivers_in_radius(
            pickup_lat, pickup_lng, self.max_search_radius_km, vehicle_type
        )
        
        if not available_drivers:
            logger.warning("Aucun conducteur disponible trouvé")
            return None
        
        logger.info(f"Trouvé {len(available_drivers)} conducteurs disponibles")
        
        # 2. Calculer le score pour chaque conducteur
        scored_drivers = []
        for driver in available_drivers:
            score_data = self._calculate_driver_score(
                driver, pickup_lat, pickup_lng
            )
            scored_drivers.append((driver, score_data))
        
        # 3. Trier par score (meilleur score = plus petit nombre)
        scored_drivers.sort(key=lambda x: x[1]["total_score"])
        
        # 4. Retourner le meilleur conducteur
        best_driver, best_score_data = scored_drivers[0]
        
        result = {
            "driver": best_driver,
            "distance_km": best_score_data["distance_km"],
            "eta_minutes": best_score_data["eta_minutes"],
            "driver_rating": best_score_data["driver_rating"],
            "score": best_score_data["total_score"],
            "score_breakdown": {
                "distance_score": best_score_data["distance_score"],
                "rating_score": best_score_data["rating_score"],
                "idle_score": best_score_data["idle_score"],
                "acceptance_score": best_score_data["acceptance_score"]
            }
        }
        
        logger.info(
            "Meilleur conducteur sélectionné",
            driver_id=best_driver.id,
            distance_km=result["distance_km"],
            eta_minutes=result["eta_minutes"],
            total_score=result["score"]
        )
        
        return result
    
    def assign_driver_to_trip(self, trip_id: str) -> Optional[Dict]:
        """Assigne automatiquement le meilleur conducteur à une course"""
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            logger.error(f"Course {trip_id} introuvable")
            return None
        
        # Trouver le meilleur conducteur
        best_match = self.find_best_driver(
            trip.pickup_latitude,
            trip.pickup_longitude,
            trip.vehicle_type
        )
        
        if not best_match:
            logger.warning(f"Aucun conducteur disponible pour la course {trip_id}")
            return None
        
        # Assigner le conducteur
        selected_driver = best_match["driver"]
        
        try:
            # Mettre à jour la course
            trip.driver_id = selected_driver.id
            trip.status = TripStatus.DRIVER_ASSIGNED
            trip.assigned_at = datetime.utcnow()
            
            # Marquer le conducteur comme occupé
            if selected_driver.location:
                selected_driver.location.is_available = False
                selected_driver.location.current_trip_id = trip_id
            
            self.db.commit()
            
            logger.info(
                "Conducteur assigné avec succès",
                trip_id=trip_id,
                driver_id=selected_driver.id,
                eta_minutes=best_match["eta_minutes"]
            )
            
            return {
                "driver_id": selected_driver.id,
                "driver_name": f"{selected_driver.first_name} {selected_driver.last_name}",
                "driver_phone": selected_driver.phone,
                "vehicle_info": self._get_vehicle_info(selected_driver),
                "eta_minutes": best_match["eta_minutes"],
                "distance_km": best_match["distance_km"],
                "driver_rating": best_match["driver_rating"]
            }
            
        except Exception as e:
            self.db.rollback()
            logger.error(
                "Erreur lors de l'assignation du conducteur",
                trip_id=trip_id,
                driver_id=selected_driver.id,
                error=str(e)
            )
            return None
    
    def _get_available_drivers_in_radius(self, 
                                       lat: float, 
                                       lng: float, 
                                       radius_km: float,
                                       vehicle_type: str) -> List[User]:
        """Récupère les conducteurs disponibles dans un rayon donné"""
        
        # Calcul approximatif des limites géographiques pour optimiser la requête
        lat_delta = radius_km / 111.0  # 1 degré ≈ 111 km
        lng_delta = radius_km / (111.0 * math.cos(math.radians(lat)))
        
        min_lat = lat - lat_delta
        max_lat = lat + lat_delta
        min_lng = lng - lng_delta
        max_lng = lng + lng_delta
        
        # Requête optimisée avec filtres géographiques
        drivers = self.db.query(User).join(DriverLocation).join(Vehicle).filter(
            and_(
                User.role == "driver",
                User.status == "active",
                DriverLocation.is_available == True,
                DriverLocation.is_online == True,
                DriverLocation.latitude.between(min_lat, max_lat),
                DriverLocation.longitude.between(min_lng, max_lng),
                Vehicle.vehicle_type == vehicle_type,
                Vehicle.status == "active",
                # Exclure les conducteurs avec une note trop basse
                or_(
                    ~User.id.in_(
                        self.db.query(Rating.driver_id).filter(
                            Rating.driver_rating < self.min_driver_rating
                        ).subquery()
                    ),
                    ~User.id.in_(self.db.query(Rating.driver_id))  # Nouveaux conducteurs
                )
            )
        ).all()
        
        # Filtrage précis par distance
        nearby_drivers = []
        for driver in drivers:
            if driver.location:
                distance = self._calculate_distance(
                    lat, lng,
                    driver.location.latitude,
                    driver.location.longitude
                )
                if distance <= radius_km:
                    nearby_drivers.append(driver)
        
        return nearby_drivers
    
    def _calculate_driver_score(self, driver: User, pickup_lat: float, pickup_lng: float) -> Dict:
        """
        Calcule un score pour le conducteur (plus petit = meilleur)
        Facteurs : distance (40%), note (30%), temps d'inactivité (20%), acceptation (10%)
        """
        
        # Distance (0-15 km → score 0-40)
        distance_km = self._calculate_distance(
            pickup_lat, pickup_lng,
            driver.location.latitude,
            driver.location.longitude
        )
        distance_score = min(distance_km * 2.67, 40)  # 40 points max
        
        # Note du conducteur (1-5 étoiles → score 30-0)
        driver_rating = self._get_driver_rating(driver.id)
        rating_score = max(0, (5 - driver_rating) * 6)  # 30 points max
        
        # Temps depuis la dernière course (0-120 min → score 0-20)
        idle_minutes = self._get_driver_idle_time(driver.id)
        idle_score = min(idle_minutes / 6, 20)  # 20 points max
        
        # Taux d'acceptation (0-100% → score 10-0)
        acceptance_rate = self._get_driver_acceptance_rate(driver.id)
        acceptance_score = max(0, (1 - acceptance_rate) * 10)  # 10 points max
        
        # ETA calculé
        eta_minutes = self._estimate_arrival_time(
            driver.location.latitude,
            driver.location.longitude,
            pickup_lat, pickup_lng
        )
        
        total_score = distance_score + rating_score + idle_score + acceptance_score
        
        return {
            "distance_km": round(distance_km, 2),
            "eta_minutes": eta_minutes,
            "driver_rating": driver_rating,
            "acceptance_rate": acceptance_rate,
            "idle_minutes": idle_minutes,
            "distance_score": round(distance_score, 2),
            "rating_score": round(rating_score, 2),
            "idle_score": round(idle_score, 2),
            "acceptance_score": round(acceptance_score, 2),
            "total_score": round(total_score, 2)
        }
    
    def _calculate_distance(self, lat1: float, lng1: float, 
                          lat2: float, lng2: float) -> float:
        """Calcule la distance haversine entre deux points GPS"""
        R = 6371  # Rayon de la Terre en km
        
        dlat = math.radians(lat2 - lat1)
        dlng = math.radians(lng2 - lng1)
        
        a = (math.sin(dlat/2) * math.sin(dlat/2) + 
             math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * 
             math.sin(dlng/2) * math.sin(dlng/2))
        
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        return R * c
    
    def _estimate_arrival_time(self, driver_lat: float, driver_lng: float,
                             pickup_lat: float, pickup_lng: float) -> int:
        """Estime le temps d'arrivée en minutes"""
        distance_km = self._calculate_distance(
            driver_lat, driver_lng, pickup_lat, pickup_lng
        )
        
        # Vitesse moyenne en ville selon la distance
        if distance_km <= 2:
            average_speed_kmh = 20  # Circulation dense
        elif distance_km <= 5:
            average_speed_kmh = 30  # Circulation normale
        else:
            average_speed_kmh = 40  # Circulation fluide
        
        time_hours = distance_km / average_speed_kmh
        time_minutes = int(time_hours * 60)
        
        # Ajouter un buffer selon l'heure
        current_hour = datetime.now().hour
        if 7 <= current_hour <= 9 or 17 <= current_hour <= 19:
            # Heures de pointe
            buffer_minutes = min(3 + int(distance_km), 8)
        else:
            buffer_minutes = min(2 + int(distance_km), 5)
        
        return max(time_minutes + buffer_minutes, 1)
    
    def _get_driver_rating(self, driver_id: str) -> float:
        """Récupère la note moyenne du conducteur"""
        avg_rating = self.db.query(func.avg(Rating.driver_rating)).filter(
            Rating.driver_id == driver_id,
            Rating.driver_rating.isnot(None)
        ).scalar()
        
        return float(avg_rating) if avg_rating else 4.5  # Note par défaut pour nouveaux conducteurs
    
    def _get_driver_idle_time(self, driver_id: str) -> int:
        """Récupère le temps d'inactivité en minutes"""
        last_trip = self.db.query(Trip).filter(
            Trip.driver_id == driver_id,
            Trip.status == TripStatus.COMPLETED
        ).order_by(Trip.completed_at.desc()).first()
        
        if last_trip and last_trip.completed_at:
            idle_time = datetime.utcnow() - last_trip.completed_at
            return int(idle_time.total_seconds() / 60)
        
        return 0  # Nouveau conducteur ou pas de course récente
    
    def _get_driver_acceptance_rate(self, driver_id: str) -> float:
        """Calcule le taux d'acceptation du conducteur sur les 30 derniers jours"""
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        
        # Courses assignées
        assigned_trips = self.db.query(Trip).filter(
            Trip.driver_id == driver_id,
            Trip.assigned_at >= thirty_days_ago
        ).count()
        
        # Courses acceptées (non annulées par le conducteur)
        accepted_trips = self.db.query(Trip).filter(
            Trip.driver_id == driver_id,
            Trip.assigned_at >= thirty_days_ago,
            Trip.status != TripStatus.DRIVER_DECLINED
        ).count()
        
        if assigned_trips == 0:
            return 0.9  # Taux par défaut pour nouveaux conducteurs
        
        return accepted_trips / assigned_trips
    
    def _get_vehicle_info(self, driver: User) -> str:
        """Récupère les informations du véhicule du conducteur"""
        if driver.vehicles:
            vehicle = driver.vehicles[0]  # Premier véhicule actif
            return f"{vehicle.make} {vehicle.model} {vehicle.color} - {vehicle.license_plate}"
        return "Véhicule non renseigné"
    
    def release_driver(self, driver_id: str) -> bool:
        """Libère un conducteur après une course"""
        try:
            driver = self.db.query(User).filter(User.id == driver_id).first()
            if driver and driver.location:
                driver.location.is_available = True
                driver.location.current_trip_id = None
                self.db.commit()
                
                logger.info(f"Conducteur {driver_id} libéré avec succès")
                return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"Erreur lors de la libération du conducteur {driver_id}: {str(e)}")
        
        return False
    
    def get_matching_stats(self, pickup_lat: float, pickup_lng: float, 
                          vehicle_type: str = "standard") -> Dict:
        """Retourne des statistiques sur le matching dans une zone"""
        
        available_drivers = self._get_available_drivers_in_radius(
            pickup_lat, pickup_lng, self.max_search_radius_km, vehicle_type
        )
        
        if not available_drivers:
            return {
                "available_drivers": 0,
                "estimated_wait_time": None,
                "average_rating": None,
                "coverage_radius_km": self.max_search_radius_km
            }
        
        # Calculer les statistiques
        ratings = [self._get_driver_rating(d.id) for d in available_drivers]
        distances = [
            self._calculate_distance(
                pickup_lat, pickup_lng,
                d.location.latitude, d.location.longitude
            ) for d in available_drivers
        ]
        
        closest_distance = min(distances)
        estimated_wait = self._estimate_arrival_time(
            available_drivers[distances.index(closest_distance)].location.latitude,
            available_drivers[distances.index(closest_distance)].location.longitude,
            pickup_lat, pickup_lng
        )
        
        return {
            "available_drivers": len(available_drivers),
            "estimated_wait_time": estimated_wait,
            "average_rating": round(sum(ratings) / len(ratings), 2),
            "closest_distance_km": round(closest_distance, 2),
            "coverage_radius_km": self.max_search_radius_km
        }

