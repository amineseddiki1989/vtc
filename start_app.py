#!/usr/bin/env python3
"""
Script de démarrage rapide de l'application VTC avec métriques.
"""

import os
import sys
import subprocess
import time
import requests
from pathlib import Path

def check_dependencies():
    """Vérifie que les dépendances sont installées."""
    try:
        import fastapi
        import uvicorn
        import sqlalchemy
        import psutil
        print("✅ Dépendances principales vérifiées")
        return True
    except ImportError as e:
        print(f"❌ Dépendance manquante: {e}")
        print("💡 Lancez: pip install -r requirements.txt")
        return False

def setup_environment():
    """Configure l'environnement si nécessaire."""
    env_file = Path(".env")
    
    if not env_file.exists():
        print("📄 Création du fichier .env minimal...")
        env_content = """APP_NAME=Uber API
ENVIRONMENT=development
DEBUG=true
DATABASE_URL=sqlite:///./uber_api.db
SECRET_KEY=dev-secret-key-change-in-production
JWT_SECRET_KEY=dev-jwt-secret-key-change-in-production
HOST=0.0.0.0
PORT=8000
METRICS_ENABLED=true
"""
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Fichier .env créé")

def create_database():
    """Crée la base de données si nécessaire."""
    try:
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        from app.core.database.base import create_tables
        create_tables()
        print("✅ Base de données initialisée")
        return True
    except Exception as e:
        print(f"❌ Erreur base de données: {e}")
        return False

def start_server():
    """Démarre le serveur de développement."""
    print("🚀 Démarrage du serveur...")
    
    try:
        # Démarrer avec uvicorn
        cmd = [
            sys.executable, "-m", "uvicorn",
            "app.main:app",
            "--host", "0.0.0.0",
            "--port", "8000",
            "--reload",
            "--log-level", "info"
        ]
        
        print("📡 Serveur démarré sur: http://localhost:8000")
        print("📊 Métriques disponibles sur: http://localhost:8000/api/v1/metrics/summary")
        print("📚 Documentation API: http://localhost:8000/docs")
        print("\n🛑 Appuyez sur Ctrl+C pour arrêter")
        
        subprocess.run(cmd)
        
    except KeyboardInterrupt:
        print("\n👋 Arrêt du serveur...")
    except Exception as e:
        print(f"❌ Erreur lors du démarrage: {e}")

def test_server():
    """Teste que le serveur fonctionne."""
    print("🧪 Test du serveur...")
    
    max_attempts = 10
    for attempt in range(max_attempts):
        try:
            response = requests.get("http://localhost:8000/health", timeout=5)
            if response.status_code == 200:
                print("✅ Serveur opérationnel")
                return True
        except requests.exceptions.RequestException:
            pass
        
        if attempt < max_attempts - 1:
            print(f"⏳ Tentative {attempt + 1}/{max_attempts}...")
            time.sleep(2)
    
    print("❌ Serveur non accessible")
    return False

def show_quick_start_guide():
    """Affiche un guide de démarrage rapide."""
    print("\n" + "="*60)
    print("🎯 GUIDE DE DÉMARRAGE RAPIDE")
    print("="*60)
    
    print("\n📋 Endpoints principaux:")
    print("• Santé:        GET  /health")
    print("• Documentation: GET  /docs")
    print("• Métriques:    GET  /api/v1/metrics/summary")
    print("• Auth:         POST /api/v1/auth/login")
    print("• Courses:      GET  /api/v1/trips")
    
    print("\n🔐 Authentification:")
    print("1. Créer un utilisateur admin")
    print("2. Se connecter pour obtenir un token")
    print("3. Utiliser le token pour accéder aux métriques")
    
    print("\n📊 Tester les métriques:")
    print("curl http://localhost:8000/api/v1/metrics/summary")
    
    print("\n🧪 Lancer les tests:")
    print("python test_metrics_collection.py")
    
    print("\n📖 Documentation complète:")
    print("Voir README_METRICS.md")

def main():
    """Fonction principale."""
    print("🚀 Démarrage de l'application VTC avec métriques")
    print("="*50)
    
    # Vérifications préliminaires
    if not check_dependencies():
        return 1
    
    # Configuration
    setup_environment()
    
    # Base de données
    if not create_database():
        return 1
    
    # Guide de démarrage
    show_quick_start_guide()
    
    # Demander confirmation
    print("\n" + "="*50)
    start_choice = input("🚀 Démarrer le serveur maintenant ? (Y/n): ").lower()
    
    if start_choice in ['', 'y', 'yes', 'oui']:
        start_server()
    else:
        print("👋 Serveur non démarré. Lancez manuellement avec:")
        print("python -m uvicorn app.main:app --reload")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

