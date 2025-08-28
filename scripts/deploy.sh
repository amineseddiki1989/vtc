#!/bin/bash
# VTC Application - Script de déploiement production

set -e

echo "🚗 VTC - Déploiement Production"
echo "================================"

# Couleurs
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Fonction d'affichage
log() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

# Vérifications préalables
log "Vérification des prérequis..."

# Docker
if ! command -v docker &> /dev/null; then
    error "Docker n'est pas installé"
fi

# Docker Compose
if ! command -v docker-compose &> /dev/null; then
    error "Docker Compose n'est pas installé"
fi

# Variables d'environnement
if [ ! -f .env ]; then
    warn "Fichier .env manquant, création avec des valeurs par défaut"
    cp .env.example .env
fi

log "Prérequis validés ✅"

# Arrêt des services existants
log "Arrêt des services existants..."
docker-compose down --remove-orphans

# Nettoyage des images obsolètes
log "Nettoyage des images obsolètes..."
docker system prune -f

# Construction des images
log "Construction des images Docker..."
docker-compose build --no-cache

# Démarrage des services
log "Démarrage des services..."
docker-compose up -d

# Vérification du déploiement
log "Vérification du déploiement..."
sleep 30

# Test de santé
if curl -f http://localhost:3000/health &> /dev/null; then
    log "Frontend: ✅ Opérationnel"
else
    warn "Frontend: ⚠️  En cours de démarrage"
fi

if curl -f http://localhost:5000/health &> /dev/null; then
    log "Backend: ✅ Opérationnel"
else
    warn "Backend: ⚠️  En cours de démarrage"
fi

# Affichage des logs
log "Affichage des logs récents..."
docker-compose logs --tail=20

log "🎉 Déploiement terminé!"
log "Frontend: http://localhost:3000"
log "Backend API: http://localhost:5000"
log "Admin: admin@vtc-app.com / AdminVTC2024!"

echo "================================"
