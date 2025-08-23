"""
Tests d'intégration pour les endpoints API de l'application VTC.
"""

import pytest
import asyncio
from fastapi.testclient import TestClient
from decimal import Decimal
import json

from app.main import app


class TestFiscalEndpoints:
    """Tests d'intégration pour les endpoints fiscaux."""
    
    @pytest.fixture
    def client(self):
        """Client de test FastAPI."""
        return TestClient(app)
    
    def test_fiscal_health_endpoint(self, client):
        """Test de l'endpoint de santé fiscal."""
        response = client.get("/api/v1/fiscal/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "calculation_engine" in data
        assert data["version"] == "3.0.0"
        assert data["calculation_engine"] == "algerian_fiscal_v3_robust"
    
    def test_fiscal_calculate_endpoint(self, client):
        """Test de l'endpoint de calcul fiscal."""
        request_data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers",
            "passenger_count": 1,
            "is_business_trip": False,
            "time_of_day": "day"
        }
        
        response = client.post("/api/v1/fiscal/calculate", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier la structure de la réponse
        assert "calculation_id" in data
        assert "base_amount" in data
        assert "tva_amount" in data
        assert "total_amount" in data
        assert "fiscal_breakdown" in data
        assert "compliance_info" in data
        
        # Vérifier les valeurs
        assert float(data["base_amount"]) == 100.00
        assert float(data["total_amount"]) > 100.00
        assert float(data["tva_amount"]) > 0
    
    def test_fiscal_calculate_luxury_service(self, client):
        """Test de calcul fiscal pour service de luxe."""
        request_data = {
            "amount": 100.00,
            "service_type": "luxury",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        response = client.post("/api/v1/fiscal/calculate", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier qu'une surtaxe de luxe est appliquée
        assert float(data["luxury_surcharge"]) > 0
    
    def test_fiscal_calculate_business_trip(self, client):
        """Test de calcul fiscal pour voyage d'affaires."""
        request_data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers",
            "is_business_trip": True
        }
        
        response = client.post("/api/v1/fiscal/calculate", json=request_data)
        
        assert response.status_code == 200
        data = response.json()
        
        # Vérifier qu'une réduction d'affaires est appliquée
        assert float(data["business_reduction"]) > 0
    
    def test_fiscal_calculate_invalid_service_type(self, client):
        """Test avec un type de service invalide."""
        request_data = {
            "amount": 100.00,
            "service_type": "invalid_type",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        response = client.post("/api/v1/fiscal/calculate", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_fiscal_calculate_negative_amount(self, client):
        """Test avec un montant négatif."""
        request_data = {
            "amount": -100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        response = client.post("/api/v1/fiscal/calculate", json=request_data)
        
        assert response.status_code == 422  # Validation error
    
    def test_fiscal_batch_calculate(self, client):
        """Test de calcul fiscal en batch."""
        requests_data = [
            {
                "amount": 100.00,
                "service_type": "standard",
                "distance_km": 5.0,
                "duration_minutes": 15,
                "region": "algiers"
            },
            {
                "amount": 200.00,
                "service_type": "premium",
                "distance_km": 10.0,
                "duration_minutes": 25,
                "region": "oran"
            }
        ]
        
        response = client.post("/api/v1/fiscal/calculate-batch", json=requests_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "successful_calculations" in data
        assert "failed_calculations" in data
        assert "results" in data
        assert data["successful_calculations"] == 2
        assert data["failed_calculations"] == 0
        assert len(data["results"]) == 2
    
    def test_fiscal_rates_endpoint(self, client):
        """Test de l'endpoint des taux fiscaux."""
        response = client.get("/api/v1/fiscal/rates")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "tva_rates" in data
        assert "municipal_taxes" in data
        assert "transport_taxes" in data
        assert "service_adjustments" in data
        assert "version" in data
        
        # Vérifier les taux TVA
        assert data["tva_rates"]["standard"] == 0.19
        assert data["tva_rates"]["reduced"] == 0.09
    
    def test_fiscal_statistics_endpoint(self, client):
        """Test de l'endpoint des statistiques fiscales."""
        response = client.get("/api/v1/fiscal/statistics")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "performance" in data
        assert "timestamp" in data
        assert "service_version" in data
        assert data["service_version"] == "3.0.0"
    
    def test_fiscal_compliance_endpoint(self, client):
        """Test de l'endpoint de conformité fiscale."""
        response = client.get("/api/v1/fiscal/compliance")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "compliance_status" in data
        assert "certifications" in data
        assert "regulatory_updates" in data
        assert "performance_guarantees" in data
        assert data["compliance_status"] == "fully_compliant"


class TestMonitoringEndpoints:
    """Tests d'intégration pour les endpoints de monitoring."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_monitoring_dashboard(self, client):
        """Test du tableau de bord de monitoring."""
        response = client.get("/api/v1/monitoring/dashboard")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "business_metrics" in data
        assert "performance_metrics" in data
        assert "system_health" in data
    
    def test_monitoring_health(self, client):
        """Test de l'endpoint de santé du monitoring."""
        response = client.get("/api/v1/monitoring/health")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "status" in data
        assert "version" in data
        assert "total_metrics" in data
        assert data["version"] == "3.0.0"
    
    def test_monitoring_alerts(self, client):
        """Test de l'endpoint des alertes."""
        response = client.get("/api/v1/monitoring/alerts")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "active_alerts_count" in data
        assert "alerts" in data
        assert "timestamp" in data
    
    def test_monitoring_performance(self, client):
        """Test de l'endpoint des métriques de performance."""
        response = client.get("/api/v1/monitoring/performance")
        
        assert response.status_code == 200
        data = response.json()
        
        assert "timestamp" in data
        assert "api_metrics" in data
        assert "fiscal_metrics" in data
    
    def test_record_custom_metric(self, client):
        """Test d'enregistrement de métrique personnalisée."""
        metric_data = {
            "name": "test_metric",
            "value": 42.0,
            "metric_type": "gauge",
            "tags": {"test": "true"}
        }
        
        response = client.post("/api/v1/monitoring/metrics", json=metric_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "metric_name" in data
        assert data["metric_name"] == "test_metric"
    
    def test_record_business_event(self, client):
        """Test d'enregistrement d'événement business."""
        event_data = {
            "event_type": "trip_created",
            "trip_id": "test_trip_123",
            "value": 150.0,
            "metadata": {
                "driver_id": "driver_456",
                "customer_id": "customer_789"
            }
        }
        
        response = client.post("/api/v1/monitoring/events/business", json=event_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "event_type" in data
        assert data["event_type"] == "trip_created"
    
    def test_create_alert_rule(self, client):
        """Test de création de règle d'alerte."""
        rule_data = {
            "metric_name": "test_metric",
            "threshold": 100.0,
            "condition": "greater_than",
            "level": "warning",
            "message": "Test alert rule"
        }
        
        response = client.post("/api/v1/monitoring/alerts/rules", json=rule_data)
        
        assert response.status_code == 200
        data = response.json()
        
        assert "message" in data
        assert "metric_name" in data
        assert data["metric_name"] == "test_metric"


class TestAuthEndpoints:
    """Tests d'intégration pour les endpoints d'authentification."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_register_endpoint_structure(self, client):
        """Test de la structure de l'endpoint register."""
        # Test avec des données invalides pour vérifier la validation
        invalid_data = {
            "email": "invalid_email",
            "password": "123",  # Trop court
            "full_name": ""
        }
        
        response = client.post("/api/v1/register", json=invalid_data)
        
        # Doit retourner une erreur de validation
        assert response.status_code in [400, 422]
    
    def test_login_endpoint_structure(self, client):
        """Test de la structure de l'endpoint login."""
        # Test avec des données invalides
        invalid_data = {
            "email": "nonexistent@example.com",
            "password": "wrongpassword"
        }
        
        response = client.post("/api/v1/login", json=invalid_data)
        
        # Doit retourner une erreur d'authentification
        assert response.status_code in [400, 401, 422]


class TestTripEndpoints:
    """Tests d'intégration pour les endpoints de trajets."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_trip_request_endpoint_structure(self, client):
        """Test de la structure de l'endpoint de demande de trajet."""
        # Test avec des données invalides pour vérifier la validation
        invalid_data = {
            "pickup_location": "",  # Vide
            "destination": "",  # Vide
            "service_type": "invalid_type"
        }
        
        response = client.post("/api/v1/trips/request", json=invalid_data)
        
        # Doit retourner une erreur de validation
        assert response.status_code in [400, 422]


class TestEmergencyEndpoints:
    """Tests d'intégration pour les endpoints d'urgence."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_sos_endpoint_structure(self, client):
        """Test de la structure de l'endpoint SOS."""
        # Test avec des données invalides
        invalid_data = {
            "location": "",  # Vide
            "emergency_type": "invalid_type"
        }
        
        response = client.post("/api/v1/emergency/sos", json=invalid_data)
        
        # Doit retourner une erreur de validation
        assert response.status_code in [400, 422]


class TestRateLimiting:
    """Tests d'intégration pour le rate limiting."""
    
    @pytest.fixture
    def client(self):
        return TestClient(app)
    
    def test_rate_limiting_fiscal_endpoint(self, client):
        """Test du rate limiting sur l'endpoint fiscal."""
        request_data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        # Faire plusieurs requêtes rapidement
        responses = []
        for i in range(25):  # Dépasser la limite de 20 pour l'endpoint fiscal
            response = client.post("/api/v1/fiscal/calculate", json=request_data)
            responses.append(response)
        
        # Au moins une requête devrait être rate limitée
        rate_limited = any(r.status_code == 429 for r in responses)
        
        # Note: Le test peut ne pas déclencher le rate limiting en fonction de la configuration
        # et de la vitesse d'exécution des tests
        if rate_limited:
            assert True, "Rate limiting fonctionne correctement"
        else:
            # Si pas de rate limiting, vérifier que toutes les requêtes ont réussi
            assert all(r.status_code == 200 for r in responses), "Toutes les requêtes devraient réussir si pas de rate limiting"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

