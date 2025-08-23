#!/bin/bash

# Script de déploiement simplifié - VTC API v3.0.0
# Usage: ./deploy_simple.sh

set -e  # Arrêter en cas d'erreur

echo "🚀 Déploiement VTC API v3.0.0"
echo "================================"

# Vérification de l'environnement Python
if ! command -v python3 &> /dev/null; then
    echo "❌ Python 3 n'est pas installé"
    exit 1
fi

# Création de l'environnement virtuel si nécessaire
if [ ! -d "venv" ]; then
    echo "📦 Création de l'environnement virtuel..."
    python3 -m venv venv
fi

# Activation de l'environnement virtuel
echo "🔧 Activation de l'environnement virtuel..."
source venv/bin/activate

# Installation des dépendances
echo "📥 Installation des dépendances..."
pip install --upgrade pip
pip install -r requirements-production.txt

# Configuration de l'environnement
if [ ! -f ".env" ]; then
    echo "⚙️ Configuration de l'environnement..."
    cp .env.production .env
    echo "✏️ Modifiez le fichier .env avec vos paramètres avant de continuer"
    echo "📝 Notamment les clés secrètes et les URLs de base de données"
fi

# Initialisation de la base de données
echo "🗃️ Initialisation de la base de données..."
python -c "
from app.core.database.session import create_tables
try:
    create_tables()
    print('✅ Base de données initialisée')
except Exception as e:
    print(f'⚠️ Erreur base de données: {e}')
"

# Test de l'application
echo "🧪 Test de l'application..."
python -c "
from app.main import app
print('✅ Application chargée avec succès')
"

echo ""
echo "✅ Déploiement terminé !"
echo ""
echo "🚀 Pour démarrer l'application :"
echo "   source venv/bin/activate"
echo "   uvicorn app.main:app --host 0.0.0.0 --port 8000"
echo ""
echo "📖 Documentation disponible sur :"
echo "   http://localhost:8000/docs"
echo ""
echo "🏥 Santé de l'application :"
echo "   http://localhost:8000/health"

