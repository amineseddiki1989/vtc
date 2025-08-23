#!/bin/bash

echo "🚀 DÉMARRAGE APPLICATION VTC - SOLUTION NO OUTPUT FROM TERMINAL"
echo "================================================================"

# Vérifier le répertoire
echo "📁 Répertoire: $(pwd)"

# Vérifier les fichiers
if [ ! -f "app/main.py" ]; then
    echo "❌ Fichier app/main.py non trouvé"
    exit 1
fi
echo "✅ Fichier principal trouvé"

# Tester l'import
echo "🐍 Test d'import..."
python3 -c "from app.main import app; print('✅ Import réussi')" || {
    echo "❌ Erreur d'import"
    exit 1
}

# Démarrer l'application EN PREMIER PLAN (SANS &)
echo "🔥 Démarrage de l'application VTC..."
echo "📝 Logs visibles ci-dessous:"
echo "🌐 URL: http://localhost:8009"
echo "📚 Documentation: http://localhost:8009/docs"
echo "🛑 Arrêter avec Ctrl+C"
echo "================================================================"

# DÉMARRAGE EN PREMIER PLAN - SOLUTION AU PROBLÈME
DATABASE_URL='postgresql://uber_user:uber_password_2024@localhost:5432/uber_vtc' \
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8009 --reload

