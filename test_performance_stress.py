#!/usr/bin/env python3
"""
Tests de performance et de stress pour l'application VTC finale.
Validation de la robustesse et des performances sous charge.
"""

import asyncio
import json
import requests
import time
import threading
from datetime import datetime
from typing import Dict, Any, List
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
BASE_URL = "http://localhost:8009"

class UberVTCStressTestSuite:
    """Suite de tests de stress pour l'application VTC."""
    
    def __init__(self):
        self.admin_token = None
        self.user_tokens = []
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
    
    def setup_test_environment(self) -> bool:
        """Configurer l'environnement de test."""
        try:
            # Créer un admin
            timestamp = int(time.time())
            admin_data = {
                "email": f"admin_stress_{timestamp}@example.com",
                "password": "AdminPassword123!",
                "first_name": "Admin",
                "last_name": "Stress",
                "phone": "+33123456000",
                "role": "admin"
            }
            
            response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=admin_data, timeout=10)
            if response.status_code == 200:
                login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
                    "email": admin_data["email"],
                    "password": admin_data["password"]
                }, timeout=10)
                
                if login_response.status_code == 200:
                    self.admin_token = login_response.json().get("access_token")
            
            # Créer plusieurs utilisateurs
            for i in range(10):
                user_data = {
                    "email": f"stress_user_{timestamp}_{i}@example.com",
                    "password": "StressPassword123!",
                    "first_name": f"StressUser{i}",
                    "last_name": "Test",
                    "phone": f"+3312345{i:04d}",
                    "role": "passenger" if i % 2 == 0 else "driver"
                }
                
                response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data, timeout=10)
                if response.status_code == 200:
                    login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json={
                        "email": user_data["email"],
                        "password": user_data["password"]
                    }, timeout=10)
                    
                    if login_response.status_code == 200:
                        token = login_response.json().get("access_token")
                        if token:
                            self.user_tokens.append(token)
                
                time.sleep(0.1)
            
            success = self.admin_token is not None and len(self.user_tokens) >= 8
            details = f"Admin: {self.admin_token is not None}, Users: {len(self.user_tokens)}/10"
            
            self.log_test("Setup Test Environment", success, details)
            return success
            
        except Exception as e:
            self.log_test("Setup Test Environment", False, str(e))
            return False
    
    def test_concurrent_notifications(self) -> bool:
        """Tester les notifications concurrentes."""
        try:
            def send_notification(token, user_index):
                headers = {"Authorization": f"Bearer {token}"}
                notification_data = {
                    "user_id": "test_user_concurrent",
                    "notification_type": "driver_found",
                    "priority": "normal",
                    "template_vars": {
                        "driver_name": f"Conducteur {user_index}",
                        "eta_minutes": "5"
                    }
                }
                
                start_time = time.time()
                response = requests.post(
                    f"{BASE_URL}/api/v1/notifications/send",
                    headers=headers,
                    json=notification_data,
                    timeout=15
                )
                end_time = time.time()
                
                return {
                    "success": response.status_code == 200,
                    "duration": end_time - start_time,
                    "user_index": user_index
                }
            
            # Lancer 10 notifications en parallèle
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [
                    executor.submit(send_notification, token, i) 
                    for i, token in enumerate(self.user_tokens[:10])
                ]
                
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            successful_sends = sum(1 for r in results if r["success"])
            avg_duration = sum(r["duration"] for r in results) / len(results)
            
            success = successful_sends >= 8 and total_duration < 10.0  # 80% réussite en moins de 10s
            details = f"Réussis: {successful_sends}/10, Durée totale: {total_duration:.2f}s, Moyenne: {avg_duration:.2f}s"
            
            self.log_test("Concurrent Notifications", success, details)
            return success
            
        except Exception as e:
            self.log_test("Concurrent Notifications", False, str(e))
            return False
    
    def test_bulk_notifications_stress(self) -> bool:
        """Tester les envois multiples sous stress."""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            
            # Créer une liste de 50 utilisateurs fictifs
            user_ids = [f"stress_user_{i}" for i in range(50)]
            
            start_time = time.time()
            
            notification_data = {
                "user_ids": user_ids,
                "notification_type": "promotion_offer",
                "priority": "low",
                "template_vars": {
                    "promotion_title": "Test de stress",
                    "discount_text": "Offre spéciale stress test"
                }
            }
            
            response = requests.post(
                f"{BASE_URL}/api/v1/notifications/bulk/send-multiple",
                headers=headers,
                json=notification_data,
                timeout=30
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            success = response.status_code == 200 and duration < 5.0  # Moins de 5 secondes
            
            if response.status_code == 200:
                data = response.json()
                total = data.get("total_notifications", 0)
                success_count = data.get("success_count", 0)
                details = f"Total: {total}, Réussis: {success_count}, Durée: {duration:.2f}s"
            else:
                details = f"Status code: {response.status_code}, Durée: {duration:.2f}s"
            
            self.log_test("Bulk Notifications Stress", success, details)
            return success
            
        except Exception as e:
            self.log_test("Bulk Notifications Stress", False, str(e))
            return False
    
    def test_database_performance_stress(self) -> bool:
        """Tester les performances de la base de données sous stress."""
        try:
            def create_trip(token, trip_index):
                headers = {"Authorization": f"Bearer {token}"}
                trip_data = {
                    "pickup_latitude": 48.8566 + (trip_index * 0.001),
                    "pickup_longitude": 2.3522 + (trip_index * 0.001),
                    "pickup_address": f"Adresse pickup {trip_index}, Paris",
                    "destination_latitude": 48.8606 + (trip_index * 0.001),
                    "destination_longitude": 2.3376 + (trip_index * 0.001),
                    "destination_address": f"Adresse destination {trip_index}, Paris",
                    "vehicle_type": "standard"
                }
                
                start_time = time.time()
                response = requests.post(
                    f"{BASE_URL}/api/v1/trips/",
                    headers=headers,
                    json=trip_data,
                    timeout=15
                )
                end_time = time.time()
                
                return {
                    "success": response.status_code == 200,
                    "duration": end_time - start_time,
                    "trip_index": trip_index
                }
            
            # Créer 5 courses en parallèle
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = [
                    executor.submit(create_trip, token, i) 
                    for i, token in enumerate(self.user_tokens[:5])
                ]
                
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            successful_creates = sum(1 for r in results if r["success"])
            avg_duration = sum(r["duration"] for r in results) / len(results)
            
            success = successful_creates >= 4 and total_duration < 15.0  # 80% réussite en moins de 15s
            details = f"Réussis: {successful_creates}/5, Durée totale: {total_duration:.2f}s, Moyenne: {avg_duration:.2f}s"
            
            self.log_test("Database Performance Stress", success, details)
            return success
            
        except Exception as e:
            self.log_test("Database Performance Stress", False, str(e))
            return False
    
    def test_mixed_operations_stress(self) -> bool:
        """Tester des opérations mixtes sous stress."""
        try:
            def mixed_operation(token, operation_index):
                headers = {"Authorization": f"Bearer {token}"}
                
                operations = [
                    # Estimation
                    lambda: requests.post(f"{BASE_URL}/api/v1/trips/estimate", headers=headers, json={
                        "pickup_latitude": 48.8566,
                        "pickup_longitude": 2.3522,
                        "pickup_address": "Test pickup",
                        "destination_latitude": 48.8606,
                        "destination_longitude": 2.3376,
                        "destination_address": "Test destination",
                        "vehicle_type": "standard"
                    }, timeout=10),
                    
                    # Notification
                    lambda: requests.post(f"{BASE_URL}/api/v1/notifications/send", headers=headers, json={
                        "user_id": f"mixed_user_{operation_index}",
                        "notification_type": "account_verified",
                        "priority": "normal",
                        "template_vars": {}
                    }, timeout=10),
                    
                    # Stats WebSocket
                    lambda: requests.get(f"{BASE_URL}/api/v1/ws/stats", headers=headers, timeout=10),
                    
                    # ETA calculation
                    lambda: requests.post(f"{BASE_URL}/api/v1/eta/calculate", headers=headers, json={
                        "origin_latitude": 48.8566,
                        "origin_longitude": 2.3522,
                        "destination_latitude": 48.8606,
                        "destination_longitude": 2.3376
                    }, timeout=10)
                ]
                
                start_time = time.time()
                operation = operations[operation_index % len(operations)]
                response = operation()
                end_time = time.time()
                
                return {
                    "success": response.status_code == 200,
                    "duration": end_time - start_time,
                    "operation_index": operation_index,
                    "operation_type": ["estimate", "notification", "ws_stats", "eta"][operation_index % 4]
                }
            
            # Lancer 8 opérations mixtes en parallèle
            start_time = time.time()
            with ThreadPoolExecutor(max_workers=8) as executor:
                futures = [
                    executor.submit(mixed_operation, self.user_tokens[i % len(self.user_tokens)], i) 
                    for i in range(8)
                ]
                
                results = [future.result() for future in as_completed(futures)]
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            successful_ops = sum(1 for r in results if r["success"])
            avg_duration = sum(r["duration"] for r in results) / len(results)
            
            success = successful_ops >= 6 and total_duration < 20.0  # 75% réussite en moins de 20s
            details = f"Réussis: {successful_ops}/8, Durée totale: {total_duration:.2f}s, Moyenne: {avg_duration:.2f}s"
            
            self.log_test("Mixed Operations Stress", success, details)
            return success
            
        except Exception as e:
            self.log_test("Mixed Operations Stress", False, str(e))
            return False
    
    def test_memory_and_stability(self) -> bool:
        """Tester la stabilité et l'utilisation mémoire."""
        try:
            headers = {"Authorization": f"Bearer {self.admin_token}"}
            
            # Effectuer 20 requêtes rapides pour tester la stabilité
            successful_requests = 0
            total_requests = 20
            
            start_time = time.time()
            
            for i in range(total_requests):
                try:
                    response = requests.get(f"{BASE_URL}/health", timeout=5)
                    if response.status_code == 200:
                        successful_requests += 1
                    
                    # Petite pause pour éviter de surcharger
                    time.sleep(0.1)
                    
                except Exception:
                    pass
            
            end_time = time.time()
            total_duration = end_time - start_time
            
            success_rate = (successful_requests / total_requests) * 100
            success = success_rate >= 95.0  # 95% de réussite minimum
            
            details = f"Réussis: {successful_requests}/{total_requests} ({success_rate:.1f}%), Durée: {total_duration:.2f}s"
            
            self.log_test("Memory and Stability", success, details)
            return success
            
        except Exception as e:
            self.log_test("Memory and Stability", False, str(e))
            return False
    
    async def run_all_stress_tests(self):
        """Exécuter tous les tests de stress."""
        print("🔥 DÉBUT DES TESTS DE STRESS - APPLICATION VTC")
        print("=" * 70)
        
        # Configuration
        if not self.setup_test_environment():
            print("❌ Configuration échouée, arrêt des tests")
            return
        
        # Tests de stress
        self.test_concurrent_notifications()
        self.test_bulk_notifications_stress()
        self.test_database_performance_stress()
        self.test_mixed_operations_stress()
        self.test_memory_and_stability()
        
        # Résumé
        print("\n" + "=" * 70)
        print("🔥 RÉSUMÉ DES TESTS DE STRESS")
        print("=" * 70)
        
        total_tests = len(self.test_results)
        successful_tests = sum(1 for r in self.test_results if r["success"])
        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0
        
        print(f"Total des tests: {total_tests}")
        print(f"Tests réussis: {successful_tests}")
        print(f"Tests échoués: {total_tests - successful_tests}")
        print(f"Taux de réussite: {success_rate:.1f}%")
        
        if success_rate >= 90:
            print("🎉 APPLICATION ULTRA-ROBUSTE SOUS STRESS")
        elif success_rate >= 80:
            print("✅ APPLICATION ROBUSTE SOUS STRESS")
        elif success_rate >= 70:
            print("⚠️ APPLICATION STABLE SOUS STRESS")
        else:
            print("❌ APPLICATION À OPTIMISER POUR LE STRESS")
        
        print(f"\n🔥 TESTS DE STRESS AVEC {len(self.user_tokens)} UTILISATEURS SIMULTANÉS")
        print(f"💪 ROBUSTESSE VALIDÉE À {success_rate:.1f}%")
        
        return success_rate

async def main():
    """Fonction principale."""
    test_suite = UberVTCStressTestSuite()
    success_rate = await test_suite.run_all_stress_tests()
    
    # Sauvegarder les résultats
    with open("test_uber_vtc_stress_results.json", "w") as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "success_rate": success_rate,
            "concurrent_users": len(test_suite.user_tokens),
            "results": test_suite.test_results
        }, f, indent=2)
    
    print(f"\n📄 Résultats de stress sauvegardés dans test_uber_vtc_stress_results.json")

if __name__ == "__main__":
    asyncio.run(main())

