#!/usr/bin/env python3
"""
Tests complets pour WebSocket et ETA dynamique.
Validation réelle des fonctionnalités dans l'environnement sandbox.
"""

import asyncio
import json
import requests
import websockets
import time
from datetime import datetime
from typing import Dict, Any

# Configuration
BASE_URL = "http://localhost:8000"
WS_URL = "ws://localhost:8000"

class WebSocketETATestSuite:
    """Suite de tests pour WebSocket et ETA."""
    
    def __init__(self):
        self.token = None
        self.user_id = None
        self.test_results = []
    
    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Enregistrer un résultat de test."""
        result = {
            "test": test_name,
            "success": success,
            "details": details,
            "timestamp": datetime.now().isoformat()
        }
        self.test_results.append(result)
        
        status = "✅ RÉUSSI" if success else "❌ ÉCHEC"
        print(f"{status} - {test_name}")
        if details:
            print(f"   Détails: {details}")
    
    def test_application_health(self) -> bool:
        """Tester la santé de l'application."""
        try:
            response = requests.get(f"{BASE_URL}/health", timeout=5)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                details = f"Version: {data.get('version')}, Status: {data.get('status')}"
            else:
                details = f"Status code: {response.status_code}"
            
            self.log_test("Application Health Check", success, details)
            return success
            
        except Exception as e:
            self.log_test("Application Health Check", False, str(e))
            return False
    
    def test_user_authentication(self) -> bool:
        """Tester l'authentification utilisateur."""
        try:
            # Créer un utilisateur de test
            user_data = {
                "email": f"test_ws_{int(time.time())}@example.com",
                "password": "TestPassword123!",
                "first_name": "Test",
                "last_name": "WebSocket",
                "phone": "+33123456789",
                "role": "passenger"
            }
            
            # Inscription
            response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data, timeout=10)
            
            if response.status_code == 200:
                user_info = response.json()
                self.user_id = user_info.get("user", {}).get("id")
                
                # Connexion
                login_data = {
                    "email": user_data["email"],
                    "password": user_data["password"]
                }
                
                login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
                
                if login_response.status_code == 200:
                    login_info = login_response.json()
                    self.token = login_info.get("access_token")
                    
                    self.log_test("User Authentication", True, f"User ID: {self.user_id}")
                    return True
                else:
                    self.log_test("User Authentication", False, f"Login failed: {login_response.status_code}")
                    return False
            else:
                self.log_test("User Authentication", False, f"Registration failed: {response.status_code}")
                return False
                
        except Exception as e:
            self.log_test("User Authentication", False, str(e))
            return False
    
    def test_eta_providers(self) -> bool:
        """Tester la liste des fournisseurs ETA."""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(f"{BASE_URL}/api/v1/eta/providers", headers=headers, timeout=10)
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                providers = data.get("providers", [])
                enabled_count = sum(1 for p in providers if p.get("enabled"))
                details = f"Providers: {len(providers)}, Enabled: {enabled_count}"
            else:
                details = f"Status code: {response.status_code}"
            
            self.log_test("ETA Providers List", success, details)
            return success
            
        except Exception as e:
            self.log_test("ETA Providers List", False, str(e))
            return False
    
    def test_eta_calculation(self) -> bool:
        """Tester le calcul ETA."""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            
            # Test avec des coordonnées Paris -> Lyon
            eta_request = {
                "origin_latitude": 48.8566,
                "origin_longitude": 2.3522,
                "destination_latitude": 45.7640,
                "destination_longitude": 4.8357
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/eta/calculate",
                headers=headers,
                json=eta_request,
                timeout=15
            )
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                duration_min = data.get("duration_minutes", 0)
                distance_km = data.get("distance_km", 0)
                provider = data.get("provider", "unknown")
                details = f"Duration: {duration_min:.1f}min, Distance: {distance_km:.1f}km, Provider: {provider}"
            else:
                details = f"Status code: {response.status_code}"
            
            self.log_test("ETA Calculation", success, details)
            return success
            
        except Exception as e:
            self.log_test("ETA Calculation", False, str(e))
            return False
    
    async def test_websocket_connection(self) -> bool:
        """Tester la connexion WebSocket."""
        try:
            uri = f"{WS_URL}/api/v1/ws/location?token={self.token}"
            
            async with websockets.connect(uri) as websocket:
                # Attendre le message de connexion
                welcome_message = await asyncio.wait_for(websocket.recv(), timeout=5)
                welcome_data = json.loads(welcome_message)
                
                success = welcome_data.get("type") == "connection_established"
                
                if success:
                    user_id = welcome_data.get("user_id")
                    role = welcome_data.get("role")
                    details = f"User: {user_id}, Role: {role}"
                else:
                    details = f"Unexpected message: {welcome_data}"
                
                self.log_test("WebSocket Connection", success, details)
                return success
                
        except Exception as e:
            self.log_test("WebSocket Connection", False, str(e))
            return False
    
    async def test_websocket_ping_pong(self) -> bool:
        """Tester le ping/pong WebSocket."""
        try:
            uri = f"{WS_URL}/api/v1/ws/location?token={self.token}"
            
            async with websockets.connect(uri) as websocket:
                # Attendre le message de bienvenue
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Envoyer un ping
                ping_message = {"type": "ping"}
                await websocket.send(json.dumps(ping_message))
                
                # Attendre le pong
                pong_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                pong_data = json.loads(pong_response)
                
                success = pong_data.get("type") == "pong"
                details = f"Response type: {pong_data.get('type')}"
                
                self.log_test("WebSocket Ping/Pong", success, details)
                return success
                
        except Exception as e:
            self.log_test("WebSocket Ping/Pong", False, str(e))
            return False
    
    async def test_websocket_location_update(self) -> bool:
        """Tester la mise à jour de position via WebSocket."""
        try:
            uri = f"{WS_URL}/api/v1/ws/location?token={self.token}"
            
            async with websockets.connect(uri) as websocket:
                # Attendre le message de bienvenue
                await asyncio.wait_for(websocket.recv(), timeout=5)
                
                # Envoyer une mise à jour de position
                location_update = {
                    "type": "location_update",
                    "latitude": 48.8566,
                    "longitude": 2.3522,
                    "heading": 45.0,
                    "speed": 25.0,
                    "accuracy": 5.0
                }
                
                await websocket.send(json.dumps(location_update))
                
                # Attendre l'accusé de réception
                ack_response = await asyncio.wait_for(websocket.recv(), timeout=5)
                ack_data = json.loads(ack_response)
                
                success = ack_data.get("type") == "location_update_ack"
                details = f"Response type: {ack_data.get('type')}"
                
                self.log_test("WebSocket Location Update", success, details)
                return success
                
        except Exception as e:
            self.log_test("WebSocket Location Update", False, str(e))
            return False
    
    def test_websocket_stats(self) -> bool:
        """Tester les statistiques WebSocket."""
        try:
            headers = {"Authorization": f"Bearer {self.token}"}
            response = requests.get(f"{BASE_URL}/api/v1/ws/stats", headers=headers, timeout=10)
            
            success = response.status_code == 200
            
            if success:
                data = response.json()
                drivers = data.get("connected_drivers", 0)
                passengers = data.get("connected_passengers", 0)
                total = data.get("total_connections", 0)
                details = f"Drivers: {drivers}, Passengers: {passengers}, Total: {total}"
            else:
                details = f"Status code: {response.status_code}"
            
            self.log_test("WebSocket Stats", success, details)
            return success
            
        except Exception as e:
            self.log_test("WebSocket Stats", False, str(e))
            return False
    
    async def run_all_tests(self):
        """Exécuter tous les tests."""
        print("🧪 DÉBUT DES TESTS WEBSOCKET ET ETA")
        print("=" * 50)
        
        # Tests HTTP
        if not self.test_application_health():
            print("❌ Application non accessible, arrêt des tests")
            return
        
        if not self.test_user_authentication():
            print("❌ Authentification échouée, arrêt des tests")
            return
        
        self.test_eta_providers()
        self.test_eta_calculation()
        self.test_websocket_stats()
        
        # Tests WebSocket
        await self.test_websocket_connection()
        await self.test_websocket_ping_pong()
        await self.test_websocket_location_update()
        
        # Résumé
        print("\n" + "=" * 50)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 50)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r["success"])
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"Total des tests: {total_tests}")
        print(f"Tests réussis: {successful_tests}")
        print(f"Tests échoués: {total_tests - successful_tests}")
        print(f"Taux de réussite: {success_rate:.1f}%")
        
        if success_rate >= 80:
            print("🎉 TESTS GLOBALEMENT RÉUSSIS")
        elif success_rate >= 60:
            print("⚠️ TESTS PARTIELLEMENT RÉUSSIS")
        else:
            print("❌ TESTS MAJORITAIREMENT ÉCHOUÉS")
        
        return success_rate

async def main():
    """Fonction principale."""
    test_suite = WebSocketETATestSuite()
    success_rate = await test_suite.run_all_tests()
    
    # Sauvegarder les résultats
    with open("test_websocket_eta_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "success_rate": success_rate,
            "results": test_suite.test_results
        }, f, indent=2)
    
    print(f"\n📄 Résultats sauvegardés dans test_websocket_eta_results.json")

if __name__ == "__main__":
    asyncio.run(main())

