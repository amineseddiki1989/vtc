"""Routes pour la gestion des chauffeurs"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/")
async def get_drivers():
    """Liste tous les chauffeurs"""
    return {"drivers": []}

@router.post("/")
async def create_driver():
    """Crée un nouveau chauffeur"""
    return {"message": "Chauffeur créé"}
