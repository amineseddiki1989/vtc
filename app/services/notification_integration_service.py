"""
Service d'intégration entre notifications Firebase et WebSocket temps réel.
Gestion automatique des notifications selon les événements VTC.
"""

import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from enum import Enum
import logging

from sqlalchemy.orm import Session

from ..models.user import User, UserRole
from ..models.trip import Trip, TripStatus
from ..models.location import DriverLocation
from ..services.firebase_notification_service import (
    FirebaseNotificationService,
    NotificationType,
    NotificationPriority
)
from ..services.websocket_service import WebSocketManager
from ..services.metrics_service import get_metrics_collector

logger = logging.getLogger(__name__)

class TripEvent(str, Enum):
    """Événements de course déclenchant des notifications."""
    TRIP_REQUESTED = "trip_requested"
    DRIVER_ASSIGNED = "driver_assigned"
    DRIVER_ARRIVING = "driver_arriving"
    DRIVER_ARRIVED = "driver_arrived"
    TRIP_STARTED = "trip_started"
    TRIP_COMPLETED = "trip_completed"
    TRIP_CANCELLED = "trip_cancelled"
    PAYMENT_PROCESSED = "payment_processed"
    EMERGENCY_TRIGGERED = "emergency_triggered"

class NotificationIntegrationService:
    """Service d'intégration notifications Firebase + WebSocket."""
    
    def __init__(self, db: Session):
        self.db = db
        self.firebase_service = FirebaseNotificationService(db)
        self.websocket_manager = WebSocketManager()
        self.metrics_collector = get_metrics_collector()
        
        # Mapping événements -> notifications
        self.event_notification_mapping = {
            TripEvent.TRIP_REQUESTED: {
                UserRole.PASSENGER: NotificationType.TRIP_REQUEST_SENT,
                UserRole.DRIVER: NotificationType.NEW_TRIP_REQUEST
            },
            TripEvent.DRIVER_ASSIGNED: {
                UserRole.PASSENGER: NotificationType.DRIVER_FOUND,
                UserRole.DRIVER: NotificationType.TRIP_ACCEPTED
            },
            TripEvent.DRIVER_ARRIVING: {
                UserRole.PASSENGER: NotificationType.DRIVER_ARRIVING
            },
            TripEvent.DRIVER_ARRIVED: {
                UserRole.PASSENGER: NotificationType.DRIVER_ARRIVED
            },
            TripEvent.TRIP_STARTED: {
                UserRole.PASSENGER: NotificationType.TRIP_STARTED,
                UserRole.DRIVER: NotificationType.TRIP_STARTED
            },
            TripEvent.TRIP_COMPLETED: {
                UserRole.PASSENGER: NotificationType.TRIP_COMPLETED,
                UserRole.DRIVER: NotificationType.TRIP_PAYMENT_RECEIVED
            },
            TripEvent.TRIP_CANCELLED: {
                UserRole.PASSENGER: NotificationType.TRIP_CANCELLED,
                UserRole.DRIVER: NotificationType.TRIP_CANCELLED
            },
            TripEvent.EMERGENCY_TRIGGERED: {
                UserRole.PASSENGER: NotificationType.EMERGENCY_ALERT,
                UserRole.DRIVER: NotificationType.EMERGENCY_ALERT
            }
        }
    
    async def handle_trip_event(
        self,
        trip_id: str,
        event: TripEvent,
        additional_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Gérer un événement de course avec notifications et WebSocket."""
        
        try:
            # Récupérer la course
            trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
            if not trip:
                logger.error(f"Course {trip_id} non trouvée")
                return {"success": False, "error": "Course non trouvée"}
            
            # Préparer les données de l'événement
            event_data = {
                "event": event.value,
                "trip_id": trip_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                **(additional_data or {})
            }
            
            # Envoyer via WebSocket
            websocket_results = await self._send_websocket_updates(trip, event, event_data)
            
            # Envoyer les notifications push
            notification_results = await self._send_push_notifications(trip, event, event_data)
            
            # Enregistrer les métriques
            await self._record_event_metrics(event, trip, websocket_results, notification_results)
            
            return {
                "success": True,
                "event": event.value,
                "trip_id": trip_id,
                "websocket_sent": websocket_results["sent_count"],
                "notifications_sent": notification_results["sent_count"],
                "timestamp": event_data["timestamp"]
            }
            
        except Exception as e:
            logger.error(f"Erreur gestion événement {event.value} pour course {trip_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def _send_websocket_updates(
        self,
        trip: Trip,
        event: TripEvent,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Envoyer les mises à jour WebSocket."""
        
        sent_count = 0
        errors = []
        
        try:
            # Message pour le passager
            if trip.passenger_id:
                passenger_message = {
                    "type": "trip_event",
                    "event": event.value,
                    "trip_id": trip.id,
                    "data": event_data,
                    "role": "passenger"
                }
                
                try:
                    await self.websocket_manager.send_to_user(
                        trip.passenger_id,
                        passenger_message
                    )
                    sent_count += 1
                except Exception as e:
                    errors.append(f"Erreur WebSocket passager: {e}")
            
            # Message pour le conducteur
            if trip.driver_id:
                driver_message = {
                    "type": "trip_event",
                    "event": event.value,
                    "trip_id": trip.id,
                    "data": event_data,
                    "role": "driver"
                }
                
                try:
                    await self.websocket_manager.send_to_user(
                        trip.driver_id,
                        driver_message
                    )
                    sent_count += 1
                except Exception as e:
                    errors.append(f"Erreur WebSocket conducteur: {e}")
            
            # Diffusion dans la room de la course
            room_message = {
                "type": "trip_update",
                "event": event.value,
                "trip_id": trip.id,
                "data": event_data
            }
            
            try:
                await self.websocket_manager.broadcast_to_room(
                    f"trip_{trip.id}",
                    room_message
                )
            except Exception as e:
                errors.append(f"Erreur diffusion room: {e}")
            
            return {
                "sent_count": sent_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Erreur envoi WebSocket: {e}")
            return {
                "sent_count": 0,
                "errors": [str(e)]
            }
    
    async def _send_push_notifications(
        self,
        trip: Trip,
        event: TripEvent,
        event_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Envoyer les notifications push."""
        
        sent_count = 0
        errors = []
        
        try:
            # Récupérer les types de notifications pour cet événement
            notification_types = self.event_notification_mapping.get(event, {})
            
            # Variables du template
            template_vars = self._prepare_template_vars(trip, event_data)
            
            # Notification au passager
            if trip.passenger_id and UserRole.PASSENGER in notification_types:
                try:
                    result = await self.firebase_service.send_notification(
                        user_id=trip.passenger_id,
                        notification_type=notification_types[UserRole.PASSENGER],
                        priority=self._get_event_priority(event),
                        **template_vars
                    )
                    
                    if result.success:
                        sent_count += 1
                    else:
                        errors.append(f"Notification passager échouée: {result.error}")
                        
                except Exception as e:
                    errors.append(f"Erreur notification passager: {e}")
            
            # Notification au conducteur
            if trip.driver_id and UserRole.DRIVER in notification_types:
                try:
                    result = await self.firebase_service.send_notification(
                        user_id=trip.driver_id,
                        notification_type=notification_types[UserRole.DRIVER],
                        priority=self._get_event_priority(event),
                        **template_vars
                    )
                    
                    if result.success:
                        sent_count += 1
                    else:
                        errors.append(f"Notification conducteur échouée: {result.error}")
                        
                except Exception as e:
                    errors.append(f"Erreur notification conducteur: {e}")
            
            return {
                "sent_count": sent_count,
                "errors": errors
            }
            
        except Exception as e:
            logger.error(f"Erreur envoi notifications push: {e}")
            return {
                "sent_count": 0,
                "errors": [str(e)]
            }
    
    def _prepare_template_vars(self, trip: Trip, event_data: Dict[str, Any]) -> Dict[str, Any]:
        """Préparer les variables pour les templates de notifications."""
        
        template_vars = {
            "trip_id": trip.id,
            "pickup_address": getattr(trip, 'pickup_address', 'Adresse de départ'),
            "destination": getattr(trip, 'destination_address', 'Destination'),
            "trip_amount": f"{getattr(trip, 'total_amount', 0):.2f}",
            "distance_km": f"{getattr(trip, 'distance_km', 0):.1f}",
            "duration_minutes": str(getattr(trip, 'duration_minutes', 0)),
            "estimated_earnings": f"{getattr(trip, 'driver_earnings', 0):.2f}"
        }
        
        # Informations conducteur
        if hasattr(trip, 'driver') and trip.driver:
            template_vars.update({
                "driver_name": f"{trip.driver.first_name} {trip.driver.last_name}",
                "vehicle_info": f"{getattr(trip.driver, 'vehicle_model', 'Véhicule')} • {getattr(trip.driver, 'license_plate', 'ABC-123')}"
            })
        
        # Informations passager
        if hasattr(trip, 'passenger') and trip.passenger:
            template_vars.update({
                "passenger_name": f"{trip.passenger.first_name} {trip.passenger.last_name}"
            })
        
        # ETA dynamique depuis les données d'événement
        if "eta_minutes" in event_data:
            template_vars["eta_minutes"] = str(event_data["eta_minutes"])
        
        # Raison d'annulation
        if "cancellation_reason" in event_data:
            template_vars["cancellation_reason"] = event_data["cancellation_reason"]
        
        # Temps d'attente
        if "waiting_minutes" in event_data:
            template_vars["waiting_minutes"] = str(event_data["waiting_minutes"])
        
        return template_vars
    
    def _get_event_priority(self, event: TripEvent) -> NotificationPriority:
        """Déterminer la priorité selon l'événement."""
        
        priority_mapping = {
            TripEvent.EMERGENCY_TRIGGERED: NotificationPriority.CRITICAL,
            TripEvent.DRIVER_ARRIVED: NotificationPriority.HIGH,
            TripEvent.DRIVER_ARRIVING: NotificationPriority.HIGH,
            TripEvent.TRIP_CANCELLED: NotificationPriority.HIGH,
            TripEvent.DRIVER_ASSIGNED: NotificationPriority.HIGH,
            TripEvent.TRIP_COMPLETED: NotificationPriority.NORMAL,
            TripEvent.TRIP_STARTED: NotificationPriority.NORMAL,
            TripEvent.TRIP_REQUESTED: NotificationPriority.NORMAL,
            TripEvent.PAYMENT_PROCESSED: NotificationPriority.LOW
        }
        
        return priority_mapping.get(event, NotificationPriority.NORMAL)
    
    async def _record_event_metrics(
        self,
        event: TripEvent,
        trip: Trip,
        websocket_results: Dict[str, Any],
        notification_results: Dict[str, Any]
    ):
        """Enregistrer les métriques de l'événement."""
        
        try:
            # Métrique de l'événement
            self.metrics_collector.record_metric(
                name="trip_event_processed",
                value=1,
                metric_type="counter",
                category="events",
                labels={
                    "event": event.value,
                    "trip_status": trip.status.value if hasattr(trip, 'status') else "unknown"
                },
                description=f"Événement {event.value} traité"
            )
            
            # Métriques WebSocket
            self.metrics_collector.record_metric(
                name="websocket_messages_sent",
                value=websocket_results["sent_count"],
                metric_type="counter",
                category="websocket",
                labels={"event": event.value},
                description=f"Messages WebSocket envoyés pour {event.value}"
            )
            
            # Métriques notifications
            self.metrics_collector.record_metric(
                name="push_notifications_sent",
                value=notification_results["sent_count"],
                metric_type="counter",
                category="notifications",
                labels={"event": event.value},
                description=f"Notifications push envoyées pour {event.value}"
            )
            
            # Métriques d'erreurs
            total_errors = len(websocket_results.get("errors", [])) + len(notification_results.get("errors", []))
            if total_errors > 0:
                self.metrics_collector.record_metric(
                    name="event_processing_errors",
                    value=total_errors,
                    metric_type="counter",
                    category="errors",
                    labels={"event": event.value},
                    description=f"Erreurs lors du traitement de {event.value}"
                )
                
        except Exception as e:
            logger.error(f"Erreur enregistrement métriques: {e}")
    
    async def handle_driver_location_update(
        self,
        driver_id: str,
        location_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Gérer une mise à jour de position conducteur avec notifications automatiques."""
        
        try:
            # Récupérer les courses actives du conducteur
            active_trips = self.db.query(Trip).filter(
                Trip.driver_id == driver_id,
                Trip.status.in_([TripStatus.ACCEPTED, TripStatus.IN_PROGRESS])
            ).all()
            
            results = []
            
            for trip in active_trips:
                # Calculer l'ETA si le conducteur se dirige vers le passager
                if trip.status == TripStatus.ACCEPTED:
                    # Logique d'ETA (simplifiée)
                    eta_minutes = self._calculate_eta_to_passenger(location_data, trip)
                    
                    # Déclencher notification si ETA < 5 minutes et pas déjà notifié
                    if eta_minutes <= 5:
                        result = await self.handle_trip_event(
                            trip.id,
                            TripEvent.DRIVER_ARRIVING,
                            {"eta_minutes": eta_minutes}
                        )
                        results.append(result)
                
                # Diffuser la position via WebSocket
                location_message = {
                    "type": "driver_location_update",
                    "trip_id": trip.id,
                    "driver_id": driver_id,
                    "location": location_data,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                
                # Envoyer au passager
                if trip.passenger_id:
                    await self.websocket_manager.send_to_user(
                        trip.passenger_id,
                        location_message
                    )
                
                # Diffuser dans la room
                await self.websocket_manager.broadcast_to_room(
                    f"trip_{trip.id}",
                    location_message
                )
            
            return {
                "success": True,
                "driver_id": driver_id,
                "active_trips": len(active_trips),
                "notifications_sent": len(results)
            }
            
        except Exception as e:
            logger.error(f"Erreur mise à jour position conducteur {driver_id}: {e}")
            return {"success": False, "error": str(e)}
    
    def _calculate_eta_to_passenger(
        self,
        driver_location: Dict[str, Any],
        trip: Trip
    ) -> int:
        """Calculer l'ETA du conducteur vers le passager (simplifié)."""
        
        try:
            # Dans une vraie implémentation, utiliser le service ETA
            # Ici, simulation basée sur la distance
            from geopy.distance import geodesic
            
            driver_coords = (driver_location.get("latitude"), driver_location.get("longitude"))
            passenger_coords = (
                getattr(trip, 'pickup_latitude', 48.8566),
                getattr(trip, 'pickup_longitude', 2.3522)
            )
            
            distance_km = geodesic(driver_coords, passenger_coords).kilometers
            
            # Estimation simple: 30 km/h en ville
            eta_minutes = int((distance_km / 30) * 60)
            
            return max(1, eta_minutes)  # Minimum 1 minute
            
        except Exception as e:
            logger.error(f"Erreur calcul ETA: {e}")
            return 10  # Valeur par défaut
    
    async def send_promotional_notification(
        self,
        user_ids: List[str],
        promotion_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Envoyer une notification promotionnelle."""
        
        try:
            results = await self.firebase_service.send_bulk_notification(
                user_ids=user_ids,
                notification_type=NotificationType.PROMOTION_OFFER,
                priority=NotificationPriority.LOW,
                **promotion_data
            )
            
            success_count = sum(1 for r in results if r.success)
            
            # Enregistrer les métriques
            self.metrics_collector.record_metric(
                name="promotional_notifications_sent",
                value=success_count,
                metric_type="counter",
                category="marketing",
                description="Notifications promotionnelles envoyées"
            )
            
            return {
                "success": True,
                "total_sent": len(user_ids),
                "successful": success_count,
                "failed": len(user_ids) - success_count
            }
            
        except Exception as e:
            logger.error(f"Erreur envoi notifications promotionnelles: {e}")
            return {"success": False, "error": str(e)}
    
    async def trigger_emergency_alert(
        self,
        trip_id: str,
        emergency_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Déclencher une alerte d'urgence."""
        
        try:
            # Priorité critique pour les urgences
            result = await self.handle_trip_event(
                trip_id,
                TripEvent.EMERGENCY_TRIGGERED,
                emergency_data
            )
            
            # Notifier aussi les services d'urgence (simulation)
            logger.critical(f"🚨 ALERTE URGENCE - Course {trip_id}: {emergency_data}")
            
            return result
            
        except Exception as e:
            logger.error(f"Erreur alerte urgence: {e}")
            return {"success": False, "error": str(e)}

