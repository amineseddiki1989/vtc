"""Routes pour la gestion des véhicules"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_vehicles():
    """Liste tous les véhicules"""
    return {"vehicles": []}

@router.post("/")
async def create_vehicle():
    """Crée un nouveau véhicule"""
    return {"message": "Véhicule créé"}
