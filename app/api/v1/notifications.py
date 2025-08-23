"""
API pour les notifications Firebase push avec templates personnalisés.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field

from ...core.database.session import get_db
from ...core.auth.dependencies import get_current_user
from ...models.user import User, UserRole
from ...services.firebase_notification_service import (
    FirebaseNotificationService,
    NotificationType,
    NotificationPriority,
    NotificationResult
)
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications", tags=["Notifications Firebase"])

# === MODÈLES PYDANTIC ===

class NotificationRequest(BaseModel):
    """Demande d'envoi de notification."""
    user_id: str = Field(..., description="ID de l'utilisateur destinataire")
    notification_type: NotificationType = Field(..., description="Type de notification")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Priorité")
    template_vars: Dict[str, Any] = Field(default_factory=dict, description="Variables du template")

class BulkNotificationRequest(BaseModel):
    """Demande d'envoi de notification en masse."""
    user_ids: List[str] = Field(..., description="Liste des IDs utilisateurs")
    notification_type: NotificationType = Field(..., description="Type de notification")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Priorité")
    template_vars: Dict[str, Any] = Field(default_factory=dict, description="Variables du template")

class TripNotificationRequest(BaseModel):
    """Demande de notification liée à une course."""
    trip_id: str = Field(..., description="ID de la course")
    notification_type: NotificationType = Field(..., description="Type de notification")
    target_role: Optional[UserRole] = Field(default=None, description="Rôle cible (optionnel)")

class NotificationResponse(BaseModel):
    """Réponse d'envoi de notification."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    tokens_sent: int = 0
    tokens_failed: int = 0

class NotificationTestResponse(BaseModel):
    """Réponse de test du service."""
    firebase_initialized: bool
    mock_mode: bool
    templates_count: int
    available_types: List[str]
    test_timestamp: str

# === ENDPOINTS ===

@router.post("/send", response_model=NotificationResponse)
async def send_notification(
    request: NotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Envoyer une notification à un utilisateur."""
    
    try:
        # Vérifier les permissions (admin ou conducteur pour certaines notifications)
        if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER, UserRole.PASSENGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour envoyer des notifications"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer la notification en arrière-plan
        def send_notification_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                result = loop.run_until_complete(
                    notification_service.send_notification(
                        user_id=request.user_id,
                        notification_type=request.notification_type,
                        priority=request.priority,
                        **request.template_vars
                    )
                )
                return result
            finally:
                loop.close()
        
        background_tasks.add_task(send_notification_task)
        
        # Retourner une réponse immédiate
        return NotificationResponse(
            success=True,
            message_id="queued",
            tokens_sent=1
        )
        
    except Exception as e:
        logger.error(f"Erreur envoi notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'envoi de la notification: {str(e)}"
        )

@router.post("/send-bulk", response_model=List[NotificationResponse])
async def send_bulk_notification(
    request: BulkNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Envoyer une notification à plusieurs utilisateurs."""
    
    try:
        # Vérifier les permissions (admin uniquement pour les envois en masse)
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls les administrateurs peuvent envoyer des notifications en masse"
            )
        
        # Limiter le nombre d'utilisateurs
        if len(request.user_ids) > 1000:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 1000 utilisateurs par envoi en masse"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer les notifications en arrière-plan
        def send_bulk_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    notification_service.send_bulk_notification(
                        user_ids=request.user_ids,
                        notification_type=request.notification_type,
                        priority=request.priority,
                        **request.template_vars
                    )
                )
                return results
            finally:
                loop.close()
        
        background_tasks.add_task(send_bulk_task)
        
        # Retourner des réponses immédiates
        responses = [
            NotificationResponse(
                success=True,
                message_id="queued",
                tokens_sent=1
            )
            for _ in request.user_ids
        ]
        
        return responses
        
    except Exception as e:
        logger.error(f"Erreur envoi notifications en masse: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'envoi des notifications: {str(e)}"
        )

@router.post("/send-trip", response_model=List[NotificationResponse])
async def send_trip_notification(
    request: TripNotificationRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Envoyer une notification liée à une course."""
    
    try:
        # Vérifier les permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER, UserRole.PASSENGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer la notification en arrière-plan
        def send_trip_notification_task():
            import asyncio
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            try:
                results = loop.run_until_complete(
                    notification_service.send_trip_notification(
                        trip_id=request.trip_id,
                        notification_type=request.notification_type,
                        target_role=request.target_role
                    )
                )
                return results
            finally:
                loop.close()
        
        background_tasks.add_task(send_trip_notification_task)
        
        # Retourner une réponse immédiate
        return [NotificationResponse(
            success=True,
            message_id="queued",
            tokens_sent=1
        )]
        
    except Exception as e:
        logger.error(f"Erreur notification course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'envoi de la notification: {str(e)}"
        )

@router.get("/templates", response_model=Dict[str, Dict[str, Any]])
async def get_notification_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtenir la liste des templates de notifications disponibles."""
    
    try:
        notification_service = FirebaseNotificationService(db)
        templates = notification_service.get_available_templates()
        
        return templates
        
    except Exception as e:
        logger.error(f"Erreur récupération templates: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des templates: {str(e)}"
        )

@router.get("/types", response_model=List[str])
async def get_notification_types():
    """Obtenir la liste des types de notifications disponibles."""
    
    return [notification_type.value for notification_type in NotificationType]

@router.get("/priorities", response_model=List[str])
async def get_notification_priorities():
    """Obtenir la liste des priorités disponibles."""
    
    return [priority.value for priority in NotificationPriority]

@router.get("/test", response_model=NotificationTestResponse)
async def test_notification_service(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Tester le service de notifications Firebase."""
    
    try:
        notification_service = FirebaseNotificationService(db)
        test_results = await notification_service.test_notification_service()
        
        return NotificationTestResponse(**test_results)
        
    except Exception as e:
        logger.error(f"Erreur test service notifications: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du test du service: {str(e)}"
        )

@router.post("/test-send", response_model=NotificationResponse)
async def test_send_notification(
    notification_type: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Envoyer une notification de test à l'utilisateur actuel."""
    
    try:
        # Convertir la string en enum
        try:
            notification_type_enum = NotificationType(notification_type)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type de notification invalide: {notification_type}"
            )
        
        notification_service = FirebaseNotificationService(db)
        
        # Variables de test
        test_vars = {
            "driver_name": "Jean Dupont",
            "passenger_name": "Marie Martin",
            "destination": "Gare de Lyon",
            "pickup_address": "Place de la République",
            "eta_minutes": "5",
            "trip_amount": "15.50",
            "distance_km": "3.2",
            "duration_minutes": "12",
            "vehicle_info": "Peugeot 308 • AB-123-CD",
            "estimated_earnings": "12.40"
        }
        
        result = await notification_service.send_notification(
            user_id=current_user.id,
            notification_type=notification_type_enum,
            priority=NotificationPriority.NORMAL,
            **test_vars
        )
        
        return NotificationResponse(
            success=result.success,
            message_id=result.message_id,
            error=result.error,
            tokens_sent=result.tokens_sent,
            tokens_failed=result.tokens_failed
        )
        
    except Exception as e:
        logger.error(f"Erreur test envoi notification: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors du test d'envoi: {str(e)}"
        )

