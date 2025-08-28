"""Routes d'administration"""
from fastapi import APIRouter

router = APIRouter()

@router.get("/stats")
async def get_stats():
    """Statistiques administrateur"""
    return {"stats": {"users": 0, "bookings": 0}}
