#!/usr/bin/env python3
"""
Test simple de validation de l'application VTC.
"""

import requests
import json
import time
import sys

def test_application():
    """Test de base de l'application."""
    base_url = "http://localhost:8000"
    
    print("🧪 Tests de validation de l'application VTC")
    print("=" * 50)
    
    # Test 1: Health check fiscal
    print("1. Test du health check fiscal...")
    try:
        response = requests.get(f"{base_url}/api/v1/fiscal/health", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Health check fiscal: {data.get('status', 'unknown')}")
        else:
            print(f"   ❌ Health check fiscal échoué: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erreur health check fiscal: {e}")
    
    # Test 2: Calcul fiscal
    print("2. Test du calcul fiscal...")
    try:
        fiscal_data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        response = requests.post(f"{base_url}/api/v1/fiscal/calculate", 
                               json=fiscal_data, timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Calcul fiscal: {data.get('total_amount', 'N/A')} DZD")
        else:
            print(f"   ❌ Calcul fiscal échoué: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erreur calcul fiscal: {e}")
    
    # Test 3: Monitoring dashboard
    print("3. Test du dashboard monitoring...")
    try:
        response = requests.get(f"{base_url}/api/v1/monitoring/dashboard", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Dashboard monitoring: {data.get('system_health', {}).get('status', 'unknown')}")
        else:
            print(f"   ❌ Dashboard monitoring échoué: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erreur dashboard monitoring: {e}")
    
    # Test 4: Taux fiscaux
    print("4. Test des taux fiscaux...")
    try:
        response = requests.get(f"{base_url}/api/v1/fiscal/rates", timeout=5)
        if response.status_code == 200:
            data = response.json()
            print(f"   ✅ Taux fiscaux: TVA {data.get('tva_rates', {}).get('standard', 'N/A')}")
        else:
            print(f"   ❌ Taux fiscaux échoué: {response.status_code}")
    except Exception as e:
        print(f"   ❌ Erreur taux fiscaux: {e}")
    
    print("\n🎯 Tests de validation terminés")

if __name__ == "__main__":
    test_application()
