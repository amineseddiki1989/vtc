#!/usr/bin/env python3
"""
Test de démonstration de l'API Uber fonctionnelle.
"""

import requests
import time
import threading
from app.main import app
import uvicorn

def start_server():
    """Démarre le serveur en arrière-plan."""
    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="error")

def test_api():
    """Teste les endpoints de l'API."""
    base_url = "http://127.0.0.1:8000"
    
    # Attendre que le serveur démarre
    time.sleep(2)
    
    print("🚀 Test de l'API Uber fonctionnelle")
    print("=" * 50)
    
    try:
        # Test 1: Endpoint racine
        print("1. Test de l'endpoint racine...")
        response = requests.get(f"{base_url}/")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200
        print("   ✅ OK")
        
        # Test 2: Health check
        print("\n2. Test du health check...")
        response = requests.get(f"{base_url}/health")
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200
        print("   ✅ OK")
        
        # Test 3: Inscription
        print("\n3. Test d'inscription...")
        user_data = {
            "email": "test@example.com",
            "password": "SecurePass123"
        }
        response = requests.post(f"{base_url}/api/v1/auth/register", json=user_data)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200
        print("   ✅ OK")
        
        # Test 4: Connexion
        print("\n4. Test de connexion...")
        login_data = {
            "email": "test@example.com",
            "password": "SecurePass123"
        }
        response = requests.post(f"{base_url}/api/v1/auth/login", json=login_data)
        print(f"   Status: {response.status_code}")
        token_data = response.json()
        print(f"   Response: {token_data}")
        assert response.status_code == 200
        assert "access_token" in token_data
        print("   ✅ OK")
        
        # Test 5: Endpoint protégé
        print("\n5. Test d'endpoint protégé...")
        headers = {"Authorization": f"Bearer {token_data['access_token']}"}
        response = requests.get(f"{base_url}/api/v1/auth/me", headers=headers)
        print(f"   Status: {response.status_code}")
        print(f"   Response: {response.json()}")
        assert response.status_code == 200
        print("   ✅ OK")
        
        print("\n🎉 Tous les tests sont passés ! L'API est fonctionnelle.")
        
    except Exception as e:
        print(f"\n❌ Erreur lors du test: {e}")
        return False
    
    return True

if __name__ == "__main__":
    # Démarrer le serveur dans un thread séparé
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    # Lancer les tests
    success = test_api()
    
    if success:
        print("\n✅ L'application Uber API est entièrement fonctionnelle !")
    else:
        print("\n❌ Des problèmes ont été détectés.")

