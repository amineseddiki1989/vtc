"""
Service WebSocket pour communications temps réel.
Gestion des connexions, rooms et diffusion de messages.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Set, Optional, Any, Callable
from dataclasses import dataclass, asdict
from enum import Enum

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from ..core.cache.redis_manager import redis_manager
from ..core.logging.production_logger import get_logger, log_performance
from ..core.security.advanced_auth import verify_jwt_token

logger = get_logger(__name__)

class MessageType(str, Enum):
    """Types de messages WebSocket."""
    # Authentification
    AUTH = "auth"
    AUTH_SUCCESS = "auth_success"
    AUTH_FAILED = "auth_failed"
    
    # Gestion des connexions
    PING = "ping"
    PONG = "pong"
    DISCONNECT = "disconnect"
    
    # Localisation
    LOCATION_UPDATE = "location_update"
    DRIVER_LOCATION = "driver_location"
    PASSENGER_LOCATION = "passenger_location"
    
    # Courses
    TRIP_REQUEST = "trip_request"
    TRIP_ACCEPTED = "trip_accepted"
    TRIP_CANCELLED = "trip_cancelled"
    TRIP_STATUS_UPDATE = "trip_status_update"
    DRIVER_ARRIVING = "driver_arriving"
    DRIVER_ARRIVED = "driver_arrived"
    TRIP_STARTED = "trip_started"
    TRIP_COMPLETED = "trip_completed"
    
    # Notifications
    NOTIFICATION = "notification"
    SYSTEM_MESSAGE = "system_message"
    CHAT_MESSAGE = "chat_message"
    
    # Erreurs
    ERROR = "error"
    INVALID_MESSAGE = "invalid_message"

@dataclass
class WebSocketMessage:
    """Message WebSocket structuré."""
    type: MessageType
    data: Dict[str, Any]
    timestamp: str = None
    message_id: str = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.now(timezone.utc).isoformat()
        if self.message_id is None:
            self.message_id = str(uuid.uuid4())

@dataclass
class ConnectedClient:
    """Client connecté via WebSocket."""
    websocket: WebSocket
    user_id: str
    user_role: str
    connection_id: str
    connected_at: datetime
    last_ping: datetime
    rooms: Set[str]
    metadata: Dict[str, Any]

class WebSocketManager:
    """Gestionnaire de connexions WebSocket."""
    
    def __init__(self):
        # Connexions actives par connection_id
        self.connections: Dict[str, ConnectedClient] = {}
        
        # Index par user_id pour accès rapide
        self.user_connections: Dict[str, Set[str]] = {}
        
        # Rooms pour diffusion groupée
        self.rooms: Dict[str, Set[str]] = {}
        
        # Handlers de messages
        self.message_handlers: Dict[MessageType, Callable] = {}
        
        # Statistiques
        self.stats = {
            "total_connections": 0,
            "active_connections": 0,
            "messages_sent": 0,
            "messages_received": 0
        }
        
        self._register_default_handlers()
        
        # Tâche de nettoyage périodique
        asyncio.create_task(self._cleanup_task())
    
    def _register_default_handlers(self):
        """Enregistre les handlers par défaut."""
        self.message_handlers = {
            MessageType.AUTH: self._handle_auth,
            MessageType.PING: self._handle_ping,
            MessageType.LOCATION_UPDATE: self._handle_location_update,
            MessageType.DISCONNECT: self._handle_disconnect,
        }
    
    # === GESTION DES CONNEXIONS ===
    
    @log_performance("websocket_connect")
    async def connect(self, websocket: WebSocket, user_id: str = None) -> str:
        """Accepte une nouvelle connexion WebSocket."""
        try:
            await websocket.accept()
            
            connection_id = str(uuid.uuid4())
            now = datetime.now(timezone.utc)
            
            client = ConnectedClient(
                websocket=websocket,
                user_id=user_id or "anonymous",
                user_role="guest",
                connection_id=connection_id,
                connected_at=now,
                last_ping=now,
                rooms=set(),
                metadata={}
            )
            
            # Stocker la connexion
            self.connections[connection_id] = client
            
            # Index par user_id
            if user_id:
                if user_id not in self.user_connections:
                    self.user_connections[user_id] = set()
                self.user_connections[user_id].add(connection_id)
            
            # Mettre à jour les stats
            self.stats["total_connections"] += 1
            self.stats["active_connections"] = len(self.connections)
            
            # Envoyer message de bienvenue
            welcome_message = WebSocketMessage(
                type=MessageType.AUTH,
                data={
                    "connection_id": connection_id,
                    "status": "connected",
                    "message": "Connexion établie. Veuillez vous authentifier."
                }
            )
            
            await self._send_to_connection(connection_id, welcome_message)
            
            logger.info(f"Nouvelle connexion WebSocket: {connection_id} (user: {user_id})")
            
            return connection_id
            
        except Exception as e:
            logger.error(f"Erreur lors de la connexion WebSocket: {e}")
            raise
    
    @log_performance("websocket_disconnect")
    async def disconnect(self, connection_id: str):
        """Ferme une connexion WebSocket."""
        try:
            if connection_id not in self.connections:
                return
            
            client = self.connections[connection_id]
            
            # Retirer des rooms
            for room in client.rooms.copy():
                await self.leave_room(connection_id, room)
            
            # Retirer de l'index user
            if client.user_id in self.user_connections:
                self.user_connections[client.user_id].discard(connection_id)
                if not self.user_connections[client.user_id]:
                    del self.user_connections[client.user_id]
            
            # Fermer la connexion WebSocket
            if client.websocket.client_state == WebSocketState.CONNECTED:
                await client.websocket.close()
            
            # Supprimer de la liste
            del self.connections[connection_id]
            
            # Mettre à jour les stats
            self.stats["active_connections"] = len(self.connections)
            
            logger.info(f"Connexion WebSocket fermée: {connection_id}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la déconnexion: {e}")
    
    # === AUTHENTIFICATION ===
    
    async def authenticate_connection(self, connection_id: str, token: str) -> bool:
        """Authentifie une connexion avec un token JWT."""
        try:
            if connection_id not in self.connections:
                return False
            
            # Vérifier le token
            payload = verify_jwt_token(token)
            if not payload:
                await self._send_auth_failed(connection_id, "Token invalide")
                return False
            
            user_id = payload.get("sub")
            user_role = payload.get("role", "user")
            
            # Mettre à jour les informations du client
            client = self.connections[connection_id]
            old_user_id = client.user_id
            
            client.user_id = user_id
            client.user_role = user_role
            client.metadata.update({
                "authenticated": True,
                "auth_time": datetime.now(timezone.utc).isoformat()
            })
            
            # Mettre à jour l'index user
            if old_user_id in self.user_connections:
                self.user_connections[old_user_id].discard(connection_id)
            
            if user_id not in self.user_connections:
                self.user_connections[user_id] = set()
            self.user_connections[user_id].add(connection_id)
            
            # Rejoindre la room utilisateur
            await self.join_room(connection_id, f"user:{user_id}")
            
            # Rejoindre la room du rôle
            await self.join_room(connection_id, f"role:{user_role}")
            
            # Envoyer confirmation
            success_message = WebSocketMessage(
                type=MessageType.AUTH_SUCCESS,
                data={
                    "user_id": user_id,
                    "role": user_role,
                    "message": "Authentification réussie"
                }
            )
            
            await self._send_to_connection(connection_id, success_message)
            
            logger.info(f"Connexion authentifiée: {connection_id} -> {user_id} ({user_role})")
            
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification: {e}")
            await self._send_auth_failed(connection_id, "Erreur d'authentification")
            return False
    
    async def _send_auth_failed(self, connection_id: str, reason: str):
        """Envoie un message d'échec d'authentification."""
        message = WebSocketMessage(
            type=MessageType.AUTH_FAILED,
            data={"reason": reason}
        )
        await self._send_to_connection(connection_id, message)
    
    # === GESTION DES ROOMS ===
    
    async def join_room(self, connection_id: str, room: str):
        """Fait rejoindre un client à une room."""
        try:
            if connection_id not in self.connections:
                return False
            
            client = self.connections[connection_id]
            client.rooms.add(room)
            
            if room not in self.rooms:
                self.rooms[room] = set()
            self.rooms[room].add(connection_id)
            
            logger.debug(f"Client {connection_id} a rejoint la room {room}")
            return True
            
        except Exception as e:
            logger.error(f"Erreur lors de l'ajout à la room: {e}")
            return False
    
    async def leave_room(self, connection_id: str, room: str):
        """Fait quitter un client d'une room."""
        try:
            if connection_id in self.connections:
                self.connections[connection_id].rooms.discard(room)
            
            if room in self.rooms:
                self.rooms[room].discard(connection_id)
                if not self.rooms[room]:
                    del self.rooms[room]
            
            logger.debug(f"Client {connection_id} a quitté la room {room}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la sortie de room: {e}")
    
    # === ENVOI DE MESSAGES ===
    
    async def _send_to_connection(self, connection_id: str, message: WebSocketMessage):
        """Envoie un message à une connexion spécifique."""
        try:
            if connection_id not in self.connections:
                return False
            
            client = self.connections[connection_id]
            
            if client.websocket.client_state != WebSocketState.CONNECTED:
                await self.disconnect(connection_id)
                return False
            
            message_data = asdict(message)
            await client.websocket.send_text(json.dumps(message_data))
            
            self.stats["messages_sent"] += 1
            return True
            
        except WebSocketDisconnect:
            await self.disconnect(connection_id)
            return False
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de message: {e}")
            await self.disconnect(connection_id)
            return False
    
    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """Envoie un message à toutes les connexions d'un utilisateur."""
        if user_id not in self.user_connections:
            return 0
        
        sent_count = 0
        connections = self.user_connections[user_id].copy()
        
        for connection_id in connections:
            if await self._send_to_connection(connection_id, message):
                sent_count += 1
        
        return sent_count
    
    async def send_to_room(self, room: str, message: WebSocketMessage, exclude: Set[str] = None):
        """Envoie un message à tous les clients d'une room."""
        if room not in self.rooms:
            return 0
        
        exclude = exclude or set()
        sent_count = 0
        connections = self.rooms[room].copy()
        
        for connection_id in connections:
            if connection_id not in exclude:
                if await self._send_to_connection(connection_id, message):
                    sent_count += 1
        
        return sent_count
    
    async def broadcast(self, message: WebSocketMessage, exclude: Set[str] = None):
        """Diffuse un message à toutes les connexions."""
        exclude = exclude or set()
        sent_count = 0
        
        for connection_id in list(self.connections.keys()):
            if connection_id not in exclude:
                if await self._send_to_connection(connection_id, message):
                    sent_count += 1
        
        return sent_count
    
    # === RÉCEPTION DE MESSAGES ===
    
    async def handle_message(self, connection_id: str, raw_message: str):
        """Traite un message reçu d'un client."""
        try:
            self.stats["messages_received"] += 1
            
            # Parser le message
            try:
                message_data = json.loads(raw_message)
                message_type = MessageType(message_data.get("type"))
                data = message_data.get("data", {})
            except (json.JSONDecodeError, ValueError) as e:
                await self._send_error(connection_id, "Format de message invalide")
                return
            
            # Vérifier que la connexion existe
            if connection_id not in self.connections:
                return
            
            # Mettre à jour le ping
            self.connections[connection_id].last_ping = datetime.now(timezone.utc)
            
            # Traiter selon le type
            if message_type in self.message_handlers:
                await self.message_handlers[message_type](connection_id, data)
            else:
                await self._send_error(connection_id, f"Type de message non supporté: {message_type}")
            
        except Exception as e:
            logger.error(f"Erreur lors du traitement de message: {e}")
            await self._send_error(connection_id, "Erreur de traitement")
    
    # === HANDLERS DE MESSAGES ===
    
    async def _handle_auth(self, connection_id: str, data: Dict[str, Any]):
        """Traite une demande d'authentification."""
        token = data.get("token")
        if not token:
            await self._send_auth_failed(connection_id, "Token manquant")
            return
        
        await self.authenticate_connection(connection_id, token)
    
    async def _handle_ping(self, connection_id: str, data: Dict[str, Any]):
        """Traite un ping."""
        pong_message = WebSocketMessage(
            type=MessageType.PONG,
            data={"timestamp": datetime.now(timezone.utc).isoformat()}
        )
        await self._send_to_connection(connection_id, pong_message)
    
    async def _handle_location_update(self, connection_id: str, data: Dict[str, Any]):
        """Traite une mise à jour de localisation."""
        if connection_id not in self.connections:
            return
        
        client = self.connections[connection_id]
        
        # Vérifier que l'utilisateur est authentifié
        if not client.metadata.get("authenticated"):
            await self._send_error(connection_id, "Authentification requise")
            return
        
        latitude = data.get("latitude")
        longitude = data.get("longitude")
        
        if latitude is None or longitude is None:
            await self._send_error(connection_id, "Coordonnées manquantes")
            return
        
        # Diffuser la position selon le rôle
        if client.user_role == "driver":
            # Diffuser aux passagers dans la zone
            location_message = WebSocketMessage(
                type=MessageType.DRIVER_LOCATION,
                data={
                    "driver_id": client.user_id,
                    "latitude": latitude,
                    "longitude": longitude,
                    "heading": data.get("heading"),
                    "speed": data.get("speed")
                }
            )
            
            # Diffuser dans la room des conducteurs
            await self.send_to_room(f"drivers_zone", location_message, {connection_id})
            
        elif client.user_role == "passenger":
            # Diffuser aux conducteurs proches
            location_message = WebSocketMessage(
                type=MessageType.PASSENGER_LOCATION,
                data={
                    "passenger_id": client.user_id,
                    "latitude": latitude,
                    "longitude": longitude
                }
            )
            
            # Diffuser dans la room des passagers
            await self.send_to_room(f"passengers_zone", location_message, {connection_id})
    
    async def _handle_disconnect(self, connection_id: str, data: Dict[str, Any]):
        """Traite une demande de déconnexion."""
        await self.disconnect(connection_id)
    
    async def _send_error(self, connection_id: str, error_message: str):
        """Envoie un message d'erreur."""
        error_msg = WebSocketMessage(
            type=MessageType.ERROR,
            data={"error": error_message}
        )
        await self._send_to_connection(connection_id, error_msg)
    
    # === MÉTHODES SPÉCIALISÉES POUR L'APPLICATION ===
    
    async def notify_trip_request(self, driver_id: str, trip_data: Dict[str, Any]):
        """Notifie un conducteur d'une demande de course."""
        message = WebSocketMessage(
            type=MessageType.TRIP_REQUEST,
            data=trip_data
        )
        return await self.send_to_user(driver_id, message)
    
    async def notify_trip_accepted(self, passenger_id: str, driver_data: Dict[str, Any]):
        """Notifie un passager que sa course a été acceptée."""
        message = WebSocketMessage(
            type=MessageType.TRIP_ACCEPTED,
            data=driver_data
        )
        return await self.send_to_user(passenger_id, message)
    
    async def notify_trip_status(self, user_ids: List[str], status_data: Dict[str, Any]):
        """Notifie les utilisateurs d'un changement de statut de course."""
        message = WebSocketMessage(
            type=MessageType.TRIP_STATUS_UPDATE,
            data=status_data
        )
        
        sent_count = 0
        for user_id in user_ids:
            sent_count += await self.send_to_user(user_id, message)
        
        return sent_count
    
    async def send_notification(self, user_id: str, notification_data: Dict[str, Any]):
        """Envoie une notification à un utilisateur."""
        message = WebSocketMessage(
            type=MessageType.NOTIFICATION,
            data=notification_data
        )
        return await self.send_to_user(user_id, message)
    
    async def send_system_message(self, message_text: str, target_role: str = None):
        """Envoie un message système."""
        message = WebSocketMessage(
            type=MessageType.SYSTEM_MESSAGE,
            data={
                "message": message_text,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
        )
        
        if target_role:
            return await self.send_to_room(f"role:{target_role}", message)
        else:
            return await self.broadcast(message)
    
    # === MAINTENANCE ET STATISTIQUES ===
    
    async def _cleanup_task(self):
        """Tâche de nettoyage périodique."""
        while True:
            try:
                await asyncio.sleep(60)  # Toutes les minutes
                await self._cleanup_stale_connections()
            except Exception as e:
                logger.error(f"Erreur lors du nettoyage: {e}")
    
    async def _cleanup_stale_connections(self):
        """Nettoie les connexions inactives."""
        now = datetime.now(timezone.utc)
        stale_connections = []
        
        for connection_id, client in self.connections.items():
            # Connexions inactives depuis plus de 5 minutes
            if (now - client.last_ping).total_seconds() > 300:
                stale_connections.append(connection_id)
        
        for connection_id in stale_connections:
            logger.info(f"Nettoyage connexion inactive: {connection_id}")
            await self.disconnect(connection_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """Retourne les statistiques du gestionnaire."""
        return {
            **self.stats,
            "rooms_count": len(self.rooms),
            "users_connected": len(self.user_connections),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    def get_room_info(self, room: str) -> Dict[str, Any]:
        """Retourne les informations d'une room."""
        if room not in self.rooms:
            return {"exists": False}
        
        connections = self.rooms[room]
        users = []
        
        for connection_id in connections:
            if connection_id in self.connections:
                client = self.connections[connection_id]
                users.append({
                    "user_id": client.user_id,
                    "role": client.user_role,
                    "connected_at": client.connected_at.isoformat()
                })
        
        return {
            "exists": True,
            "connection_count": len(connections),
            "users": users
        }

# Instance globale
websocket_manager = WebSocketManager()

async def get_websocket_manager() -> WebSocketManager:
    """Dépendance FastAPI pour obtenir le gestionnaire WebSocket."""
    return websocket_manager

