"""
API pour les envois multiples de notifications Firebase avec tests synchrones.
"""

from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, Field
import asyncio
import logging

from ...core.database.session import get_db
from ...core.auth.dependencies import get_current_user
from ...models.user import User, UserRole
from ...services.firebase_notification_service import (
    FirebaseNotificationService,
    NotificationType,
    NotificationPriority,
    NotificationResult
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/notifications/bulk", tags=["Notifications Bulk"])

# === MODÈLES PYDANTIC ===

class BulkNotificationRequest(BaseModel):
    """Demande d'envoi de notifications multiples."""
    user_ids: List[str] = Field(..., description="Liste des IDs utilisateurs")
    notification_type: NotificationType = Field(..., description="Type de notification")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Priorité")
    template_vars: Dict[str, Any] = Field(default_factory=dict, description="Variables du template")

class MultipleNotificationsRequest(BaseModel):
    """Demande d'envoi de notifications différentes en lot."""
    notifications: List[Dict[str, Any]] = Field(..., description="Liste des notifications à envoyer")

class RoleBroadcastRequest(BaseModel):
    """Demande de diffusion par rôle."""
    role: UserRole = Field(..., description="Rôle des utilisateurs cibles")
    notification_type: NotificationType = Field(..., description="Type de notification")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Priorité")
    template_vars: Dict[str, Any] = Field(default_factory=dict, description="Variables du template")
    limit: Optional[int] = Field(default=None, description="Limite d'utilisateurs (optionnel)")

class TripBroadcastRequest(BaseModel):
    """Demande de diffusion pour une course."""
    trip_id: str = Field(..., description="ID de la course")
    notification_type: NotificationType = Field(..., description="Type de notification")
    priority: NotificationPriority = Field(default=NotificationPriority.NORMAL, description="Priorité")
    template_vars: Dict[str, Any] = Field(default_factory=dict, description="Variables du template")

class NotificationResponse(BaseModel):
    """Réponse d'envoi de notification."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    tokens_sent: int = 0
    tokens_failed: int = 0

class BulkNotificationResponse(BaseModel):
    """Réponse d'envoi en lot."""
    total_notifications: int
    success_count: int
    error_count: int
    success_rate: float
    total_tokens_sent: int
    total_tokens_failed: int
    error_types: Dict[str, int]
    results: List[NotificationResponse]
    timestamp: str

# === ENDPOINTS SYNCHRONES POUR TESTS ===

@router.post("/send-multiple", response_model=BulkNotificationResponse)
async def send_multiple_notifications(
    request: BulkNotificationRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Envoyer une notification à plusieurs utilisateurs (synchrone pour tests)."""
    
    try:
        # Vérifier les permissions (assouplies pour les tests)
        if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER, UserRole.PASSENGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour les envois multiples"
            )
        
        # Limiter le nombre d'utilisateurs pour les tests
        if len(request.user_ids) > 100:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 100 utilisateurs par envoi de test"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer les notifications
        results = await notification_service.send_notifications_to_multiple_users(
            user_ids=request.user_ids,
            notification_type=request.notification_type,
            priority=request.priority,
            **request.template_vars
        )
        
        # Calculer les statistiques
        stats = notification_service.get_bulk_notification_stats(results)
        
        # Convertir les résultats
        response_results = [
            NotificationResponse(
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                tokens_sent=result.tokens_sent,
                tokens_failed=result.tokens_failed
            )
            for result in results
        ]
        
        return BulkNotificationResponse(
            total_notifications=stats["total_notifications"],
            success_count=stats["success_count"],
            error_count=stats["error_count"],
            success_rate=stats["success_rate"],
            total_tokens_sent=stats["total_tokens_sent"],
            total_tokens_failed=stats["total_tokens_failed"],
            error_types=stats["error_types"],
            results=response_results,
            timestamp=stats["timestamp"]
        )
        
    except HTTPException:
        # Re-lever les HTTPException pour qu'elles soient gérées correctement par FastAPI
        raise
    except Exception as e:
        logger.error(f"Erreur envoi notifications multiples: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'envoi multiple: {str(e)}"
        )

@router.post("/send-batch", response_model=BulkNotificationResponse)
async def send_batch_notifications(
    request: MultipleNotificationsRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Envoyer plusieurs notifications différentes en lot (synchrone pour tests)."""
    
    try:
        # Vérifier les permissions (assouplies pour les tests)
        if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER, UserRole.PASSENGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes pour les envois en lot"
            )
        
        # Limiter le nombre de notifications
        if len(request.notifications) > 50:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum 50 notifications par lot de test"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer les notifications en lot
        results = await notification_service.send_bulk_notifications(
            notifications=request.notifications
        )
        
        # Calculer les statistiques
        stats = notification_service.get_bulk_notification_stats(results)
        
        # Convertir les résultats
        response_results = [
            NotificationResponse(
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                tokens_sent=result.tokens_sent,
                tokens_failed=result.tokens_failed
            )
            for result in results
        ]
        
        return BulkNotificationResponse(
            total_notifications=stats["total_notifications"],
            success_count=stats["success_count"],
            error_count=stats["error_count"],
            success_rate=stats["success_rate"],
            total_tokens_sent=stats["total_tokens_sent"],
            total_tokens_failed=stats["total_tokens_failed"],
            error_types=stats["error_types"],
            results=response_results,
            timestamp=stats["timestamp"]
        )
        
    except HTTPException:
        # Re-lever les HTTPException pour qu'elles soient gérées correctement par FastAPI
        raise
    except Exception as e:
        logger.error(f"Erreur envoi notifications en lot: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de l'envoi en lot: {str(e)}"
        )

@router.post("/broadcast-by-role", response_model=BulkNotificationResponse)
async def broadcast_by_role(
    request: RoleBroadcastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Diffuser une notification à tous les utilisateurs d'un rôle (synchrone pour tests)."""
    
    try:
        # Vérifier les permissions (admin uniquement pour les diffusions)
        if current_user.role != UserRole.ADMIN:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Seuls les administrateurs peuvent faire des diffusions par rôle"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer la diffusion
        results = await notification_service.send_notifications_by_role(
            role=request.role,
            notification_type=request.notification_type,
            priority=request.priority,
            limit=request.limit,
            **request.template_vars
        )
        
        # Calculer les statistiques
        stats = notification_service.get_bulk_notification_stats(results)
        
        # Convertir les résultats
        response_results = [
            NotificationResponse(
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                tokens_sent=result.tokens_sent,
                tokens_failed=result.tokens_failed
            )
            for result in results
        ]
        
        return BulkNotificationResponse(
            total_notifications=stats["total_notifications"],
            success_count=stats["success_count"],
            error_count=stats["error_count"],
            success_rate=stats["success_rate"],
            total_tokens_sent=stats["total_tokens_sent"],
            total_tokens_failed=stats["total_tokens_failed"],
            error_types=stats["error_types"],
            results=response_results,
            timestamp=stats["timestamp"]
        )
        
    except HTTPException:
        # Re-lever les HTTPException pour qu'elles soient gérées correctement par FastAPI
        raise
    except Exception as e:
        logger.error(f"Erreur diffusion par rôle: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la diffusion: {str(e)}"
        )

@router.post("/broadcast-by-trip", response_model=BulkNotificationResponse)
async def broadcast_by_trip(
    request: TripBroadcastRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Diffuser une notification aux participants d'une course (synchrone pour tests)."""
    
    try:
        # Vérifier les permissions
        if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER, UserRole.PASSENGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Envoyer la diffusion
        results = await notification_service.send_notifications_by_trip(
            trip_id=request.trip_id,
            notification_type=request.notification_type,
            priority=request.priority,
            **request.template_vars
        )
        
        # Calculer les statistiques
        stats = notification_service.get_bulk_notification_stats(results)
        
        # Convertir les résultats
        response_results = [
            NotificationResponse(
                success=result.success,
                message_id=result.message_id,
                error=result.error,
                tokens_sent=result.tokens_sent,
                tokens_failed=result.tokens_failed
            )
            for result in results
        ]
        
        return BulkNotificationResponse(
            total_notifications=stats["total_notifications"],
            success_count=stats["success_count"],
            error_count=stats["error_count"],
            success_rate=stats["success_rate"],
            total_tokens_sent=stats["total_tokens_sent"],
            total_tokens_failed=stats["total_tokens_failed"],
            error_types=stats["error_types"],
            results=response_results,
            timestamp=stats["timestamp"]
        )
        
    except HTTPException:
        # Re-lever les HTTPException pour qu'elles soient gérées correctement par FastAPI
        raise
    except Exception as e:
        logger.error(f"Erreur diffusion par course: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la diffusion: {str(e)}"
        )

@router.get("/stats", response_model=Dict[str, Any])
async def get_bulk_notification_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Obtenir les statistiques des envois multiples."""
    
    try:
        # Vérifier les permissions (assouplies pour les tests)
        if current_user.role not in [UserRole.ADMIN, UserRole.DRIVER, UserRole.PASSENGER]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        
        # Créer le service
        notification_service = FirebaseNotificationService(db)
        
        # Retourner les capacités du service
        return {
            "bulk_capabilities": {
                "max_users_per_batch": 100,
                "max_notifications_per_batch": 50,
                "supported_methods": [
                    "send_multiple",
                    "send_batch", 
                    "broadcast_by_role",
                    "broadcast_by_trip"
                ],
                "available_roles": [role.value for role in UserRole],
                "available_types": [ntype.value for ntype in NotificationType],
                "available_priorities": [priority.value for priority in NotificationPriority]
            },
            "service_status": {
                "firebase_initialized": notification_service.is_initialized,
                "mock_mode": notification_service.firebase_config.get("use_mock", True),
                "templates_count": len(notification_service.templates)
            }
        }
        
    except HTTPException:
        # Re-lever les HTTPException pour qu'elles soient gérées correctement par FastAPI
        raise
    except Exception as e:
        logger.error(f"Erreur récupération stats: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur lors de la récupération des stats: {str(e)}"
        )

