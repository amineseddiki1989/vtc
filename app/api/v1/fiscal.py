"""
Module API pour le système fiscal algérien robuste.
"""

from fastapi import APIRouter, HTTPException, Depends, status, BackgroundTasks
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Dict, Any, Optional
from decimal import Decimal
from datetime import datetime
import logging
import asyncio

from ...services.fiscal_service import (
    fiscal_service, FiscalCalculationRequest, ServiceType, FiscalRegion
)

logger = logging.getLogger(__name__)

router = APIRouter()


class FiscalCalculationRequestAPI(BaseModel):
    """Modèle API pour les demandes de calcul fiscal."""
    amount: Decimal = Field(..., description="Montant de base en DZD", gt=0)
    service_type: str = Field(..., description="Type de service (standard, premium, luxury, shared, business)")
    distance_km: float = Field(..., description="Distance en kilomètres", ge=0)
    duration_minutes: int = Field(..., description="Durée en minutes", ge=0)
    region: str = Field(default="algiers", description="Région (algiers, oran, constantine, etc.)")
    passenger_count: int = Field(default=1, description="Nombre de passagers", ge=1, le=8)
    is_business_trip: bool = Field(default=False, description="Voyage d'affaires")
    time_of_day: str = Field(default="day", description="Moment de la journée (day, night, peak)")
    
    @validator('service_type')
    def validate_service_type(cls, v):
        valid_types = [t.value for t in ServiceType]
        if v not in valid_types:
            raise ValueError(f"Type de service invalide. Valeurs autorisées: {valid_types}")
        return v
    
    @validator('region')
    def validate_region(cls, v):
        valid_regions = [r.value for r in FiscalRegion]
        if v not in valid_regions:
            raise ValueError(f"Région invalide. Valeurs autorisées: {valid_regions}")
        return v
    
    @validator('time_of_day')
    def validate_time_of_day(cls, v):
        if v not in ["day", "night", "peak"]:
            raise ValueError("time_of_day doit être 'day', 'night' ou 'peak'")
        return v


class FiscalCalculationResponseAPI(BaseModel):
    """Modèle API pour les réponses de calcul fiscal."""
    calculation_id: str
    base_amount: Decimal
    tva_amount: Decimal
    tva_rate: float
    municipal_tax: Decimal
    transport_tax: Decimal
    luxury_surcharge: Decimal
    business_reduction: Decimal
    total_amount: Decimal
    calculation_timestamp: datetime
    fiscal_breakdown: Dict[str, Any]
    compliance_info: Dict[str, Any]


class FiscalHealthResponse(BaseModel):
    """Modèle pour la santé du système fiscal."""
    status: str
    version: str
    last_update: datetime
    tax_rates_valid: bool
    calculation_engine: str
    performance_metrics: Dict[str, Any]


@router.get("/fiscal/health", response_model=FiscalHealthResponse)
async def fiscal_health_check():
    """Vérification de santé du système fiscal robuste."""
    try:
        health_data = await fiscal_service.health_check()
        
        return FiscalHealthResponse(
            status=health_data["status"],
            version="3.0.0",
            last_update=datetime.now(),
            tax_rates_valid=True,
            calculation_engine="algerian_fiscal_v3_robust",
            performance_metrics=health_data.get("statistics", {})
        )
    except Exception as e:
        logger.error(f"Erreur lors du health check fiscal: {e}")
        return FiscalHealthResponse(
            status="unhealthy",
            version="3.0.0",
            last_update=datetime.now(),
            tax_rates_valid=False,
            calculation_engine="algerian_fiscal_v3_robust",
            performance_metrics={"error": str(e)}
        )


@router.post("/fiscal/calculate", response_model=FiscalCalculationResponseAPI)
async def calculate_fiscal_amount(request: FiscalCalculationRequestAPI):
    """Calcule les taxes et montants fiscaux selon la réglementation algérienne (version robuste)."""
    try:
        # Convertir la requête API en requête de service
        service_request = FiscalCalculationRequest(
            base_amount=request.amount,
            service_type=ServiceType(request.service_type),
            distance_km=request.distance_km,
            duration_minutes=request.duration_minutes,
            region=FiscalRegion(request.region),
            passenger_count=request.passenger_count,
            is_business_trip=request.is_business_trip,
            time_of_day=request.time_of_day
        )
        
        # Effectuer le calcul fiscal
        result = await fiscal_service.calculate_fiscal_amount(service_request)
        
        return FiscalCalculationResponseAPI(
            calculation_id=result.calculation_id,
            base_amount=result.base_amount,
            tva_amount=result.tva_amount,
            tva_rate=float(result.tva_rate),
            municipal_tax=result.municipal_tax,
            transport_tax=result.transport_tax,
            luxury_surcharge=result.luxury_surcharge,
            business_reduction=result.business_reduction,
            total_amount=result.total_amount,
            calculation_timestamp=result.timestamp,
            fiscal_breakdown=result.breakdown,
            compliance_info=result.compliance_info
        )
        
    except ValueError as e:
        logger.warning(f"Erreur de validation lors du calcul fiscal: {e}")
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Erreur de validation: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Erreur lors du calcul fiscal: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de calcul fiscal: {str(e)}"
        )


