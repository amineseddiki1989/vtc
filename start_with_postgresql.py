#!/usr/bin/env python3
"""
Script de démarrage de l'application VTC avec PostgreSQL intégré.
Gestion automatique de la migration et de l'initialisation.
"""

import os
import sys
import subprocess
import time
from pathlib import Path
import logging

# Ajouter le répertoire de l'application au path
sys.path.append('.')

from app.core.database.session import test_database_connection, create_tables
from app.core.config.settings import get_settings

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class VTCApplicationStarter:
    """Gestionnaire de démarrage de l'application VTC"""
    
    def __init__(self):
        self.settings = get_settings()
        self.use_postgresql = self.settings.database_url.startswith("postgresql")
        
    def check_environment(self) -> bool:
        """Vérifie l'environnement et les dépendances"""
        logger.info("🔍 Vérification de l'environnement...")
        
        # Vérifier les dépendances Python
        try:
            import psycopg2
            logger.info("✅ psycopg2 installé")
        except ImportError:
            logger.error("❌ psycopg2 manquant. Exécutez: pip install psycopg2-binary")
            return False
        
        # Vérifier le fichier .env
        if self.use_postgresql:
            required_vars = [
                'POSTGRES_HOST', 'POSTGRES_PORT', 'POSTGRES_DB',
                'POSTGRES_USER', 'POSTGRES_PASSWORD'
            ]
            missing = [var for var in required_vars if not os.getenv(var)]
            if missing:
                logger.error(f"❌ Variables d'environnement manquantes: {missing}")
                logger.info("💡 Exécutez: python setup_postgresql.py")
                return False
        
        logger.info("✅ Environnement validé")
        return True
    
    def setup_database(self) -> bool:
        """Configure la base de données"""
        logger.info("🗄️ Configuration de la base de données...")
        
        # Test de connexion
        if not test_database_connection():
            if self.use_postgresql:
                logger.error("❌ Connexion PostgreSQL échouée")
                logger.info("💡 Vérifiez que PostgreSQL est démarré et configuré")
                return False
            else:
                logger.error("❌ Connexion base de données échouée")
                return False
        
        # Migration automatique si nécessaire
        if self.use_postgresql and os.path.exists("uber_api.db"):
            logger.info("📦 Base SQLite détectée, migration automatique...")
            if not self.run_migration():
                logger.warning("⚠️ Migration échouée, continuons avec PostgreSQL vide")
        
        # Création des tables
        try:
            create_tables()
            logger.info("✅ Base de données initialisée")
            return True
        except Exception as e:
            logger.error(f"❌ Erreur initialisation DB: {e}")
            return False
    
    def run_migration(self) -> bool:
        """Exécute la migration SQLite vers PostgreSQL"""
        try:
            logger.info("🔄 Démarrage de la migration...")
            result = subprocess.run([
                sys.executable, "migrate_to_postgresql.py"
            ], capture_output=True, text=True, timeout=300)
            
            if result.returncode == 0:
                logger.info("✅ Migration réussie")
                return True
            else:
                logger.error(f"❌ Migration échouée: {result.stderr}")
                return False
                
        except subprocess.TimeoutExpired:
            logger.error("❌ Migration timeout (5 minutes)")
            return False
        except Exception as e:
            logger.error(f"❌ Erreur migration: {e}")
            return False
    
    def start_application(self) -> None:
        """Démarre l'application"""
        logger.info("🚀 Démarrage de l'application VTC...")
        
        # Configuration du serveur
        host = os.getenv('HOST', '0.0.0.0')
        port = int(os.getenv('PORT', 8000))
        workers = int(os.getenv('WORKERS', 1))
        
        if self.use_postgresql:
            logger.info(f"🐘 Mode PostgreSQL - {self.settings.database_url}")
        else:
            logger.info(f"📁 Mode SQLite - {self.settings.database_url}")
        
        # Démarrage avec uvicorn
        try:
            import uvicorn
            uvicorn.run(
                "app.main:app",
                host=host,
                port=port,
                workers=workers,
                reload=self.settings.environment == "development",
                log_level="info"
            )
        except KeyboardInterrupt:
            logger.info("🛑 Arrêt de l'application")
        except Exception as e:
            logger.error(f"❌ Erreur démarrage: {e}")
            sys.exit(1)
    
    def run(self) -> None:
        """Exécute le démarrage complet"""
        logger.info("🎯 DÉMARRAGE APPLICATION VTC")
        logger.info("=" * 50)
        
        try:
            # 1. Vérification environnement
            if not self.check_environment():
                sys.exit(1)
            
            # 2. Configuration base de données
            if not self.setup_database():
                sys.exit(1)
            
            # 3. Démarrage application
            self.start_application()
            
        except Exception as e:
            logger.error(f"❌ ERREUR CRITIQUE: {e}")
            sys.exit(1)

def show_help():
    """Affiche l'aide"""
    help_text = """
🎯 DÉMARRAGE APPLICATION VTC

Usage:
    python start_with_postgresql.py [options]

Options:
    --help, -h          Afficher cette aide
    --setup-postgres    Installer et configurer PostgreSQL
    --migrate-only      Migrer SQLite vers PostgreSQL uniquement
    --check-env         Vérifier l'environnement uniquement

Variables d'environnement:
    HOST                Adresse d'écoute (défaut: 0.0.0.0)
    PORT                Port d'écoute (défaut: 8000)
    WORKERS             Nombre de workers (défaut: 1)
    
    # PostgreSQL
    POSTGRES_HOST       Hôte PostgreSQL
    POSTGRES_PORT       Port PostgreSQL
    POSTGRES_DB         Nom de la base
    POSTGRES_USER       Utilisateur
    POSTGRES_PASSWORD   Mot de passe

Exemples:
    # Démarrage normal
    python start_with_postgresql.py
    
    # Installation PostgreSQL
    python start_with_postgresql.py --setup-postgres
    
    # Migration uniquement
    python start_with_postgresql.py --migrate-only
"""
    print(help_text)

def main():
    """Fonction principale"""
    if len(sys.argv) > 1:
        arg = sys.argv[1]
        
        if arg in ['--help', '-h']:
            show_help()
            return
        
        elif arg == '--setup-postgres':
            logger.info("🐘 Installation PostgreSQL...")
            result = subprocess.run([sys.executable, "setup_postgresql.py"])
            sys.exit(result.returncode)
        
        elif arg == '--migrate-only':
            logger.info("🔄 Migration uniquement...")
            starter = VTCApplicationStarter()
            if starter.run_migration():
                logger.info("✅ Migration terminée")
            else:
                logger.error("❌ Migration échouée")
                sys.exit(1)
            return
        
        elif arg == '--check-env':
            logger.info("🔍 Vérification environnement...")
            starter = VTCApplicationStarter()
            if starter.check_environment():
                logger.info("✅ Environnement OK")
            else:
                logger.error("❌ Environnement invalide")
                sys.exit(1)
            return
        
        else:
            logger.error(f"❌ Option inconnue: {arg}")
            show_help()
            sys.exit(1)
    
    # Démarrage normal
    starter = VTCApplicationStarter()
    starter.run()

if __name__ == "__main__":
    main()

