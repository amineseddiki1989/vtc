#!/usr/bin/env python3
"""
Script de test final pour validation complète de l'application VTC.
"""

import requests
import json
from datetime import datetime

# Configuration de test
BASE_URL = "http://localhost:8001"

def test_complete_workflow():
    """Test du workflow complet de l'application"""
    
    print("🚀 TEST FINAL - VALIDATION COMPLÈTE VTC")
    print("=" * 50)
    
    results = []
    
    # Test 1: Health Check
    print("1. Test Health Check...")
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        success = response.status_code == 200
        print(f"   {'✅' if success else '❌'} Health Check: {response.status_code}")
        results.append(("Health Check", success))
    except Exception as e:
        print(f"   ❌ Health Check: Erreur - {e}")
        results.append(("Health Check", False))
    
    # Test 2: Création utilisateur passager
    print("\n2. Test Création Passager...")
    try:
        user_data = {
            "email": "final_passenger@test.com",
            "password": "password123",
            "role": "passenger",
            "first_name": "Final",
            "last_name": "Passenger",
            "phone": "+33123456789"
        }
        response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=user_data, timeout=10)
        success = response.status_code in [200, 201]
        print(f"   {'✅' if success else '❌'} Création Passager: {response.status_code}")
        if success:
            passenger_data = response.json()
            passenger_id = passenger_data.get("id")
        results.append(("Création Passager", success))
    except Exception as e:
        print(f"   ❌ Création Passager: Erreur - {e}")
        results.append(("Création Passager", False))
        return results
    
    # Test 3: Authentification passager
    print("\n3. Test Authentification Passager...")
    try:
        login_data = {"email": "final_passenger@test.com", "password": "password123"}
        response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data, timeout=10)
        success = response.status_code == 200
        print(f"   {'✅' if success else '❌'} Authentification: {response.status_code}")
        if success:
            token_data = response.json()
            passenger_token = token_data.get("access_token")
        results.append(("Authentification Passager", success))
    except Exception as e:
        print(f"   ❌ Authentification: Erreur - {e}")
        results.append(("Authentification Passager", False))
        return results
    
    # Test 4: Estimation de course
    print("\n4. Test Estimation Course...")
    try:
        headers = {"Authorization": f"Bearer {passenger_token}"}
        trip_data = {
            "pickup_latitude": 48.8566,
            "pickup_longitude": 2.3522,
            "pickup_address": "Place de la Concorde, Paris",
            "destination_latitude": 48.8584,
            "destination_longitude": 2.2945,
            "destination_address": "Tour Eiffel, Paris",
            "vehicle_type": "standard"
        }
        response = requests.post(f"{BASE_URL}/api/v1/trips/estimate", json=trip_data, headers=headers, timeout=10)
        success = response.status_code == 200
        print(f"   {'✅' if success else '❌'} Estimation: {response.status_code}")
        if success:
            estimate = response.json()
            print(f"   💰 Prix estimé: {estimate.get('price', 'N/A')}€")
        results.append(("Estimation Course", success))
    except Exception as e:
        print(f"   ❌ Estimation: Erreur - {e}")
        results.append(("Estimation Course", False))
    
    # Test 5: Création de course
    print("\n5. Test Création Course...")
    try:
        headers = {"Authorization": f"Bearer {passenger_token}"}
        response = requests.post(f"{BASE_URL}/api/v1/trips/", json=trip_data, headers=headers, timeout=10)
        success = response.status_code in [200, 201]
        print(f"   {'✅' if success else '❌'} Création Course: {response.status_code}")
        if success:
            trip = response.json()
            trip_id = trip.get("id")
            print(f"   🚗 Course créée: {trip_id}")
        else:
            print(f"   📄 Réponse: {response.text[:200]}")
        results.append(("Création Course", success))
    except Exception as e:
        print(f"   ❌ Création Course: Erreur - {e}")
        results.append(("Création Course", False))
    
    # Test 6: Liste des courses
    print("\n6. Test Liste Courses...")
    try:
        headers = {"Authorization": f"Bearer {passenger_token}"}
        response = requests.get(f"{BASE_URL}/api/v1/trips/", headers=headers, timeout=10)
        success = response.status_code == 200
        print(f"   {'✅' if success else '❌'} Liste Courses: {response.status_code}")
        if success:
            trips = response.json()
            trip_count = len(trips.get("trips", []))
            print(f"   📋 Nombre de courses: {trip_count}")
        results.append(("Liste Courses", success))
    except Exception as e:
        print(f"   ❌ Liste Courses: Erreur - {e}")
        results.append(("Liste Courses", False))
    
    # Résumé final
    print("\n" + "=" * 50)
    passed = sum(1 for _, success in results if success)
    total = len(results)
    print(f"📊 RÉSULTATS FINAUX: {passed}/{total} tests réussis")
    
    if passed == total:
        print("🎉 TOUS LES TESTS SONT PASSÉS!")
        print("✅ Application 100% fonctionnelle")
    else:
        print(f"⚠️  {total - passed} test(s) échoué(s)")
        print("❌ Corrections nécessaires")
    
    # Sauvegarder les résultats
    with open("test_final_results.json", 'w') as f:
        json.dump({
            "timestamp": datetime.now().isoformat(),
            "total_tests": total,
            "passed_tests": passed,
            "success_rate": f"{(passed/total)*100:.1f}%",
            "results": [{"test": test, "success": success} for test, success in results]
        }, f, indent=2)
    
    print(f"📄 Résultats sauvegardés dans test_final_results.json")
    
    return passed == total

if __name__ == "__main__":
    success = test_complete_workflow()
    exit(0 if success else 1)

