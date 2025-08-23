#!/usr/bin/env python3
"""
Script de test des fonctionnalités critiques de l'application VTC.
"""

import sys
import os
import asyncio
import requests
import json
from datetime import datetime

# Ajouter le répertoire de l'application au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configuration de test
BASE_URL = "http://localhost:8000"
TEST_USER_PASSENGER = {
    "email": "passenger@test.com",
    "password": "password123",
    "role": "passenger",
    "first_name": "Test",
    "last_name": "Passenger",
    "phone": "+33123456789"
}

TEST_USER_DRIVER = {
    "email": "driver@test.com",
    "password": "password123",
    "role": "driver",
    "first_name": "Test",
    "last_name": "Driver",
    "phone": "+33987654321"
}

TEST_TRIP = {
    "pickup_latitude": 48.8566,
    "pickup_longitude": 2.3522,
    "pickup_address": "Place de la Concorde, Paris",
    "destination_latitude": 48.8584,
    "destination_longitude": 2.2945,
    "destination_address": "Tour Eiffel, Paris",
    "vehicle_type": "standard"
}


class VTCTester:
    """Testeur des fonctionnalités critiques VTC"""
    
    def __init__(self):
        self.passenger_token = None
        self.driver_token = None
        self.test_trip_id = None
        self.results = []
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Enregistre le résultat d'un test"""
        status = "✅ PASS" if success else "❌ FAIL"
        print(f"{status} {test_name}")
        if details:
            print(f"    {details}")
        
        self.results.append({
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        })
    
    def test_health_check(self):
        """Test 1: Vérification de santé de l'API"""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            success = response.status_code == 200
            details = f"Status: {response.status_code}"
            if success:
                data = response.json()
                details += f", Response: {data}"
        except Exception as e:
            success = False
            details = f"Erreur: {str(e)}"
        
        self.log_test("Health Check API", success, details)
        return success
    
    def test_user_registration(self):
        """Test 2: Inscription des utilisateurs"""
        success_passenger = self._register_user(TEST_USER_PASSENGER, "passenger")
        success_driver = self._register_user(TEST_USER_DRIVER, "driver")
        
        success = success_passenger and success_driver
        self.log_test("Inscription utilisateurs", success)
        return success
    
    def _register_user(self, user_data: dict, role: str) -> bool:
        """Inscrit un utilisateur"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/register",
                json=user_data,
                timeout=10
            )
            
            if response.status_code == 201:
                print(f"    ✅ Utilisateur {role} créé")
                return True
            else:
                print(f"    ❌ Échec création {role}: {response.status_code}")
                print(f"    Response: {response.text}")
                return False
                
        except Exception as e:
            print(f"    ❌ Erreur création {role}: {str(e)}")
            return False
    
    def test_user_authentication(self):
        """Test 3: Authentification des utilisateurs"""
        success_passenger = self._authenticate_user(TEST_USER_PASSENGER, "passenger")
        success_driver = self._authenticate_user(TEST_USER_DRIVER, "driver")
        
        success = success_passenger and success_driver
        self.log_test("Authentification utilisateurs", success)
        return success
    
    def _authenticate_user(self, user_data: dict, role: str) -> bool:
        """Authentifie un utilisateur"""
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/auth/login",
                json={
                    "email": user_data["email"],
                    "password": user_data["password"]
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                token = data.get("access_token")
                
                if role == "passenger":
                    self.passenger_token = token
                else:
                    self.driver_token = token
                
                print(f"    ✅ Authentification {role} réussie")
                return True
            else:
                print(f"    ❌ Échec authentification {role}: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"    ❌ Erreur authentification {role}: {str(e)}")
            return False
    
    def test_trip_estimation(self):
        """Test 4: Estimation de course"""
        if not self.passenger_token:
            self.log_test("Estimation de course", False, "Token passager manquant")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.passenger_token}"}
            response = requests.post(
                f"{BASE_URL}/api/v1/trips/estimate",
                json=TEST_TRIP,
                headers=headers,
                timeout=10
            )
            
            success = response.status_code == 200
            if success:
                data = response.json()
                details = f"Prix estimé: {data.get('estimated_price', 'N/A')}€"
            else:
                details = f"Status: {response.status_code}, Response: {response.text}"
            
        except Exception as e:
            success = False
            details = f"Erreur: {str(e)}"
        
        self.log_test("Estimation de course", success, details)
        return success
    
    def test_trip_creation(self):
        """Test 5: Création de course"""
        if not self.passenger_token:
            self.log_test("Création de course", False, "Token passager manquant")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.passenger_token}"}
            response = requests.post(
                f"{BASE_URL}/api/v1/trips",
                json=TEST_TRIP,
                headers=headers,
                timeout=10
            )
            
            success = response.status_code == 201
            if success:
                data = response.json()
                self.test_trip_id = data.get("id")
                details = f"Course créée: {self.test_trip_id}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text}"
            
        except Exception as e:
            success = False
            details = f"Erreur: {str(e)}"
        
        self.log_test("Création de course", success, details)
        return success
    
    def test_trip_listing(self):
        """Test 6: Listage des courses"""
        if not self.passenger_token:
            self.log_test("Listage des courses", False, "Token passager manquant")
            return False
        
        try:
            headers = {"Authorization": f"Bearer {self.passenger_token}"}
            response = requests.get(
                f"{BASE_URL}/api/v1/trips",
                headers=headers,
                timeout=10
            )
            
            success = response.status_code == 200
            if success:
                data = response.json()
                trip_count = len(data.get("trips", []))
                details = f"Nombre de courses: {trip_count}"
            else:
                details = f"Status: {response.status_code}, Response: {response.text}"
            
        except Exception as e:
            success = False
            details = f"Erreur: {str(e)}"
        
        self.log_test("Listage des courses", success, details)
        return success
    
    def test_url_redirections(self):
        """Test 7: Correction des redirections URL"""
        try:
            # Test sans slash final
            response1 = requests.get(f"{BASE_URL}/api/v1/trips", timeout=5)
            # Test avec slash final  
            response2 = requests.get(f"{BASE_URL}/api/v1/trips/", timeout=5)
            
            # Les deux doivent fonctionner sans redirection 307
            success = (response1.status_code != 307 and response2.status_code != 307)
            details = f"Sans slash: {response1.status_code}, Avec slash: {response2.status_code}"
            
        except Exception as e:
            success = False
            details = f"Erreur: {str(e)}"
        
        self.log_test("Correction redirections URL", success, details)
        return success
    
    def test_metrics_access(self):
        """Test 8: Accès aux métriques (admin requis)"""
        try:
            # Test sans authentification (doit échouer)
            response = requests.get(f"{BASE_URL}/api/v1/metrics/summary", timeout=5)
            
            success = response.status_code in [401, 403]  # Authentification requise
            details = f"Status sans auth: {response.status_code} (attendu: 401/403)"
            
        except Exception as e:
            success = False
            details = f"Erreur: {str(e)}"
        
        self.log_test("Sécurité métriques", success, details)
        return success
    
    def run_all_tests(self):
        """Exécute tous les tests critiques"""
        print("🚀 DÉBUT DES TESTS CRITIQUES VTC")
        print("=" * 50)
        
        tests = [
            self.test_health_check,
            self.test_user_registration,
            self.test_user_authentication,
            self.test_trip_estimation,
            self.test_trip_creation,
            self.test_trip_listing,
            self.test_url_redirections,
            self.test_metrics_access
        ]
        
        passed = 0
        total = len(tests)
        
        for test in tests:
            if test():
                passed += 1
            print()  # Ligne vide entre les tests
        
        # Résumé final
        print("=" * 50)
        print(f"📊 RÉSULTATS: {passed}/{total} tests réussis")
        
        if passed == total:
            print("🎉 TOUS LES TESTS CRITIQUES SONT PASSÉS!")
            print("✅ Application prête pour la production")
        else:
            print(f"⚠️  {total - passed} test(s) échoué(s)")
            print("❌ Corrections nécessaires avant production")
        
        return passed == total
    
    def save_results(self, filename: str = "test_results.json"):
        """Sauvegarde les résultats des tests"""
        with open(filename, 'w') as f:
            json.dump({
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.results),
                "passed_tests": sum(1 for r in self.results if r["success"]),
                "results": self.results
            }, f, indent=2)
        
        print(f"📄 Résultats sauvegardés dans {filename}")


def main():
    """Fonction principale"""
    print("🔧 TESTEUR VTC - FONCTIONNALITÉS CRITIQUES")
    print("Assurez-vous que l'application est démarrée sur http://localhost:8000")
    print()
    
    # Attendre que l'utilisateur confirme
    input("Appuyez sur Entrée pour commencer les tests...")
    print()
    
    # Exécuter les tests
    tester = VTCTester()
    success = tester.run_all_tests()
    
    # Sauvegarder les résultats
    tester.save_results()
    
    # Code de sortie
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()

