#!/usr/bin/env python3
"""Tests complets de l'application VTC avec PostgreSQL"""

import requests
import json
import time
import random
import string
from datetime import datetime

class VTCPostgreSQLTester:
    def __init__(self, base_url="http://localhost:8000"):
        self.base_url = base_url
        self.token = None
        self.test_results = []
        
    def log_test(self, test_name, success, details=""):
        """Enregistrer le résultat d'un test"""
        status = "✅ SUCCÈS" if success else "❌ ÉCHEC"
        result = f"{status} {test_name}"
        if details:
            result += f" - {details}"
        self.test_results.append(result)
        print(result)
        
    def test_health_check(self):
        """Test du health check"""
        try:
            response = requests.get(f"{self.base_url}/health", timeout=10)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Version: {data.get('version', 'N/A')}"
            self.log_test("Health Check", success, details)
            return success
        except Exception as e:
            self.log_test("Health Check", False, str(e))
            return False
    
    def test_user_registration(self):
        """Test de création d'utilisateur"""
        try:
            # Générer un email unique
            random_id = ''.join(random.choices(string.ascii_lowercase + string.digits, k=8))
            test_user = {
                "email": f"test_postgresql_{random_id}@test.com",
                "password": "password123",
                "role": "passenger",
                "first_name": "Test",
                "last_name": "PostgreSQL",
                "phone": "+33123456789"
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/auth/register",
                json=test_user,
                timeout=10
            )
            
            success = response.status_code in [200, 201]
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", User ID: {data.get('id', 'N/A')}"
                self.test_user_email = test_user["email"]
                self.test_user_password = test_user["password"]
            else:
                details += f", Error: {response.text}"
                
            self.log_test("Création Utilisateur", success, details)
            return success
        except Exception as e:
            self.log_test("Création Utilisateur", False, str(e))
            return False
    
    def test_user_login(self):
        """Test de connexion utilisateur"""
        try:
            if not hasattr(self, 'test_user_email'):
                self.log_test("Connexion Utilisateur", False, "Pas d'utilisateur créé")
                return False
                
            login_data = {
                "email": self.test_user_email,
                "password": self.test_user_password
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/auth/login",
                json=login_data,
                timeout=10
            )
            
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                self.token = data.get('access_token')
                details += f", Token obtenu: {'Oui' if self.token else 'Non'}"
            else:
                details += f", Error: {response.text}"
                
            self.log_test("Connexion Utilisateur", success, details)
            return success
        except Exception as e:
            self.log_test("Connexion Utilisateur", False, str(e))
            return False
    
    def test_trip_estimation(self):
        """Test d'estimation de course"""
        try:
            trip_data = {
                "pickup_address": "Place de la Concorde, Paris",
                "pickup_latitude": 48.8566,
                "pickup_longitude": 2.3522,
                "destination_address": "Tour Eiffel, Paris",
                "destination_latitude": 48.8584,
                "destination_longitude": 2.2945
            }
            
            response = requests.post(
                f"{self.base_url}/api/v1/trips/estimate",
                json=trip_data,
                timeout=10
            )
            
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                price = data.get('estimated_price', 0)
                details += f", Prix estimé: {price}€"
            else:
                details += f", Error: {response.text}"
                
            self.log_test("Estimation Course", success, details)
            return success
        except Exception as e:
            self.log_test("Estimation Course", False, str(e))
            return False
    
    def test_trip_creation(self):
        """Test de création de course"""
        try:
            if not self.token:
                self.log_test("Création Course", False, "Pas de token d'authentification")
                return False
                
            trip_data = {
                "pickup_address": "Place de la Concorde, Paris",
                "pickup_latitude": 48.8566,
                "pickup_longitude": 2.3522,
                "destination_address": "Tour Eiffel, Paris",
                "destination_latitude": 48.8584,
                "destination_longitude": 2.2945
            }
            
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.post(
                f"{self.base_url}/api/v1/trips",
                json=trip_data,
                headers=headers,
                timeout=10
            )
            
            success = response.status_code in [200, 201]
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                trip_id = data.get('id', 'N/A')
                details += f", Trip ID: {trip_id}"
                self.test_trip_id = trip_id
            else:
                details += f", Error: {response.text}"
                
            self.log_test("Création Course", success, details)
            return success
        except Exception as e:
            self.log_test("Création Course", False, str(e))
            return False
    
    def test_metrics_access(self):
        """Test d'accès aux métriques"""
        try:
            response = requests.get(
                f"{self.base_url}/api/v1/metrics/summary",
                timeout=10
            )
            
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                metrics_count = len(data.get('metrics', []))
                details += f", Métriques: {metrics_count}"
            else:
                details += f", Error: {response.text}"
                
            self.log_test("Accès Métriques", success, details)
            return success
        except Exception as e:
            self.log_test("Accès Métriques", False, str(e))
            return False
    
    def test_database_connection(self):
        """Test de connexion à la base de données PostgreSQL"""
        try:
            import psycopg2
            conn = psycopg2.connect(
                host='localhost',
                database='uber_vtc',
                user='uber_user',
                password='uber_password_2024',
                port='5432'
            )
            
            cursor = conn.cursor()
            
            # Test de comptage des utilisateurs
            cursor.execute("SELECT COUNT(*) FROM users")
            user_count = cursor.fetchone()[0]
            
            # Test de comptage des courses
            cursor.execute("SELECT COUNT(*) FROM trips")
            trip_count = cursor.fetchone()[0]
            
            # Test de comptage des métriques
            cursor.execute("SELECT COUNT(*) FROM metrics")
            metrics_count = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            details = f"Users: {user_count}, Trips: {trip_count}, Metrics: {metrics_count}"
            self.log_test("Connexion PostgreSQL", True, details)
            return True
            
        except Exception as e:
            self.log_test("Connexion PostgreSQL", False, str(e))
            return False
    
    def run_all_tests(self):
        """Exécuter tous les tests"""
        print("🐘 TESTS COMPLETS APPLICATION VTC AVEC POSTGRESQL")
        print("=" * 60)
        print(f"🕐 Début des tests: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print()
        
        tests = [
            self.test_health_check,
            self.test_database_connection,
            self.test_user_registration,
            self.test_user_login,
            self.test_trip_estimation,
            self.test_trip_creation,
            self.test_metrics_access
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
            time.sleep(1)  # Pause entre les tests
        
        print()
        print("📊 RÉSUMÉ DES TESTS:")
        print("=" * 40)
        for result in self.test_results:
            print(f"  {result}")
        
        print()
        success_rate = (passed / total) * 100
        print(f"🎯 RÉSULTAT FINAL: {passed}/{total} tests réussis ({success_rate:.1f}%)")
        
        if success_rate >= 85:
            print("🎉 POSTGRESQL INTÉGRATION RÉUSSIE !")
        elif success_rate >= 70:
            print("⚠️ POSTGRESQL PARTIELLEMENT FONCTIONNEL")
        else:
            print("❌ POSTGRESQL INTÉGRATION ÉCHOUÉE")
        
        return success_rate

if __name__ == "__main__":
    tester = VTCPostgreSQLTester()
    success_rate = tester.run_all_tests()

