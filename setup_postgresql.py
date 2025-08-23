#!/usr/bin/env python3
"""
Script d'installation et configuration automatisée de PostgreSQL pour l'application VTC.
Installation, configuration et migration complète.
"""

import os
import sys
import subprocess
import time
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import logging
from pathlib import Path

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('postgresql_setup.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PostgreSQLSetup:
    """Gestionnaire d'installation PostgreSQL automatisée"""
    
    def __init__(self):
        self.db_name = "uber_vtc"
        self.db_user = "uber_user"
        self.db_password = "uber_password_2024"
        self.db_host = "localhost"
        self.db_port = "5432"
        
    def check_postgresql_installed(self) -> bool:
        """Vérifie si PostgreSQL est installé"""
        try:
            result = subprocess.run(['psql', '--version'], 
                                  capture_output=True, text=True)
            if result.returncode == 0:
                logger.info(f"✅ PostgreSQL détecté: {result.stdout.strip()}")
                return True
            return False
        except FileNotFoundError:
            logger.info("❌ PostgreSQL non installé")
            return False
    
    def install_postgresql_ubuntu(self) -> bool:
        """Installe PostgreSQL sur Ubuntu"""
        try:
            logger.info("📦 Installation de PostgreSQL...")
            
            # Mise à jour des paquets
            subprocess.run(['sudo', 'apt', 'update'], check=True)
            
            # Installation PostgreSQL
            subprocess.run([
                'sudo', 'apt', 'install', '-y', 
                'postgresql', 'postgresql-contrib', 'postgresql-client'
            ], check=True)
            
            # Démarrage du service
            subprocess.run(['sudo', 'systemctl', 'start', 'postgresql'], check=True)
            subprocess.run(['sudo', 'systemctl', 'enable', 'postgresql'], check=True)
            
            logger.info("✅ PostgreSQL installé avec succès")
            return True
            
        except subprocess.CalledProcessError as e:
            logger.error(f"❌ Erreur installation PostgreSQL: {e}")
            return False
    
    def create_database_and_user(self) -> bool:
        """Crée la base de données et l'utilisateur"""
        try:
            # Connexion en tant que postgres
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                user='postgres',
                database='postgres'
            )
            conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
            cursor = conn.cursor()
            
            # Créer l'utilisateur
            try:
                cursor.execute(f"""
                    CREATE USER {self.db_user} WITH PASSWORD '{self.db_password}';
                """)
                logger.info(f"✅ Utilisateur {self.db_user} créé")
            except psycopg2.errors.DuplicateObject:
                logger.info(f"ℹ️ Utilisateur {self.db_user} existe déjà")
            
            # Créer la base de données
            try:
                cursor.execute(f"""
                    CREATE DATABASE {self.db_name} 
                    OWNER {self.db_user} 
                    ENCODING 'UTF8' 
                    LC_COLLATE = 'en_US.UTF-8' 
                    LC_CTYPE = 'en_US.UTF-8';
                """)
                logger.info(f"✅ Base de données {self.db_name} créée")
            except psycopg2.errors.DuplicateDatabase:
                logger.info(f"ℹ️ Base de données {self.db_name} existe déjà")
            
            # Accorder les privilèges
            cursor.execute(f"""
                GRANT ALL PRIVILEGES ON DATABASE {self.db_name} TO {self.db_user};
            """)
            
            cursor.close()
            conn.close()
            
            logger.info("✅ Base de données et utilisateur configurés")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur création base/utilisateur: {e}")
            return False
    
    def configure_postgresql(self) -> bool:
        """Configure PostgreSQL pour l'application"""
        try:
            # Trouver le répertoire de configuration PostgreSQL
            result = subprocess.run([
                'sudo', '-u', 'postgres', 'psql', '-t', '-P', 'format=unaligned',
                '-c', 'SHOW config_file;'
            ], capture_output=True, text=True)
            
            if result.returncode != 0:
                logger.error("❌ Impossible de trouver le fichier de configuration")
                return False
            
            config_file = result.stdout.strip()
            config_dir = os.path.dirname(config_file)
            
            # Configuration postgresql.conf
            postgresql_conf = f"{config_dir}/postgresql.conf"
            hba_conf = f"{config_dir}/pg_hba.conf"
            
            # Backup des fichiers de configuration
            subprocess.run(['sudo', 'cp', postgresql_conf, f"{postgresql_conf}.backup"])
            subprocess.run(['sudo', 'cp', hba_conf, f"{hba_conf}.backup"])
            
            # Optimisations PostgreSQL pour l'application VTC
            optimizations = """
# Optimisations pour application VTC
shared_buffers = 256MB
effective_cache_size = 1GB
maintenance_work_mem = 64MB
checkpoint_completion_target = 0.9
wal_buffers = 16MB
default_statistics_target = 100
random_page_cost = 1.1
effective_io_concurrency = 200
work_mem = 4MB
min_wal_size = 1GB
max_wal_size = 4GB
max_connections = 200
"""
            
            # Ajouter les optimisations
            subprocess.run([
                'sudo', 'bash', '-c', 
                f'echo "{optimizations}" >> {postgresql_conf}'
            ])
            
            # Configuration pg_hba.conf pour l'authentification
            hba_config = f"""
# Configuration pour application VTC
local   {self.db_name}   {self.db_user}   md5
host    {self.db_name}   {self.db_user}   127.0.0.1/32   md5
host    {self.db_name}   {self.db_user}   ::1/128        md5
"""
            
            subprocess.run([
                'sudo', 'bash', '-c',
                f'echo "{hba_config}" >> {hba_conf}'
            ])
            
            # Redémarrer PostgreSQL
            subprocess.run(['sudo', 'systemctl', 'restart', 'postgresql'])
            time.sleep(3)  # Attendre le redémarrage
            
            logger.info("✅ PostgreSQL configuré et redémarré")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur configuration PostgreSQL: {e}")
            return False
    
    def test_connection(self) -> bool:
        """Test la connexion à la base de données"""
        try:
            conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.db_user,
                password=self.db_password
            )
            
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            version = cursor.fetchone()[0]
            
            cursor.close()
            conn.close()
            
            logger.info(f"✅ Connexion réussie: {version}")
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur connexion: {e}")
            return False
    
    def create_env_file(self) -> None:
        """Crée le fichier .env avec la configuration PostgreSQL"""
        env_content = f"""# Configuration PostgreSQL
POSTGRES_HOST={self.db_host}
POSTGRES_PORT={self.db_port}
POSTGRES_DB={self.db_name}
POSTGRES_USER={self.db_user}
POSTGRES_PASSWORD={self.db_password}
POSTGRES_SSL_MODE=prefer

# Configuration du pool de connexions
POSTGRES_POOL_SIZE=20
POSTGRES_MAX_OVERFLOW=30
POSTGRES_POOL_TIMEOUT=30
POSTGRES_POOL_RECYCLE=3600

# Configuration application
DATABASE_URL=postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}
SQL_DEBUG=false
"""
        
        with open('.env.postgresql', 'w') as f:
            f.write(env_content)
        
        logger.info("✅ Fichier .env.postgresql créé")
    
    def run_setup(self) -> bool:
        """Exécute l'installation complète"""
        logger.info("🐘 INSTALLATION POSTGRESQL AUTOMATISÉE")
        logger.info("=" * 50)
        
        try:
            # 1. Vérifier si PostgreSQL est installé
            if not self.check_postgresql_installed():
                logger.info("📦 Installation de PostgreSQL...")
                if not self.install_postgresql_ubuntu():
                    return False
            
            # 2. Créer la base de données et l'utilisateur
            logger.info("🏗️ Configuration base de données...")
            if not self.create_database_and_user():
                return False
            
            # 3. Configurer PostgreSQL
            logger.info("⚙️ Configuration PostgreSQL...")
            if not self.configure_postgresql():
                return False
            
            # 4. Tester la connexion
            logger.info("🔍 Test de connexion...")
            if not self.test_connection():
                return False
            
            # 5. Créer le fichier .env
            logger.info("📄 Création fichier .env...")
            self.create_env_file()
            
            logger.info("🎉 INSTALLATION POSTGRESQL RÉUSSIE !")
            logger.info(f"📊 Base de données: {self.db_name}")
            logger.info(f"👤 Utilisateur: {self.db_user}")
            logger.info(f"🔗 URL: postgresql://{self.db_user}:***@{self.db_host}:{self.db_port}/{self.db_name}")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ INSTALLATION ÉCHOUÉE: {e}")
            return False

def main():
    """Fonction principale"""
    print("🐘 INSTALLATION POSTGRESQL AUTOMATISÉE")
    print("=" * 50)
    
    # Vérifier les privilèges sudo
    if os.geteuid() == 0:
        print("❌ Ne pas exécuter en tant que root")
        sys.exit(1)
    
    # Confirmation
    confirm = input("⚠️ Installer PostgreSQL pour l'application VTC ? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Installation annulée")
        sys.exit(0)
    
    # Installation
    setup = PostgreSQLSetup()
    success = setup.run_setup()
    
    if success:
        print("\n🎉 Installation terminée avec succès !")
        print("📄 Consultez postgresql_setup.log pour les détails")
        print("📄 Configuration dans .env.postgresql")
        print("\n🔄 Prochaines étapes:")
        print("1. Copier .env.postgresql vers .env")
        print("2. Exécuter python migrate_to_postgresql.py")
        print("3. Redémarrer l'application")
    else:
        print("\n❌ Installation échouée !")
        print("📄 Consultez postgresql_setup.log pour les erreurs")
        sys.exit(1)

if __name__ == "__main__":
    main()

