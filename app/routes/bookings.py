"""Routes pour la gestion des réservations"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_bookings():
    """Liste toutes les réservations"""
    return {"bookings": []}

@router.post("/")
async def create_booking():
    """Crée une nouvelle réservation"""
    return {"message": "Réservation créée"}