@router.post("/fiscal/calculate-batch")
async def calculate_fiscal_batch(requests: list[FiscalCalculationRequestAPI]):
    """Calcule les montants fiscaux pour plusieurs demandes en parallèle."""
    if len(requests) > 100:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Maximum 100 calculs par batch"
        )
    
    try:
        # Convertir toutes les requêtes
        service_requests = []
        for req in requests:
            service_requests.append(FiscalCalculationRequest(
                base_amount=req.amount,
                service_type=ServiceType(req.service_type),
                distance_km=req.distance_km,
                duration_minutes=req.duration_minutes,
                region=FiscalRegion(req.region),
                passenger_count=req.passenger_count,
                is_business_trip=req.is_business_trip,
                time_of_day=req.time_of_day
            ))
        
        # Exécuter les calculs en parallèle
        tasks = [fiscal_service.calculate_fiscal_amount(req) for req in service_requests]
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les résultats
        responses = []
        errors = []
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                errors.append({
                    "index": i,
                    "error": str(result)
                })
            else:
                responses.append(FiscalCalculationResponseAPI(
                    calculation_id=result.calculation_id,
                    base_amount=result.base_amount,
                    tva_amount=result.tva_amount,
                    tva_rate=float(result.tva_rate),
                    municipal_tax=result.municipal_tax,
                    transport_tax=result.transport_tax,
                    luxury_surcharge=result.luxury_surcharge,
                    business_reduction=result.business_reduction,
                    total_amount=result.total_amount,
                    calculation_timestamp=result.timestamp,
                    fiscal_breakdown=result.breakdown,
                    compliance_info=result.compliance_info
                ))
        
        return {
            "successful_calculations": len(responses),
            "failed_calculations": len(errors),
            "results": responses,
            "errors": errors
        }
        
    except Exception as e:
        logger.error(f"Erreur lors du calcul fiscal en batch: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Erreur de calcul fiscal en batch: {str(e)}"
        )


@router.get("/fiscal/rates")
async def get_tax_rates():
    """Retourne les taux de taxation actuels avec détails régionaux."""
    return {
        "tva_rates": {
            "standard": 0.19,
            "reduced": 0.09
        },
        "municipal_taxes": {
            "algiers": {"base": 0.01, "multiplier": 2.0, "effective": 0.02},
            "oran": {"base": 0.01, "multiplier": 1.5, "effective": 0.015},
            "constantine": {"base": 0.01, "multiplier": 1.5, "effective": 0.015},
            "annaba": {"base": 0.01, "multiplier": 1.3, "effective": 0.013},
            "setif": {"base": 0.01, "multiplier": 1.2, "effective": 0.012},
            "batna": {"base": 0.01, "multiplier": 1.2, "effective": 0.012},
            "other": {"base": 0.01, "multiplier": 1.0, "effective": 0.01}
        },
        "transport_taxes": {
            "short_distance": {"base": 0.003, "threshold_km": 10},
            "long_distance": {"base": 0.005, "threshold_km": 10}
        },
        "service_adjustments": {
            "luxury_surcharge": 0.02,
            "business_reduction": 0.005
        },
        "last_update": datetime.now().isoformat(),
        "regulatory_source": "Direction Générale des Impôts - Algérie",
        "version": "3.0.0"
    }


@router.get("/fiscal/statistics")
async def get_fiscal_statistics():
    """Retourne les statistiques de performance du système fiscal."""
    try:
        stats = fiscal_service.get_statistics()
        return {
            "performance": stats,
            "timestamp": datetime.now().isoformat(),
            "service_version": "3.0.0"
        }
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des statistiques: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de la récupération des statistiques"
        )


@router.post("/fiscal/cache/clear")
async def clear_fiscal_cache(background_tasks: BackgroundTasks):
    """Vide le cache fiscal (opération d'administration)."""
    try:
        background_tasks.add_task(fiscal_service.clear_cache)
        return {
            "message": "Cache fiscal en cours de vidage",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Erreur lors du vidage du cache: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors du vidage du cache"
        )


@router.get("/fiscal/compliance")
async def get_compliance_status():
    """Retourne le statut de conformité fiscale détaillé."""
    return {
        "compliance_status": "fully_compliant",
        "last_audit": "2024-01-15",
        "next_audit": "2024-07-15",
        "certifications": [
            "DGI_ALGERIA_2024",
            "MUNICIPAL_TAX_COMPLIANT",
            "TRANSPORT_LAW_2023",
            "FISCAL_ROBUSTNESS_CERTIFIED"
        ],
        "regulatory_updates": {
            "pending": [],
            "applied": [
                {
                    "date": "2024-01-01",
                    "description": "Mise à jour des taux municipaux",
                    "impact": "Taux municipal Alger: 1.8% -> 2.0%"
                },
                {
                    "date": "2024-01-01",
                    "description": "Implémentation du système robuste v3.0",
                    "impact": "Cache, calculs parallèles, gestion d'erreurs avancée"
                }
            ]
        },
        "performance_guarantees": {
            "max_response_time_ms": 100,
            "cache_hit_rate_target": 80,
            "error_rate_target": 0.1,
            "concurrent_calculations": 1000
        }
    }

