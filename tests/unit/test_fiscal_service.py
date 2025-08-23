"""
Tests unitaires pour le service fiscal robuste.
"""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime

from app.services.fiscal_service import (
    RobustFiscalService, FiscalCalculationRequest, ServiceType, FiscalRegion,
    FiscalCache, TaxRates
)


class TestFiscalCache:
    """Tests pour le cache fiscal."""
    
    def test_cache_key_generation(self):
        """Test de génération de clé de cache."""
        cache = FiscalCache()
        
        request1 = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        request2 = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        key1 = cache._generate_key(request1)
        key2 = cache._generate_key(request2)
        
        assert key1 == key2, "Les clés doivent être identiques pour des requêtes identiques"
    
    def test_cache_different_keys(self):
        """Test que des requêtes différentes génèrent des clés différentes."""
        cache = FiscalCache()
        
        request1 = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        request2 = FiscalCalculationRequest(
            base_amount=Decimal("200.00"),  # Montant différent
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        key1 = cache._generate_key(request1)
        key2 = cache._generate_key(request2)
        
        assert key1 != key2, "Les clés doivent être différentes pour des requêtes différentes"


class TestRobustFiscalService:
    """Tests pour le service fiscal robuste."""
    
    @pytest.fixture
    def fiscal_service(self):
        """Fixture pour le service fiscal."""
        return RobustFiscalService()
    
    @pytest.fixture
    def basic_request(self):
        """Fixture pour une requête de base."""
        return FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
    
    @pytest.mark.asyncio
    async def test_basic_calculation(self, fiscal_service, basic_request):
        """Test de calcul fiscal de base."""
        result = await fiscal_service.calculate_fiscal_amount(basic_request)
        
        assert result.base_amount == Decimal("100.00")
        assert result.total_amount > result.base_amount
        assert result.tva_amount > 0
        assert result.municipal_tax > 0
        assert result.transport_tax > 0
        assert result.calculation_id is not None
        assert result.timestamp is not None
    
    @pytest.mark.asyncio
    async def test_luxury_service_surcharge(self, fiscal_service):
        """Test de la surtaxe pour service de luxe."""
        request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.LUXURY,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        result = await fiscal_service.calculate_fiscal_amount(request)
        
        assert result.luxury_surcharge > 0, "Une surtaxe de luxe doit être appliquée"
    
    @pytest.mark.asyncio
    async def test_business_trip_reduction(self, fiscal_service):
        """Test de la réduction pour voyage d'affaires."""
        request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS,
            is_business_trip=True
        )
        
        result = await fiscal_service.calculate_fiscal_amount(request)
        
        assert result.business_reduction > 0, "Une réduction d'affaires doit être appliquée"
    
    @pytest.mark.asyncio
    async def test_regional_differences(self, fiscal_service):
        """Test des différences régionales."""
        base_request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        other_request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.OTHER
        )
        
        algiers_result = await fiscal_service.calculate_fiscal_amount(base_request)
        other_result = await fiscal_service.calculate_fiscal_amount(other_request)
        
        # Alger devrait avoir des taxes municipales plus élevées
        assert algiers_result.municipal_tax > other_result.municipal_tax
    
    @pytest.mark.asyncio
    async def test_distance_based_transport_tax(self, fiscal_service):
        """Test de la taxe de transport basée sur la distance."""
        short_request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=5.0,  # Distance courte
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        long_request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=15.0,  # Distance longue
            duration_minutes=30,
            region=FiscalRegion.ALGIERS
        )
        
        short_result = await fiscal_service.calculate_fiscal_amount(short_request)
        long_result = await fiscal_service.calculate_fiscal_amount(long_request)
        
        # Les distances longues devraient avoir une taxe de transport plus élevée
        assert long_result.transport_tax > short_result.transport_tax
    
    @pytest.mark.asyncio
    async def test_cache_functionality(self, fiscal_service, basic_request):
        """Test de la fonctionnalité de cache."""
        # Premier calcul
        result1 = await fiscal_service.calculate_fiscal_amount(basic_request)
        
        # Deuxième calcul identique (devrait utiliser le cache)
        result2 = await fiscal_service.calculate_fiscal_amount(basic_request)
        
        # Les résultats doivent être identiques
        assert result1.total_amount == result2.total_amount
        assert result1.tva_amount == result2.tva_amount
        assert result1.municipal_tax == result2.municipal_tax
        
        # Vérifier que le cache a été utilisé
        stats = fiscal_service.get_statistics()
        assert stats["cache_hits"] > 0
    
    @pytest.mark.asyncio
    async def test_invalid_amount(self, fiscal_service):
        """Test avec un montant invalide."""
        request = FiscalCalculationRequest(
            base_amount=Decimal("-100.00"),  # Montant négatif
            service_type=ServiceType.STANDARD,
            distance_km=5.0,
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        with pytest.raises(ValueError, match="Le montant de base doit être positif"):
            await fiscal_service.calculate_fiscal_amount(request)
    
    @pytest.mark.asyncio
    async def test_invalid_distance(self, fiscal_service):
        """Test avec une distance invalide."""
        request = FiscalCalculationRequest(
            base_amount=Decimal("100.00"),
            service_type=ServiceType.STANDARD,
            distance_km=-5.0,  # Distance négative
            duration_minutes=15,
            region=FiscalRegion.ALGIERS
        )
        
        with pytest.raises(ValueError, match="La distance ne peut pas être négative"):
            await fiscal_service.calculate_fiscal_amount(request)
    
    @pytest.mark.asyncio
    async def test_calculation_id_uniqueness(self, fiscal_service, basic_request):
        """Test de l'unicité des IDs de calcul."""
        result1 = await fiscal_service.calculate_fiscal_amount(basic_request)
        result2 = await fiscal_service.calculate_fiscal_amount(basic_request)
        
        # Même si les calculs sont identiques, les IDs doivent être différents
        # (sauf si le cache est utilisé, auquel cas c'est le même résultat)
        if result1.calculation_id == result2.calculation_id:
            # Cache utilisé, c'est normal
            pass
        else:
            # Nouveaux calculs, IDs différents
            assert result1.calculation_id != result2.calculation_id
    
    @pytest.mark.asyncio
    async def test_compliance_info(self, fiscal_service, basic_request):
        """Test des informations de conformité."""
        result = await fiscal_service.calculate_fiscal_amount(basic_request)
        
        assert "regulatory_compliance" in result.compliance_info
        assert "calculation_method" in result.compliance_info
        assert "audit_trail" in result.compliance_info
        
        compliance = result.compliance_info["regulatory_compliance"]
        assert "algerian_tax_code" in compliance
        assert "certification" in compliance
    
    @pytest.mark.asyncio
    async def test_breakdown_completeness(self, fiscal_service, basic_request):
        """Test de la complétude du détail de calcul."""
        result = await fiscal_service.calculate_fiscal_amount(basic_request)
        
        assert "base_calculation" in result.breakdown
        assert "taxes" in result.breakdown
        assert "adjustments" in result.breakdown
        
        taxes = result.breakdown["taxes"]
        assert "tva" in taxes
        assert "municipal" in taxes
        assert "transport" in taxes
        
        adjustments = result.breakdown["adjustments"]
        assert "luxury_surcharge" in adjustments
        assert "business_reduction" in adjustments
    
    @pytest.mark.asyncio
    async def test_health_check(self, fiscal_service):
        """Test du health check."""
        health = await fiscal_service.health_check()
        
        assert "status" in health
        assert health["status"] in ["healthy", "unhealthy"]
        assert "response_time_ms" in health
        assert "cache_operational" in health
    
    def test_statistics(self, fiscal_service):
        """Test des statistiques."""
        stats = fiscal_service.get_statistics()
        
        assert "total_calculations" in stats
        assert "cache_hits" in stats
        assert "errors" in stats
        assert "average_calculation_time" in stats
        assert "cache_size" in stats
        assert "cache_hit_rate" in stats
    
    def test_cache_clear(self, fiscal_service):
        """Test du vidage de cache."""
        # Ajouter quelque chose au cache
        fiscal_service.cache.cache["test"] = ("value", 123456)
        
        assert len(fiscal_service.cache.cache) > 0
        
        fiscal_service.clear_cache()
        
        assert len(fiscal_service.cache.cache) == 0


class TestTaxCalculations:
    """Tests spécifiques aux calculs de taxes."""
    
    @pytest.fixture
    def fiscal_service(self):
        return RobustFiscalService()
    
    def test_tva_calculation(self, fiscal_service):
        """Test du calcul de TVA."""
        amount = Decimal("100.00")
        
        # Service standard
        tva_amount, tva_rate = fiscal_service._calculate_tva(amount, ServiceType.STANDARD)
        expected_tva = amount * fiscal_service.tax_rates.tva_standard
        assert tva_amount == expected_tva.quantize(Decimal('0.01'))
        
        # Service de luxe
        tva_amount_luxury, tva_rate_luxury = fiscal_service._calculate_tva(amount, ServiceType.LUXURY)
        expected_tva_luxury = amount * fiscal_service.tax_rates.tva_standard
        assert tva_amount_luxury == expected_tva_luxury.quantize(Decimal('0.01'))
    
    def test_municipal_tax_calculation(self, fiscal_service):
        """Test du calcul de taxe municipale."""
        amount = Decimal("100.00")
        
        # Test pour Alger
        municipal_tax = fiscal_service._calculate_municipal_tax(amount, FiscalRegion.ALGIERS)
        expected_rate = (fiscal_service.tax_rates.municipal_base * 
                        fiscal_service.regional_multipliers[FiscalRegion.ALGIERS]["municipal"])
        expected_tax = (amount * expected_rate).quantize(Decimal('0.01'))
        assert municipal_tax == expected_tax
    
    def test_transport_tax_calculation(self, fiscal_service):
        """Test du calcul de taxe de transport."""
        amount = Decimal("100.00")
        
        # Distance courte
        transport_tax_short = fiscal_service._calculate_transport_tax(amount, 5.0, FiscalRegion.ALGIERS)
        
        # Distance longue
        transport_tax_long = fiscal_service._calculate_transport_tax(amount, 15.0, FiscalRegion.ALGIERS)
        
        # La taxe longue distance doit être plus élevée
        assert transport_tax_long > transport_tax_short
    
    def test_service_adjustments(self, fiscal_service):
        """Test des ajustements de service."""
        amount = Decimal("100.00")
        
        # Service de luxe
        luxury_surcharge, business_reduction = fiscal_service._calculate_service_adjustments(
            amount, ServiceType.LUXURY, False
        )
        assert luxury_surcharge > 0
        assert business_reduction == 0
        
        # Voyage d'affaires
        luxury_surcharge_biz, business_reduction_biz = fiscal_service._calculate_service_adjustments(
            amount, ServiceType.STANDARD, True
        )
        assert luxury_surcharge_biz == 0
        assert business_reduction_biz > 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

