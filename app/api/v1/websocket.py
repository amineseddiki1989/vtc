"""
API WebSocket pour géolocalisation temps réel et communication en direct.
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
from uuid import uuid4

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, ValidationError

from ...core.database.session import get_db
from ...core.auth.websocket_auth import get_current_user_websocket
from ...core.auth.dependencies import get_current_user
from ...models.user import User, UserRole
from ...models.location import DriverLocation
from ...services.location_service import LocationService
from ...services.metrics_service import get_metrics_collector
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/ws", tags=["WebSocket"])

# === GESTIONNAIRE DE CONNEXIONS WEBSOCKET ===

class WebSocketManager:
    """Gestionnaire de connexions WebSocket pour géolocalisation temps réel."""
    
    def __init__(self):
        # Connexions actives par utilisateur
        self.active_connections: Dict[str, WebSocket] = {}
        # Connexions par rôle
        self.drivers: Dict[str, WebSocket] = {}
        self.passengers: Dict[str, WebSocket] = {}
        # Rooms pour courses spécifiques
        self.trip_rooms: Dict[str, List[str]] = {}
        
    async def connect(self, websocket: WebSocket, user_id: str, user_role: UserRole):
        """Connecter un utilisateur."""
        await websocket.accept()
        
        # Déconnecter l'ancienne connexion si elle existe
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].close()
            except:
                pass
        
        # Enregistrer la nouvelle connexion
        self.active_connections[user_id] = websocket
        
        if user_role == UserRole.DRIVER:
            self.drivers[user_id] = websocket
        elif user_role == UserRole.PASSENGER:
            self.passengers[user_id] = websocket
            
        logger.info(f"WebSocket connecté: {user_id} ({user_role})")
        
        # Envoyer confirmation de connexion
        await self.send_personal_message(user_id, {
            "type": "connection_established",
            "user_id": user_id,
            "role": user_role.value,
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
    
    def disconnect(self, user_id: str):
        """Déconnecter un utilisateur."""
        if user_id in self.active_connections:
            del self.active_connections[user_id]
        
        if user_id in self.drivers:
            del self.drivers[user_id]
            
        if user_id in self.passengers:
            del self.passengers[user_id]
            
        # Retirer des rooms de courses
        for trip_id, users in self.trip_rooms.items():
            if user_id in users:
                users.remove(user_id)
                
        logger.info(f"WebSocket déconnecté: {user_id}")
    
    async def send_personal_message(self, user_id: str, message: Dict[str, Any]):
        """Envoyer un message à un utilisateur spécifique."""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_text(json.dumps(message))
                return True
            except Exception as e:
                logger.error(f"Erreur envoi message à {user_id}: {e}")
                self.disconnect(user_id)
                return False
        return False
    
    async def broadcast_to_drivers(self, message: Dict[str, Any], exclude_user: Optional[str] = None):
        """Diffuser un message à tous les conducteurs."""
        disconnected = []
        for driver_id, websocket in self.drivers.items():
            if exclude_user and driver_id == exclude_user:
                continue
            try:
                await websocket.send_text(json.dumps(message))
            except Exception as e:
                logger.error(f"Erreur diffusion à conducteur {driver_id}: {e}")
                disconnected.append(driver_id)
        
        # Nettoyer les connexions fermées
        for driver_id in disconnected:
            self.disconnect(driver_id)
    
    async def broadcast_to_trip(self, trip_id: str, message: Dict[str, Any]):
        """Diffuser un message à tous les participants d'une course."""
        if trip_id not in self.trip_rooms:
            return
            
        disconnected = []
        for user_id in self.trip_rooms[trip_id]:
            if user_id in self.active_connections:
                try:
                    await self.active_connections[user_id].send_text(json.dumps(message))
                except Exception as e:
                    logger.error(f"Erreur diffusion course {trip_id} à {user_id}: {e}")
                    disconnected.append(user_id)
        
        # Nettoyer les connexions fermées
        for user_id in disconnected:
            self.disconnect(user_id)
    
    def join_trip_room(self, trip_id: str, user_id: str):
        """Ajouter un utilisateur à une room de course."""
        if trip_id not in self.trip_rooms:
            self.trip_rooms[trip_id] = []
        
        if user_id not in self.trip_rooms[trip_id]:
            self.trip_rooms[trip_id].append(user_id)
            logger.info(f"Utilisateur {user_id} rejoint la course {trip_id}")
    
    def leave_trip_room(self, trip_id: str, user_id: str):
        """Retirer un utilisateur d'une room de course."""
        if trip_id in self.trip_rooms and user_id in self.trip_rooms[trip_id]:
            self.trip_rooms[trip_id].remove(user_id)
            logger.info(f"Utilisateur {user_id} quitte la course {trip_id}")
    
    def get_connected_drivers_count(self) -> int:
        """Obtenir le nombre de conducteurs connectés."""
        return len(self.drivers)
    
    def get_connected_passengers_count(self) -> int:
        """Obtenir le nombre de passagers connectés."""
        return len(self.passengers)

