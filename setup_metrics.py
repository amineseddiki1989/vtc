#!/usr/bin/env python3
"""
Script de configuration et d'initialisation du système de métriques.
"""

import os
import sys
import subprocess
from pathlib import Path

def install_dependencies():
    """Installe les dépendances nécessaires."""
    print("📦 Installation des dépendances...")
    
    try:
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], 
                      check=True, capture_output=True, text=True)
        print("✅ Dépendances installées avec succès")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Erreur lors de l'installation des dépendances: {e}")
        print(f"Sortie d'erreur: {e.stderr}")
        return False

def create_database_tables():
    """Crée les tables de base de données."""
    print("🗄️ Création des tables de base de données...")
    
    try:
        # Ajouter le répertoire de l'application au path
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))
        
        from app.core.database.base import create_tables
        create_tables()
        
        print("✅ Tables de base de données créées")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création des tables: {e}")
        return False

def test_metrics_system():
    """Teste le système de métriques."""
    print("🧪 Test du système de métriques...")
    
    try:
        result = subprocess.run([sys.executable, "test_metrics_collection.py"], 
                              capture_output=True, text=True, timeout=60)
        
        if result.returncode == 0:
            print("✅ Tests des métriques réussis")
            print("Résultats des tests:")
            print(result.stdout)
            return True
        else:
            print("❌ Échec des tests des métriques")
            print("Erreurs:")
            print(result.stderr)
            return False
            
    except subprocess.TimeoutExpired:
        print("⏰ Timeout lors des tests (plus de 60 secondes)")
        return False
    except Exception as e:
        print(f"❌ Erreur lors des tests: {e}")
        return False

def create_env_file():
    """Crée un fichier .env avec la configuration par défaut."""
    env_file = Path(".env")
    
    if env_file.exists():
        print("📄 Fichier .env existant trouvé")
        return True
    
    print("📄 Création du fichier .env...")
    
    env_content = """# Configuration de l'application VTC
APP_NAME=Uber API
APP_VERSION=1.0.0
ENVIRONMENT=development
DEBUG=true

# Base de données
DATABASE_URL=sqlite:///./uber_api.db

# Sécurité
SECRET_KEY=your-secret-key-here-change-in-production
JWT_SECRET_KEY=your-jwt-secret-key-here-change-in-production
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=30
REFRESH_TOKEN_EXPIRE_DAYS=7

# Serveur
HOST=0.0.0.0
PORT=8000
LOG_LEVEL=info

# Métriques
METRICS_ENABLED=true
METRICS_BUFFER_SIZE=1000
METRICS_FLUSH_INTERVAL=30
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Fichier .env créé")
        return True
    except Exception as e:
        print(f"❌ Erreur lors de la création du fichier .env: {e}")
        return False

def check_system_requirements():
    """Vérifie les prérequis système."""
    print("🔍 Vérification des prérequis système...")
    
    # Vérifier Python
    if sys.version_info < (3, 8):
        print("❌ Python 3.8+ requis")
        return False
    
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    
    # Vérifier pip
    try:
        subprocess.run([sys.executable, "-m", "pip", "--version"], 
                      check=True, capture_output=True)
        print("✅ pip disponible")
    except subprocess.CalledProcessError:
        print("❌ pip non disponible")
        return False
    
    return True

def main():
    """Fonction principale de configuration."""
    print("🚀 Configuration du système de métriques VTC")
    print("=" * 50)
    
    # Vérifier les prérequis
    if not check_system_requirements():
        print("💥 Prérequis système non satisfaits")
        return 1
    
    # Créer le fichier .env
    if not create_env_file():
        print("💥 Échec de la création du fichier .env")
        return 1
    
    # Installer les dépendances
    if not install_dependencies():
        print("💥 Échec de l'installation des dépendances")
        return 1
    
    # Créer les tables
    if not create_database_tables():
        print("💥 Échec de la création des tables")
        return 1
    
    # Tester le système
    print("\n🧪 Lancement des tests (optionnel)...")
    test_choice = input("Voulez-vous lancer les tests du système de métriques ? (y/N): ").lower()
    
    if test_choice in ['y', 'yes', 'oui']:
        if not test_metrics_system():
            print("⚠️ Tests échoués, mais l'installation peut continuer")
    
    print("\n" + "=" * 50)
    print("🎉 Configuration terminée avec succès !")
    print("\n📋 Prochaines étapes :")
    print("1. Modifiez le fichier .env avec vos paramètres")
    print("2. Lancez l'application avec: python -m app.main")
    print("3. Accédez aux métriques sur: http://localhost:8000/api/v1/metrics/summary")
    print("4. Documentation API: http://localhost:8000/docs")
    
    return 0

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

