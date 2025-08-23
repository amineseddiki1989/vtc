#!/usr/bin/env python3
"""
Script de debug spécialisé pour analyser les erreurs 422 Pydantic.
"""

import requests
import json
import sys

BASE_URL = "http://localhost:8007"

def get_auth_token():
    """Obtenir un token d'authentification valide."""
    
    # D'abord créer un utilisateur
    register_data = {
        "email": "debug_pydantic@test.com",
        "password": "password123",
        "first_name": "Debug",
        "last_name": "Pydantic",
        "phone": "+33123456789"
    }
    
    register_response = requests.post(f"{BASE_URL}/api/v1/auth/register", json=register_data)
    print(f"📝 Register: {register_response.status_code}")
    
    # Puis se connecter
    login_data = {
        "email": "debug_pydantic@test.com",
        "password": "password123"
    }
    
    login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    print(f"🔑 Login: {login_response.status_code}")
    
    if login_response.status_code == 200:
        token_data = login_response.json()
        return token_data.get("access_token")
    
    return None

def debug_pydantic_errors():
    """Debug approfondi des erreurs 422 Pydantic."""
    
    print("🔍 DEBUG APPROFONDI - ERREURS 422 PYDANTIC")
    print("=" * 60)
    
    # Obtenir un token valide
    token = get_auth_token()
    if not token:
        print("❌ Impossible d'obtenir un token d'authentification")
        return
    
    print(f"✅ Token obtenu: {token[:20]}...")
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {token}"
    }
    
    # Test 1: Payload minimal
    print(f"\n🧪 TEST 1: Payload minimal")
    payload1 = {
        "user_id": "2bc0d110-997f-4e3c-b9a4-2b81d3acf1c1",
        "notification_type": "driver_found"
    }
    
    response1 = requests.post(f"{BASE_URL}/api/v1/notifications/send", json=payload1, headers=headers)
    print(f"   Status: {response1.status_code}")
    if response1.status_code == 422:
        print(f"   Erreur 422: {response1.text}")
    elif response1.status_code == 200:
        print(f"   Succès: {response1.json()}")
    else:
        print(f"   Autre erreur: {response1.text}")
    
    # Test 2: Payload avec priority
    print(f"\n🧪 TEST 2: Payload avec priority")
    payload2 = {
        "user_id": "2bc0d110-997f-4e3c-b9a4-2b81d3acf1c1",
        "notification_type": "driver_found",
        "priority": "normal"
    }
    
    response2 = requests.post(f"{BASE_URL}/api/v1/notifications/send", json=payload2, headers=headers)
    print(f"   Status: {response2.status_code}")
    if response2.status_code == 422:
        print(f"   Erreur 422: {response2.text}")
    elif response2.status_code == 200:
        print(f"   Succès: {response2.json()}")
    else:
        print(f"   Autre erreur: {response2.text}")
    
    # Test 3: Payload complet avec template_vars
    print(f"\n🧪 TEST 3: Payload complet avec template_vars")
    payload3 = {
        "user_id": "2bc0d110-997f-4e3c-b9a4-2b81d3acf1c1",
        "notification_type": "driver_found",
        "priority": "normal",
        "template_vars": {
            "driver_name": "Jean Dupont",
            "eta_minutes": "5",
            "vehicle_info": "Peugeot 308"
        }
    }
    
    response3 = requests.post(f"{BASE_URL}/api/v1/notifications/send", json=payload3, headers=headers)
    print(f"   Status: {response3.status_code}")
    if response3.status_code == 422:
        print(f"   Erreur 422: {response3.text}")
        # Analyser l'erreur en détail
        try:
            error_data = response3.json()
            print(f"   Détails erreur: {json.dumps(error_data, indent=2)}")
        except:
            print(f"   Erreur brute: {response3.text}")
    elif response3.status_code == 200:
        print(f"   Succès: {response3.json()}")
    else:
        print(f"   Autre erreur: {response3.text}")
    
    # Test 4: Types invalides
    print(f"\n🧪 TEST 4: Types invalides")
    payload4 = {
        "user_id": "2bc0d110-997f-4e3c-b9a4-2b81d3acf1c1",
        "notification_type": "invalid_type",
        "priority": "invalid_priority"
    }
    
    response4 = requests.post(f"{BASE_URL}/api/v1/notifications/send", json=payload4, headers=headers)
    print(f"   Status: {response4.status_code}")
    if response4.status_code == 422:
        print(f"   Erreur 422: {response4.text}")
        try:
            error_data = response4.json()
            print(f"   Détails erreur: {json.dumps(error_data, indent=2)}")
        except:
            print(f"   Erreur brute: {response4.text}")

if __name__ == "__main__":
    debug_pydantic_errors()

