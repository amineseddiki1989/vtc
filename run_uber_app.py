#!/usr/bin/env python3
"""
Script de démarrage robuste pour l'application VTC Uber.
Résout définitivement le problème "no output from terminal".
"""

import os
import sys
import time
import subprocess
import signal
import logging
from pathlib import Path

# Configuration des logs
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('uber_app.log')
    ]
)

logger = logging.getLogger(__name__)

class UberAppRunner:
    """Gestionnaire de démarrage de l'application VTC Uber."""
    
    def __init__(self):
        self.app_dir = Path(__file__).parent
        self.process = None
        self.port = 8009
        
    def check_dependencies(self):
        """Vérifier les dépendances."""
        logger.info("🔍 Vérification des dépendances...")
        
        # Vérifier Python
        python_version = sys.version_info
        if python_version.major < 3 or python_version.minor < 8:
            logger.error("❌ Python 3.8+ requis")
            return False
        logger.info(f"✅ Python {python_version.major}.{python_version.minor}")
        
        # Vérifier les modules
        required_modules = ['fastapi', 'uvicorn', 'sqlalchemy', 'psycopg2']
        for module in required_modules:
            try:
                __import__(module)
                logger.info(f"✅ Module {module} disponible")
            except ImportError:
                logger.error(f"❌ Module {module} manquant")
                return False
        
        # Vérifier les fichiers
        main_file = self.app_dir / 'app' / 'main.py'
        if not main_file.exists():
            logger.error(f"❌ Fichier principal manquant: {main_file}")
            return False
        logger.info("✅ Fichier principal trouvé")
        
        return True
    
    def check_port(self):
        """Vérifier si le port est libre."""
        logger.info(f"🌐 Vérification du port {self.port}...")
        
        try:
            result = subprocess.run(
                ['netstat', '-tlnp'], 
                capture_output=True, 
                text=True, 
                timeout=10
            )
            if f":{self.port}" in result.stdout:
                logger.warning(f"⚠️ Port {self.port} déjà utilisé")
                return False
            else:
                logger.info(f"✅ Port {self.port} libre")
                return True
        except Exception as e:
            logger.warning(f"⚠️ Impossible de vérifier le port: {e}")
            return True
    
    def setup_environment(self):
        """Configurer l'environnement."""
        logger.info("⚙️ Configuration de l'environnement...")
        
        # Variables d'environnement
        os.environ['DATABASE_URL'] = 'postgresql://uber_user:uber_password_2024@localhost:5432/uber_vtc'
        os.environ['PYTHONPATH'] = str(self.app_dir)
        
        # Changer de répertoire
        os.chdir(self.app_dir)
        logger.info(f"✅ Répertoire de travail: {os.getcwd()}")
        
    def start_application(self):
        """Démarrer l'application."""
        logger.info("🚀 Démarrage de l'application VTC Uber...")
        
        # Commande de démarrage
        cmd = [
            sys.executable, '-m', 'uvicorn',
            'app.main:app',
            '--host', '0.0.0.0',
            '--port', str(self.port),
            '--reload',
            '--log-level', 'info'
        ]
        
        logger.info(f"📝 Commande: {' '.join(cmd)}")
        
        try:
            # Démarrer le processus EN PREMIER PLAN
            self.process = subprocess.Popen(
                cmd,
                stdout=sys.stdout,  # Logs visibles
                stderr=sys.stderr,  # Erreurs visibles
                cwd=self.app_dir,
                env=os.environ.copy()
            )
            
            logger.info(f"✅ Application démarrée (PID: {self.process.pid})")
            logger.info(f"🌐 URL: http://localhost:{self.port}")
            logger.info(f"📚 Documentation: http://localhost:{self.port}/docs")
            logger.info("🛑 Arrêter avec Ctrl+C")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Erreur de démarrage: {e}")
            return False
    
    def wait_for_startup(self):
        """Attendre que l'application soit prête."""
        logger.info("⏳ Attente du démarrage complet...")
        
        import requests
        max_attempts = 30
        
        for attempt in range(max_attempts):
            try:
                response = requests.get(f"http://localhost:{self.port}/health", timeout=2)
                if response.status_code == 200:
                    logger.info("✅ Application prête et fonctionnelle")
                    return True
            except:
                pass
            
            time.sleep(1)
            if attempt % 5 == 0:
                logger.info(f"⏳ Tentative {attempt + 1}/{max_attempts}...")
        
        logger.warning("⚠️ Application démarrée mais health check échoué")
        return False
    
    def handle_shutdown(self, signum, frame):
        """Gérer l'arrêt propre."""
        logger.info("🛑 Arrêt demandé...")
        
        if self.process:
            logger.info("🔄 Arrêt de l'application...")
            self.process.terminate()
            
            # Attendre l'arrêt propre
            try:
                self.process.wait(timeout=10)
                logger.info("✅ Application arrêtée proprement")
            except subprocess.TimeoutExpired:
                logger.warning("⚠️ Arrêt forcé")
                self.process.kill()
        
        sys.exit(0)
    
    def run(self):
        """Lancer l'application complète."""
        logger.info("🎯 DÉMARRAGE APPLICATION VTC UBER - SOLUTION NO OUTPUT FROM TERMINAL")
        logger.info("=" * 80)
        
        # Gestionnaire d'arrêt
        signal.signal(signal.SIGINT, self.handle_shutdown)
        signal.signal(signal.SIGTERM, self.handle_shutdown)
        
        # Vérifications
        if not self.check_dependencies():
            logger.error("❌ Dépendances manquantes")
            return False
        
        if not self.check_port():
            logger.error(f"❌ Port {self.port} occupé")
            return False
        
        # Configuration
        self.setup_environment()
        
        # Démarrage
        if not self.start_application():
            logger.error("❌ Échec du démarrage")
            return False
        
        # Attendre le démarrage
        self.wait_for_startup()
        
        # Attendre indéfiniment (logs visibles)
        try:
            self.process.wait()
        except KeyboardInterrupt:
            self.handle_shutdown(None, None)
        
        return True

def main():
    """Point d'entrée principal."""
    runner = UberAppRunner()
    success = runner.run()
    
    if not success:
        logger.error("❌ Échec du démarrage de l'application")
        sys.exit(1)

if __name__ == "__main__":
    main()

