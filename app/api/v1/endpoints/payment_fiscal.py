"""
Module API pour les paiements avec calculs fiscaux intégrés.
"""

from fastapi import APIRouter, HTTPException, status, Depends
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any
from decimal import Decimal
from datetime import datetime
import uuid
import logging

logger = logging.getLogger(__name__)

router = APIRouter()


class FiscalPaymentRequest(BaseModel):
    """Modèle pour les demandes de paiement avec calcul fiscal."""
    base_amount: Decimal = Field(..., description="Montant de base en DZD")
    service_type: str = Field(..., description="Type de service")
    distance_km: float = Field(..., description="Distance en km")
    duration_minutes: int = Field(..., description="Durée en minutes")
    region: str = Field(default="algiers", description="Région")
    payment_method: str = Field(..., description="Méthode de paiement")
    trip_id: str = Field(..., description="ID du trajet")
    customer_id: str = Field(..., description="ID du client")


class FiscalPaymentResponse(BaseModel):
    """Modèle pour les réponses de paiement fiscal."""
    payment_id: str
    transaction_id: str
    fiscal_calculation: Dict[str, Any]
    payment_status: str
    total_amount: Decimal
    timestamp: datetime


@router.post("/process-with-fiscal", response_model=FiscalPaymentResponse)
async def process_fiscal_payment(request: FiscalPaymentRequest):
    """Traite un paiement avec calculs fiscaux automatiques."""
    try:
        # Calcul fiscal automatique
        tva_rate = 0.19
        tva_amount = request.base_amount * Decimal(str(tva_rate))
        
        municipal_rates = {"algiers": 0.02, "oran": 0.015, "default": 0.01}
        municipal_rate = municipal_rates.get(request.region, municipal_rates["default"])
        municipal_tax = request.base_amount * Decimal(str(municipal_rate))
        
        transport_tax_rate = 0.005 if request.distance_km > 10 else 0.003
        transport_tax = request.base_amount * Decimal(str(transport_tax_rate))
        
        total_amount = request.base_amount + tva_amount + municipal_tax + transport_tax
        
        # Génération des IDs
        payment_id = str(uuid.uuid4())
        transaction_id = f"FISCAL_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{payment_id[:8]}"
        
        fiscal_calculation = {
            "base_amount": float(request.base_amount),
            "tva": {"rate": tva_rate, "amount": float(tva_amount)},
            "municipal_tax": {"rate": municipal_rate, "amount": float(municipal_tax)},
            "transport_tax": {"rate": transport_tax_rate, "amount": float(transport_tax)},
            "total_amount": float(total_amount),
            "compliance": {
                "algerian_tax_code": "2024",
                "calculation_method": "automatic_fiscal_integration"
            }
        }
        
        return FiscalPaymentResponse(
            payment_id=payment_id,
            transaction_id=transaction_id,
            fiscal_calculation=fiscal_calculation,
            payment_status="completed",
            total_amount=total_amount,
            timestamp=datetime.now()
        )
        
    except Exception as e:
        logger.error(f"Erreur de paiement fiscal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de paiement fiscal: {str(e)}"
        )

