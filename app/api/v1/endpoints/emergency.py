"""
Module API pour le système d'urgence SOS.
"""

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class SOSRequest(BaseModel):
    """Modèle pour les demandes SOS."""
    user_id: str = Field(..., description="ID de l'utilisateur")
    latitude: float = Field(..., description="Latitude de l'urgence")
    longitude: float = Field(..., description="Longitude de l'urgence")
    emergency_type: str = Field(..., description="Type d'urgence (medical, security, accident)")
    message: Optional[str] = Field(None, description="Message d'urgence")
    contact_number: Optional[str] = Field(None, description="Numéro de contact")


class SOSResponse(BaseModel):
    """Modèle pour les réponses SOS."""
    sos_id: str
    status: str
    emergency_services_notified: bool
    estimated_response_time: int
    emergency_contact: str
    timestamp: datetime


async def notify_emergency_services(sos_request: SOSRequest, sos_id: str):
    """Notifie les services d'urgence (tâche en arrière-plan)."""
    try:
        # Simulation de notification aux services d'urgence
        logger.info(f"Services d'urgence notifiés pour SOS {sos_id}")
        logger.info(f"Localisation: {sos_request.latitude}, {sos_request.longitude}")
        logger.info(f"Type d'urgence: {sos_request.emergency_type}")
    except Exception as e:
        logger.error(f"Erreur de notification des services d'urgence: {e}")


@router.post("/emergency/sos", response_model=SOSResponse)
async def trigger_sos(request: SOSRequest, background_tasks: BackgroundTasks):
    """Déclenche un signal SOS d'urgence."""
    try:
        sos_id = str(uuid.uuid4())
        
        # Ajouter la notification en arrière-plan
        background_tasks.add_task(notify_emergency_services, request, sos_id)
        
        # Déterminer le temps de réponse estimé selon le type d'urgence
        response_times = {
            "medical": 8,  # 8 minutes
            "security": 12,  # 12 minutes
            "accident": 10  # 10 minutes
        }
        estimated_time = response_times.get(request.emergency_type, 15)
        
        # Numéro d'urgence selon le type
        emergency_contacts = {
            "medical": "14 (SAMU)",
            "security": "17 (Police)",
            "accident": "14 (SAMU) / 17 (Police)"
        }
        emergency_contact = emergency_contacts.get(request.emergency_type, "14/17")
        
        return SOSResponse(
            sos_id=sos_id,
            status="emergency_activated",
            emergency_services_notified=True,
            estimated_response_time=estimated_time,
            emergency_contact=emergency_contact,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Erreur lors du déclenchement SOS: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur SOS: {str(e)}"
        )


@router.get("/emergency/status/{sos_id}")
async def get_sos_status(sos_id: str):
    """Récupère le statut d'un SOS."""
    return {
        "sos_id": sos_id,
        "status": "in_progress",
        "services_dispatched": True,
        "estimated_arrival": "8 minutes",
        "last_update": datetime.now().isoformat(),
        "emergency_contact": "14 (SAMU)"
    }


@router.get("/emergency/history/{user_id}")
async def get_sos_history(user_id: str):
    """Récupère l'historique SOS d'un utilisateur."""
    return {
        "user_id": user_id,
        "total_sos_calls": 2,
        "history": [
            {
                "sos_id": "sos_001",
                "date": "2024-08-01T10:30:00Z",
                "type": "medical",
                "status": "resolved",
                "response_time": "7 minutes"
            },
            {
                "sos_id": "sos_002",
                "date": "2024-07-15T15:45:00Z",
                "type": "accident",
                "status": "resolved",
                "response_time": "9 minutes"
            }
        ]
    }

