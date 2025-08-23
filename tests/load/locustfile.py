from locust import HttpUser, task, between
import json
import random

class VTCUser(HttpUser):
    wait_time = between(1, 3)
    
    def on_start(self):
        """Exécuté au démarrage de chaque utilisateur"""
        # Test de santé pour vérifier que l'API répond
        response = self.client.get("/health")
        if response.status_code != 200:
            print(f"Health check failed: {response.status_code}")
    
    @task(3)
    def test_health_endpoint(self):
        """Test de l'endpoint de santé - tâche fréquente"""
        self.client.get("/health")
    
    @task(2)
    def test_monitoring_dashboard(self):
        """Test du dashboard de monitoring"""
        self.client.get("/api/v1/monitoring/dashboard")
    
    @task(2)
    def test_fiscal_calculation(self):
        """Test du système fiscal"""
        payload = {
            "montant_ht": random.randint(500, 5000),
            "type_activite": "transport_personnes",
            "wilaya": random.choice(["alger", "oran", "constantine"])
        }
        self.client.post(
            "/api/v1/fiscal/calculate",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
    
    @task(1)
    def test_user_registration(self):
        """Test d'inscription d'utilisateur"""
        user_id = random.randint(1000, 9999)
        payload = {
            "email": f"test{user_id}@example.com",
            "password": "SecurePass123",
            "role": random.choice(["passenger", "driver"]),
            "first_name": "Test",
            "last_name": "User",
            "phone": f"+33{random.randint(100000000, 999999999)}"
        }
        self.client.post(
            "/api/v1/auth/register",
            json=payload,
            headers={"Content-Type": "application/json"}
        )
    
    @task(1)
    def test_metrics_endpoint(self):
        """Test des métriques publiques"""
        self.client.get("/api/v1/metrics/public")

class AdminUser(HttpUser):
    """Utilisateur admin avec des tâches spécifiques"""
    wait_time = between(2, 5)
    weight = 1  # Moins d'utilisateurs admin
    
    @task
    def test_monitoring_performance(self):
        """Test des métriques de performance"""
        self.client.get("/api/v1/monitoring/performance")
    
    @task
    def test_system_metrics(self):
        """Test des métriques système"""
        self.client.get("/api/v1/monitoring/system")

# Configuration pour différents scénarios de test
class QuickTest(HttpUser):
    """Test rapide pour validation"""
    wait_time = between(0.5, 1)
    
    @task
    def quick_health_check(self):
        self.client.get("/health")

class StressTest(HttpUser):
    """Test de stress avec charge élevée"""
    wait_time = between(0.1, 0.5)
    
    @task(5)
    def stress_health(self):
        self.client.get("/health")
    
    @task(3)
    def stress_fiscal(self):
        payload = {
            "montant_ht": 1000,
            "type_activite": "transport_personnes",
            "wilaya": "alger"
        }
        self.client.post("/api/v1/fiscal/calculate", json=payload)