# Instance globale du gestionnaire
websocket_manager = WebSocketManager()

# === MODÈLES DE MESSAGES ===

class LocationUpdateMessage(BaseModel):
    """Message de mise à jour de position."""
    type: str = "location_update"
    latitude: float
    longitude: float
    heading: Optional[float] = None
    speed: Optional[float] = None
    accuracy: Optional[float] = None
    timestamp: Optional[str] = None

class TripJoinMessage(BaseModel):
    """Message pour rejoindre une course."""
    type: str = "join_trip"
    trip_id: str

class PingMessage(BaseModel):
    """Message de ping pour maintenir la connexion."""
    type: str = "ping"

# === ENDPOINTS WEBSOCKET ===

@router.websocket("/location")
async def websocket_location_endpoint(
    websocket: WebSocket,
    token: str,
    db: Session = Depends(get_db)
):
    """
    Endpoint WebSocket pour géolocalisation temps réel.
    
    Paramètres:
    - token: JWT token d'authentification
    
    Messages supportés:
    - location_update: Mise à jour de position
    - join_trip: Rejoindre une course
    - ping: Maintenir la connexion
    """
    user = None
    user_id = None
    
    try:
        # Authentification WebSocket
        user = await get_current_user_websocket(token, db)
        user_id = user.id
        
        # Connexion WebSocket
        await websocket_manager.connect(websocket, user_id, user.role)
        
        # Services
        location_service = LocationService(db)
        metrics_collector = get_metrics_collector()
        
        # Envoyer les statistiques de connexion
        await websocket_manager.send_personal_message(user_id, {
            "type": "connection_stats",
            "connected_drivers": websocket_manager.get_connected_drivers_count(),
            "connected_passengers": websocket_manager.get_connected_passengers_count(),
            "timestamp": datetime.now(timezone.utc).isoformat()
        })
        
        # Boucle de traitement des messages
        while True:
            try:
                # Recevoir le message
                data = await websocket.receive_text()
                message_data = json.loads(data)
                
                message_type = message_data.get("type")
                
                if message_type == "location_update":
                    # Traiter la mise à jour de position
                    try:
                        location_msg = LocationUpdateMessage(**message_data)
                        
                        if user.role == UserRole.DRIVER:
                            # Mettre à jour la position du conducteur
                            driver_location = location_service.update_driver_location(
                                driver_id=user_id,
                                latitude=location_msg.latitude,
                                longitude=location_msg.longitude,
                                heading=location_msg.heading,
                                speed=location_msg.speed,
                                accuracy=location_msg.accuracy
                            )
                            
                            # Diffuser la position aux passagers connectés
                            broadcast_message = {
                                "type": "driver_location_update",
                                "driver_id": user_id,
                                "latitude": location_msg.latitude,
                                "longitude": location_msg.longitude,
                                "heading": location_msg.heading,
                                "speed": location_msg.speed,
                                "timestamp": datetime.now(timezone.utc).isoformat()
                            }
                            
                            # Envoyer aux passagers connectés
                            for passenger_id in websocket_manager.passengers:
                                await websocket_manager.send_personal_message(passenger_id, broadcast_message)
                            
                            # Métriques
                            metrics_collector.record_metric(
                                name="websocket_location_update",
                                value=1,
                                metric_type="counter",
                                category="realtime",
                                user_id=user_id,
                                description="Mise à jour position conducteur WebSocket"
                            )
                        
                        # Confirmer la réception
                        await websocket_manager.send_personal_message(user_id, {
                            "type": "location_update_ack",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        
                    except ValidationError as e:
                        await websocket_manager.send_personal_message(user_id, {
                            "type": "error",
                            "message": f"Format de message invalide: {e}",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                
                elif message_type == "join_trip":
                    # Rejoindre une course
                    try:
                        trip_msg = TripJoinMessage(**message_data)
                        websocket_manager.join_trip_room(trip_msg.trip_id, user_id)
                        
                        await websocket_manager.send_personal_message(user_id, {
                            "type": "trip_joined",
                            "trip_id": trip_msg.trip_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        
                        # Notifier les autres participants
                        await websocket_manager.broadcast_to_trip(trip_msg.trip_id, {
                            "type": "user_joined_trip",
                            "user_id": user_id,
                            "user_role": user.role.value,
                            "trip_id": trip_msg.trip_id,
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                        
                    except ValidationError as e:
                        await websocket_manager.send_personal_message(user_id, {
                            "type": "error",
                            "message": f"Format de message invalide: {e}",
                            "timestamp": datetime.now(timezone.utc).isoformat()
                        })
                
                elif message_type == "ping":
                    # Répondre au ping
                    await websocket_manager.send_personal_message(user_id, {
                        "type": "pong",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                
                else:
                    # Message non reconnu
                    await websocket_manager.send_personal_message(user_id, {
                        "type": "error",
                        "message": f"Type de message non supporté: {message_type}",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    })
                    
            except json.JSONDecodeError:
                await websocket_manager.send_personal_message(user_id, {
                    "type": "error",
                    "message": "Format JSON invalide",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
            
            except Exception as e:
                logger.error(f"Erreur traitement message WebSocket {user_id}: {e}")
                await websocket_manager.send_personal_message(user_id, {
                    "type": "error",
                    "message": "Erreur interne du serveur",
                    "timestamp": datetime.now(timezone.utc).isoformat()
                })
    
    except WebSocketDisconnect:
        logger.info(f"WebSocket déconnecté: {user_id}")
    
    except Exception as e:
        logger.error(f"Erreur WebSocket {user_id}: {e}")
        try:
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
        except:
            pass
    
    finally:
        if user_id:
            websocket_manager.disconnect(user_id)

# === ENDPOINTS HTTP POUR GESTION WEBSOCKET ===

@router.get("/stats")
async def get_websocket_stats():
    """Obtenir les statistiques des connexions WebSocket (accessible pour monitoring)."""
    return {
        "connected_drivers": websocket_manager.get_connected_drivers_count(),
        "connected_passengers": websocket_manager.get_connected_passengers_count(),
        "total_connections": len(websocket_manager.active_connections),
        "active_trips": len(websocket_manager.trip_rooms),
        "timestamp": datetime.now(timezone.utc).isoformat()
    }

@router.post("/broadcast/drivers")
async def broadcast_to_drivers(
    message: Dict[str, Any],
    current_user: User = Depends(get_current_user)
):
    """Diffuser un message à tous les conducteurs connectés (admin seulement)."""
    if current_user.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Accès réservé aux administrateurs"
        )
    
    await websocket_manager.broadcast_to_drivers({
        **message,
        "from_admin": True,
        "timestamp": datetime.now(timezone.utc).isoformat()
    })
    
    return {
        "message": "Message diffusé aux conducteurs",
        "recipients_count": websocket_manager.get_connected_drivers_count()
    }

