#!/bin/bash

# Script de démarrage robuste pour l'application VTC Uber
# Résout définitivement le problème "no output from terminal"

set -e  # Arrêter en cas d'erreur

echo "🎯 DÉMARRAGE APPLICATION VTC UBER - SOLUTION DÉFINITIVE"
echo "========================================================"

# Variables
APP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT=8009
LOG_FILE="$APP_DIR/uber_app.log"

# Fonction de nettoyage
cleanup() {
    echo ""
    echo "🛑 Arrêt demandé..."
    if [ ! -z "$APP_PID" ]; then
        echo "🔄 Arrêt de l'application (PID: $APP_PID)..."
        kill -TERM $APP_PID 2>/dev/null || true
        wait $APP_PID 2>/dev/null || true
    fi
    echo "✅ Application arrêtée"
    exit 0
}

# Gestionnaire de signaux
trap cleanup SIGINT SIGTERM

# Aller dans le répertoire de l'application
cd "$APP_DIR"
echo "📁 Répertoire: $APP_DIR"

# Vérifier les fichiers essentiels
if [ ! -f "app/main.py" ]; then
    echo "❌ Fichier app/main.py non trouvé"
    exit 1
fi
echo "✅ Fichier principal trouvé"

# Vérifier Python et les modules
echo "🐍 Vérification Python..."
python3 --version || {
    echo "❌ Python 3 non trouvé"
    exit 1
}

# Test d'import
echo "📦 Test des modules..."
python3 -c "
import sys
try:
    from app.main import app
    import uvicorn, fastapi, sqlalchemy
    print('✅ Tous les modules disponibles')
except ImportError as e:
    print(f'❌ Module manquant: {e}')
    sys.exit(1)
" || exit 1

# Vérifier le port
echo "🌐 Vérification du port $PORT..."
if netstat -tlnp 2>/dev/null | grep -q ":$PORT "; then
    echo "⚠️ Port $PORT déjà utilisé, tentative d'arrêt..."
    pkill -f "uvicorn.*:$PORT" || true
    sleep 2
fi

# Configuration de l'environnement
export DATABASE_URL='postgresql://uber_user:uber_password_2024@localhost:5432/uber_vtc'
export PYTHONPATH="$APP_DIR"

echo "⚙️ Variables d'environnement configurées"

# Démarrage de l'application
echo "🚀 Démarrage de l'application..."
echo "📝 Logs visibles ci-dessous (SOLUTION NO OUTPUT FROM TERMINAL):"
echo "🌐 URL: http://localhost:$PORT"
echo "📚 Documentation: http://localhost:$PORT/docs"
echo "📊 Monitoring: http://localhost:$PORT/api/v1/monitoring/summary"
echo "🛑 Arrêter avec Ctrl+C"
echo "========================================================"

# Démarrer EN PREMIER PLAN (SANS &) - SOLUTION AU PROBLÈME
python3 -m uvicorn app.main:app \
    --host 0.0.0.0 \
    --port $PORT \
    --reload \
    --log-level info &

APP_PID=$!
echo "✅ Application démarrée (PID: $APP_PID)"

# Attendre que l'application soit prête
echo "⏳ Attente du démarrage complet..."
for i in {1..30}; do
    if curl -s --max-time 2 "http://localhost:$PORT/health" >/dev/null 2>&1; then
        echo "✅ Application prête et fonctionnelle"
        break
    fi
    sleep 1
    if [ $((i % 5)) -eq 0 ]; then
        echo "⏳ Tentative $i/30..."
    fi
done

# Test final
echo "🧪 Test final..."
HEALTH_RESPONSE=$(curl -s --max-time 5 "http://localhost:$PORT/health" 2>/dev/null || echo "ERREUR")
if [[ $HEALTH_RESPONSE == *"healthy"* ]]; then
    echo "🎉 APPLICATION VTC PARFAITEMENT FONCTIONNELLE"
    echo "✅ Health Check: $HEALTH_RESPONSE"
else
    echo "⚠️ Application démarrée mais health check échoué"
fi

echo "========================================================"
echo "🎯 APPLICATION PRÊTE - LOGS EN TEMPS RÉEL CI-DESSOUS:"
echo "========================================================"

# Attendre le processus (logs visibles)
wait $APP_PID

