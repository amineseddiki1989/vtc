#!/usr/bin/env python3
"""
Reproduire exactement le test Send Custom Notification qui cause l'erreur 422.
"""

import requests
import json

BASE_URL = "http://localhost:8008"

def get_auth_token():
    """Obtenir un token d'authentification valide."""
    
    # Se connecter avec un utilisateur existant
    login_data = {
        "email": "debug_pydantic@test.com",
        "password": "password123"
    }
    
    login_response = requests.post(f"{BASE_URL}/api/v1/auth/login", json=login_data)
    print(f"🔑 Login: {login_response.status_code}")
    
    if login_response.status_code == 200:
        token_data = login_response.json()
        user_id = token_data.get("user", {}).get("id")
        access_token = token_data.get("access_token")
        return access_token, user_id
    
    return None, None

def test_custom_notification():
    """Reproduire exactement le test Send Custom Notification."""
    
    print("🧪 REPRODUCTION EXACTE - Send Custom Notification")
    print("=" * 60)
    
    # Obtenir token et user_id
    token, user_id = get_auth_token()
    if not token:
        print("❌ Impossible d'obtenir un token")
        return
    
    print(f"✅ Token: {token[:20]}...")
    print(f"✅ User ID: {user_id}")
    
    headers = {"Authorization": f"Bearer {token}"}
    
    notification_data = {
        "user_id": user_id,
        "notification_type": "trip_completed",
        "priority": "normal",
        "template_vars": {
            "trip_amount": "25.50",
            "destination": "Aéroport Charles de Gaulle",
            "driver_name": "Jean Dupont"
        }
    }
    
    print(f"\n📤 Payload envoyé:")
    print(json.dumps(notification_data, indent=2))
    
    response = requests.post(
        f"{BASE_URL}/api/v1/notifications/send",
        headers=headers,
        json=notification_data,
        timeout=15
    )
    
    print(f"\n📥 Réponse:")
    print(f"   Status: {response.status_code}")
    print(f"   Headers: {dict(response.headers)}")
    print(f"   Body: {response.text}")
    
    if response.status_code == 422:
        print(f"\n🔍 ANALYSE ERREUR 422:")
        try:
            error_data = response.json()
            print(json.dumps(error_data, indent=2))
        except:
            print(f"   Erreur brute: {response.text}")

if __name__ == "__main__":
    test_custom_notification()

