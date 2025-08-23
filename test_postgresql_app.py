#!/usr/bin/env python3
"""Test de l'application VTC avec PostgreSQL"""

import os
import sys
import requests
import time
import subprocess
from threading import Thread

# Configuration PostgreSQL
os.environ['DATABASE_URL'] = 'postgresql://uber_user:uber_password_2024@localhost:5432/uber_vtc'
os.environ['POSTGRES_HOST'] = 'localhost'
os.environ['POSTGRES_PORT'] = '5432'
os.environ['POSTGRES_DB'] = 'uber_vtc'
os.environ['POSTGRES_USER'] = 'uber_user'
os.environ['POSTGRES_PASSWORD'] = 'uber_password_2024'

def start_app():
    """Démarrer l'application en arrière-plan"""
    try:
        subprocess.run([sys.executable, 'start_app.py'], check=True)
    except Exception as e:
        print(f"❌ Erreur démarrage app: {e}")

def test_endpoints():
    """Tester les endpoints de l'application"""
    base_url = "http://localhost:8000"
    
    # Attendre que l'app démarre
    print("⏳ Attente démarrage application...")
    time.sleep(5)
    
    tests = [
        ("Health Check", f"{base_url}/health"),
        ("API Docs", f"{base_url}/docs"),
        ("Metrics", f"{base_url}/api/v1/admin/metrics"),
    ]
    
    results = []
    for name, url in tests:
        try:
            response = requests.get(url, timeout=10)
            status = "✅ SUCCÈS" if response.status_code == 200 else f"⚠️ {response.status_code}"
            results.append(f"{name}: {status}")
        except Exception as e:
            results.append(f"{name}: ❌ ERREUR - {e}")
    
    return results

if __name__ == "__main__":
    print("🐘 TEST APPLICATION VTC AVEC POSTGRESQL")
    print("=" * 50)
    
    # Démarrer l'app en arrière-plan
    app_thread = Thread(target=start_app, daemon=True)
    app_thread.start()
    
    # Tester les endpoints
    results = test_endpoints()
    
    print("\n📊 RÉSULTATS DES TESTS:")
    for result in results:
        print(f"  {result}")
    
    print("\n🎯 Test terminé !")

