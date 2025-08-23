"""
Service de gestion du workflow complet des courses VTC.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
import asyncio
import logging

from ..models.trip import Trip, TripStatus
from ..models.user import User
from ..models.location import DriverLocation
from .driver_matching_service import DriverMatchingService

logger = logging.getLogger(__name__)


class TripWorkflowService:
    """Gestionnaire du workflow complet des courses"""
    
    def __init__(self, db: Session):
        self.db = db
        self.matching_service = DriverMatchingService(db)
        self.acceptance_timeout_seconds = 120  # 2 minutes
        self.arrival_timeout_minutes = 15      # 15 minutes
    
    async def process_trip_creation(self, trip_id: str) -> Dict[str, Any]:
        """
        Traite la création d'une course avec matching automatique
        """
        logger.info(f"Traitement de la création de course {trip_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            logger.error(f"Course {trip_id} introuvable")
            raise ValueError(f"Course {trip_id} introuvable")
        
        # 1. Rechercher et assigner un conducteur
        assignment_result = self.matching_service.assign_driver_to_trip(trip_id)
        
        if assignment_result:
            logger.info(
                f"Conducteur assigné à la course {trip_id}",
                driver_id=assignment_result["driver_id"],
                eta_minutes=assignment_result["eta_minutes"]
            )
            
            # 2. Programmer le timeout d'acceptation
            asyncio.create_task(
                self._handle_acceptance_timeout(trip_id, self.acceptance_timeout_seconds)
            )
            
            return {
                "status": "driver_assigned",
                "message": "Conducteur trouvé et assigné",
                "driver_info": {
                    "driver_id": assignment_result["driver_id"],
                    "driver_name": assignment_result["driver_name"],
                    "driver_phone": assignment_result["driver_phone"],
                    "vehicle_info": assignment_result["vehicle_info"],
                    "eta_minutes": assignment_result["eta_minutes"],
                    "distance_km": assignment_result["distance_km"],
                    "driver_rating": assignment_result["driver_rating"]
                }
            }
        else:
            # Aucun conducteur disponible
            trip.status = TripStatus.NO_DRIVER_AVAILABLE
            self.db.commit()
            
            logger.warning(f"Aucun conducteur disponible pour la course {trip_id}")
            
            return {
                "status": "no_driver_available",
                "message": "Aucun conducteur disponible actuellement",
                "retry_suggested": True,
                "retry_delay_minutes": 5
            }
    
    async def handle_driver_acceptance(self, trip_id: str, driver_id: str) -> Dict[str, Any]:
        """
        Traite l'acceptation d'une course par un conducteur
        """
        logger.info(f"Traitement acceptation course {trip_id} par conducteur {driver_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.driver_id != driver_id:
            raise ValueError("Conducteur non autorisé pour cette course")
        
        if trip.status != TripStatus.DRIVER_ASSIGNED:
            raise ValueError(f"Course non dans le bon statut pour acceptation: {trip.status}")
        
        # Mettre à jour le statut
        trip.status = TripStatus.DRIVER_ACCEPTED
        trip.accepted_at = datetime.utcnow()
        self.db.commit()
        
        # Programmer le timeout d'arrivée
        asyncio.create_task(
            self._handle_arrival_timeout(trip_id, self.arrival_timeout_minutes * 60)
        )
        
        logger.info(f"Course {trip_id} acceptée par conducteur {driver_id}")
        
        return {
            "status": "driver_accepted",
            "message": "Course acceptée avec succès",
            "next_step": "driver_arrival",
            "max_arrival_time_minutes": self.arrival_timeout_minutes
        }
    
    async def handle_driver_decline(self, trip_id: str, driver_id: str, reason: str = None) -> Dict[str, Any]:
        """
        Traite le refus d'une course par un conducteur
        """
        logger.info(f"Traitement refus course {trip_id} par conducteur {driver_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.driver_id != driver_id:
            raise ValueError("Conducteur non autorisé pour cette course")
        
        # Libérer le conducteur
        self.matching_service.release_driver(driver_id)
        
        # Marquer comme refusée
        trip.status = TripStatus.DRIVER_DECLINED
        trip.cancellation_reason = reason or "Refusée par le conducteur"
        self.db.commit()
        
        # Rechercher un nouveau conducteur
        logger.info(f"Recherche d'un nouveau conducteur pour la course {trip_id}")
        reassignment_result = await self.process_trip_creation(trip_id)
        
        return {
            "status": "driver_declined",
            "message": "Course refusée, recherche d'un nouveau conducteur",
            "reassignment_result": reassignment_result
        }
    
    async def handle_driver_arrival(self, trip_id: str, driver_id: str) -> Dict[str, Any]:
        """
        Traite l'arrivée du conducteur au point de prise en charge
        """
        logger.info(f"Traitement arrivée conducteur {driver_id} pour course {trip_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.driver_id != driver_id:
            raise ValueError("Conducteur non autorisé pour cette course")
        
        if trip.status != TripStatus.DRIVER_ACCEPTED:
            raise ValueError(f"Course non dans le bon statut pour arrivée: {trip.status}")
        
        # Mettre à jour le statut
        trip.status = TripStatus.DRIVER_ARRIVED
        trip.arrived_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Conducteur {driver_id} arrivé pour course {trip_id}")
        
        return {
            "status": "driver_arrived",
            "message": "Conducteur arrivé au point de prise en charge",
            "next_step": "trip_start",
            "wait_time_minutes": trip.wait_time_minutes
        }
    
    async def handle_trip_start(self, trip_id: str, driver_id: str) -> Dict[str, Any]:
        """
        Traite le démarrage d'une course
        """
        logger.info(f"Traitement démarrage course {trip_id} par conducteur {driver_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.driver_id != driver_id:
            raise ValueError("Conducteur non autorisé pour cette course")
        
        if trip.status != TripStatus.DRIVER_ARRIVED:
            raise ValueError(f"Course non dans le bon statut pour démarrage: {trip.status}")
        
        # Mettre à jour le statut
        trip.status = TripStatus.IN_PROGRESS
        trip.started_at = datetime.utcnow()
        self.db.commit()
        
        logger.info(f"Course {trip_id} démarrée par conducteur {driver_id}")
        
        return {
            "status": "in_progress",
            "message": "Course démarrée",
            "next_step": "trip_completion",
            "estimated_duration_minutes": trip.duration_minutes
        }
    
    async def handle_trip_completion(self, trip_id: str, driver_id: str, 
                                   final_price: Optional[float] = None) -> Dict[str, Any]:
        """
        Traite la finalisation d'une course
        """
        logger.info(f"Traitement finalisation course {trip_id} par conducteur {driver_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.driver_id != driver_id:
            raise ValueError("Conducteur non autorisé pour cette course")
        
        if trip.status != TripStatus.IN_PROGRESS:
            raise ValueError(f"Course non dans le bon statut pour finalisation: {trip.status}")
        
        # Mettre à jour la course
        trip.status = TripStatus.COMPLETED
        trip.completed_at = datetime.utcnow()
        trip.final_price = final_price or trip.estimated_price
        
        # Libérer le conducteur
        self.matching_service.release_driver(driver_id)
        
        self.db.commit()
        
        logger.info(
            f"Course {trip_id} finalisée",
            final_price=trip.final_price,
            duration_actual=trip.duration_actual_minutes
        )
        
        return {
            "status": "completed",
            "message": "Course terminée avec succès",
            "final_price": trip.final_price,
            "duration_actual_minutes": trip.duration_actual_minutes,
            "next_step": "payment_processing"
        }
    
    async def handle_trip_cancellation(self, trip_id: str, user_id: str, 
                                     reason: str) -> Dict[str, Any]:
        """
        Traite l'annulation d'une course
        """
        logger.info(f"Traitement annulation course {trip_id} par utilisateur {user_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        if not trip.can_be_cancelled_by(user_id):
            raise ValueError("Utilisateur non autorisé à annuler cette course")
        
        # Libérer le conducteur si assigné
        if trip.driver_id:
            self.matching_service.release_driver(trip.driver_id)
        
        # Mettre à jour la course
        trip.status = TripStatus.CANCELLED
        trip.cancelled_at = datetime.utcnow()
        trip.cancellation_reason = reason
        
        self.db.commit()
        
        # Calculer les frais d'annulation si nécessaire
        cancellation_fee = self._calculate_cancellation_fee(trip, user_id)
        
        logger.info(
            f"Course {trip_id} annulée",
            cancelled_by=user_id,
            reason=reason,
            cancellation_fee=cancellation_fee
        )
        
        return {
            "status": "cancelled",
            "message": "Course annulée",
            "cancellation_reason": reason,
            "cancellation_fee": cancellation_fee,
            "cancelled_by": "passenger" if user_id == trip.passenger_id else "driver"
        }
    
    async def _handle_acceptance_timeout(self, trip_id: str, timeout_seconds: int):
        """
        Gère le timeout d'acceptation d'une course
        """
        await asyncio.sleep(timeout_seconds)
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if trip and trip.status == TripStatus.DRIVER_ASSIGNED:
            logger.warning(f"Timeout d'acceptation pour la course {trip_id}")
            
            # Le conducteur n'a pas accepté dans les temps
            await self.handle_driver_decline(
                trip_id, 
                trip.driver_id, 
                "Timeout d'acceptation"
            )
    
    async def _handle_arrival_timeout(self, trip_id: str, timeout_seconds: int):
        """
        Gère le timeout d'arrivée d'un conducteur
        """
        await asyncio.sleep(timeout_seconds)
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if trip and trip.status == TripStatus.DRIVER_ACCEPTED:
            logger.warning(f"Timeout d'arrivée pour la course {trip_id}")
            
            # Le conducteur n'est pas arrivé dans les temps
            await self.handle_trip_cancellation(
                trip_id,
                trip.passenger_id,
                "Conducteur non arrivé dans les temps"
            )
    
    def _calculate_cancellation_fee(self, trip: Trip, cancelled_by_user_id: str) -> float:
        """
        Calcule les frais d'annulation selon les règles business
        """
        # Pas de frais si annulation avant acceptation
        if trip.status in [TripStatus.REQUESTED, TripStatus.DRIVER_ASSIGNED]:
            return 0.0
        
        # Frais pour le passager si annulation après acceptation
        if cancelled_by_user_id == trip.passenger_id and trip.status in [
            TripStatus.DRIVER_ACCEPTED,
            TripStatus.DRIVER_ARRIVED
        ]:
            # Frais fixes de 5€ ou 20% du prix estimé (minimum)
            return min(5.0, trip.estimated_price * 0.2)
        
        # Pas de frais pour les autres cas
        return 0.0
    
    def get_trip_status_summary(self, trip_id: str) -> Dict[str, Any]:
        """
        Retourne un résumé complet du statut d'une course
        """
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        
        if not trip:
            raise ValueError("Course non trouvée")
        
        # Informations de base
        summary = {
            "trip_id": trip.id,
            "status": trip.status.value,
            "is_active": trip.is_active,
            "is_completed": trip.is_completed,
            "passenger_id": trip.passenger_id,
            "driver_id": trip.driver_id,
            "estimated_price": trip.estimated_price,
            "final_price": trip.final_price,
            "payment_status": trip.payment_status.value
        }
        
        # Timestamps
        summary["timestamps"] = {
            "requested_at": trip.requested_at.isoformat() if trip.requested_at else None,
            "assigned_at": trip.assigned_at.isoformat() if trip.assigned_at else None,
            "accepted_at": trip.accepted_at.isoformat() if trip.accepted_at else None,
            "arrived_at": trip.arrived_at.isoformat() if trip.arrived_at else None,
            "started_at": trip.started_at.isoformat() if trip.started_at else None,
            "completed_at": trip.completed_at.isoformat() if trip.completed_at else None,
            "cancelled_at": trip.cancelled_at.isoformat() if trip.cancelled_at else None
        }
        
        # Métriques calculées
        summary["metrics"] = {
            "wait_time_minutes": trip.wait_time_minutes,
            "duration_actual_minutes": trip.duration_actual_minutes,
            "duration_estimated_minutes": trip.duration_minutes
        }
        
        # Prochaines actions possibles
        summary["next_valid_statuses"] = [status.value for status in trip.get_next_valid_statuses()]
        
        return summary
    
    def get_active_trips_count(self) -> Dict[str, int]:
        """
        Retourne le nombre de courses actives par statut
        """
        active_statuses = [
            TripStatus.REQUESTED,
            TripStatus.DRIVER_ASSIGNED,
            TripStatus.DRIVER_ACCEPTED,
            TripStatus.DRIVER_ARRIVED,
            TripStatus.IN_PROGRESS
        ]
        
        counts = {}
        for status in active_statuses:
            count = self.db.query(Trip).filter(Trip.status == status).count()
            counts[status.value] = count
        
        counts["total_active"] = sum(counts.values())
        
        return counts

