"""
Tests complets de l'infrastructure production.
Validation de tous les composants critiques.
"""

import asyncio
import time
import json
import logging
from typing import Dict, Any, List
from datetime import datetime

# Configuration du logging pour les tests
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class InfrastructureTestSuite:
    """Suite de tests pour l'infrastructure."""
    
    def __init__(self):
        self.results: List[Dict[str, Any]] = []
        self.start_time = time.time()
    
    def log_test_result(self, test_name: str, success: bool, details: Dict[str, Any] = None):
        """Enregistre le résultat d'un test."""
        result = {
            "test": test_name,
            "success": success,
            "timestamp": datetime.now().isoformat(),
            "details": details or {}
        }
        self.results.append(result)
        
        status = "✅ PASS" if success else "❌ FAIL"
        logger.info(f"{status} - {test_name}")
        
        if details:
            for key, value in details.items():
                logger.info(f"  {key}: {value}")
    
    async def test_imports(self) -> bool:
        """Test des imports des modules."""
        try:
            # Test des imports critiques
            from app.core.config.production_settings import get_settings
            from app.core.database.postgresql import DatabaseManager
            from app.core.cache.redis_manager import RedisManager
            from app.core.security.security_headers import SecurityHeadersMiddleware
            from app.core.security.advanced_auth import AdvancedAuthManager
            from app.core.logging.production_logger import ProductionLoggerManager
            from app.core.monitoring.health_checks import HealthChecker
            
            self.log_test_result("imports", True, {
                "modules_imported": 7,
                "critical_components": "all_available"
            })
            return True
            
        except Exception as e:
            self.log_test_result("imports", False, {
                "error": str(e),
                "error_type": type(e).__name__
            })
            return False
    
    async def test_configuration(self) -> bool:
        """Test de la configuration production."""
        try:
            from app.core.config.production_settings import get_settings
            
            settings = get_settings()
            
            # Vérifications de base
            checks = {
                "app_name_set": bool(settings.app_name),
                "version_set": bool(settings.app_version),
                "environment_set": bool(settings.environment),
                "database_config": bool(settings.database.host and settings.database.name),
                "redis_config": bool(settings.redis.host),
                "security_config": bool(settings.security.secret_key),
                "monitoring_config": bool(settings.monitoring.log_level)
            }
            
            all_passed = all(checks.values())
            
            self.log_test_result("configuration", all_passed, {
                "checks_passed": sum(checks.values()),
                "total_checks": len(checks),
                "failed_checks": [k for k, v in checks.items() if not v]
            })
            
            return all_passed
            
        except Exception as e:
            self.log_test_result("configuration", False, {
                "error": str(e)
            })
            return False
    
    async def test_database_manager(self) -> bool:
        """Test du gestionnaire de base de données."""
        try:
            from app.core.database.postgresql import DatabaseManager
            
            db_manager = DatabaseManager()
            
            # Test de création d'instance
            self.log_test_result("database_manager_creation", True, {
                "instance_created": True,
                "type": type(db_manager).__name__
            })
            
            return True
            
        except Exception as e:
            self.log_test_result("database_manager_creation", False, {
                "error": str(e)
            })
            return False
    
    async def test_redis_manager(self) -> bool:
        """Test du gestionnaire Redis."""
        try:
            from app.core.cache.redis_manager import RedisManager
            
            redis_manager = RedisManager()
            
            # Test de création d'instance
            self.log_test_result("redis_manager_creation", True, {
                "instance_created": True,
                "type": type(redis_manager).__name__
            })
            
            return True
            
        except Exception as e:
            self.log_test_result("redis_manager_creation", False, {
                "error": str(e)
            })
            return False
    
    async def test_security_components(self) -> bool:
        """Test des composants de sécurité."""
        try:
            from app.core.security.security_headers import SecurityHeadersMiddleware
            from app.core.security.advanced_auth import AdvancedAuthManager, AdvancedPasswordValidator
            
            # Test des middlewares
            from fastapi import FastAPI
            app = FastAPI()
            
            # Test d'ajout des middlewares
            app.add_middleware(SecurityHeadersMiddleware)
            
            # Test du gestionnaire d'auth
            auth_manager = AdvancedAuthManager()
            password_validator = AdvancedPasswordValidator()
            
            # Test de validation de mot de passe
            validation_result = password_validator.validate_password("TestPassword123!")
            
            self.log_test_result("security_components", True, {
                "middleware_added": True,
                "auth_manager_created": True,
                "password_validation": validation_result["valid"],
                "password_score": validation_result["score"]
            })
            
            return True
            
        except Exception as e:
            self.log_test_result("security_components", False, {
                "error": str(e)
            })
            return False
    
    async def test_logging_system(self) -> bool:
        """Test du système de logging."""
        try:
            from app.core.logging.production_logger import ProductionLoggerManager, setup_logging
            
            # Test de configuration du logging
            setup_logging()
            
            # Test de création d'un logger
            test_logger = logging.getLogger("test_infrastructure")
            test_logger.info("Test log message", extra={
                "test_data": "infrastructure_test",
                "component": "logging_system"
            })
            
            self.log_test_result("logging_system", True, {
                "logging_configured": True,
                "test_log_sent": True
            })
            
            return True
            
        except Exception as e:
            self.log_test_result("logging_system", False, {
                "error": str(e)
            })
            return False
    
    async def test_health_checks(self) -> bool:
        """Test du système de health checks."""
        try:
            from app.core.monitoring.health_checks import HealthChecker
            
            health_checker = HealthChecker()
            
            # Test des checks individuels (sans connexions réelles)
            checks_available = list(health_checker.checks.keys())
            
            self.log_test_result("health_checks", True, {
                "health_checker_created": True,
                "available_checks": checks_available,
                "checks_count": len(checks_available)
            })
            
            return True
            
        except Exception as e:
            self.log_test_result("health_checks", False, {
                "error": str(e)
            })
            return False
    
    async def test_main_application(self) -> bool:
        """Test de l'application principale."""
        try:
            from app.main_production import create_production_app
            
            # Créer l'application
            app = create_production_app()
            
            # Vérifier les routes
            routes = [route.path for route in app.routes]
            expected_routes = ["/", "/health", "/health/ready", "/health/live"]
            
            routes_ok = all(route in routes for route in expected_routes)
            
            self.log_test_result("main_application", routes_ok, {
                "app_created": True,
                "routes_count": len(routes),
                "expected_routes_present": routes_ok,
                "middleware_count": len(app.user_middleware)
            })
            
            return routes_ok
            
        except Exception as e:
            self.log_test_result("main_application", False, {
                "error": str(e)
            })
            return False
    
    async def test_password_security(self) -> bool:
        """Test approfondi de la sécurité des mots de passe."""
        try:
            from app.core.security.advanced_auth import AdvancedPasswordValidator
            
            validator = AdvancedPasswordValidator()
            
            # Tests de différents mots de passe
            test_passwords = [
                ("password", False),  # Trop simple
                ("123456", False),    # Trop simple
                ("Password123!", True),  # Bon
                ("SuperSecurePassword2024!", True),  # Très bon
                ("abc", False),       # Trop court
            ]
            
            results = []
            for password, expected_valid in test_passwords:
                result = validator.validate_password(password)
                results.append({
                    "password": password[:3] + "***",
                    "valid": result["valid"],
                    "expected": expected_valid,
                    "score": result["score"],
                    "strength": result["strength"]
                })
            
            # Vérifier que les résultats correspondent aux attentes
            all_correct = all(
                r["valid"] == r["expected"] for r in results
            )
            
            self.log_test_result("password_security", all_correct, {
                "tests_run": len(test_passwords),
                "all_correct": all_correct,
                "results": results
            })
            
            return all_correct
            
        except Exception as e:
            self.log_test_result("password_security", False, {
                "error": str(e)
            })
            return False
    
    async def run_all_tests(self) -> Dict[str, Any]:
        """Exécute tous les tests d'infrastructure."""
        logger.info("🧪 Démarrage des tests d'infrastructure...")
        
        # Liste des tests à exécuter
        tests = [
            self.test_imports,
            self.test_configuration,
            self.test_database_manager,
            self.test_redis_manager,
            self.test_security_components,
            self.test_logging_system,
            self.test_health_checks,
            self.test_main_application,
            self.test_password_security
        ]
        
        # Exécuter tous les tests
        for test in tests:
            try:
                await test()
            except Exception as e:
                logger.error(f"Erreur lors du test {test.__name__}: {e}")
                self.log_test_result(test.__name__, False, {"error": str(e)})
        
        # Calculer les statistiques
        total_tests = len(self.results)
        passed_tests = sum(1 for r in self.results if r["success"])
        failed_tests = total_tests - passed_tests
        success_rate = (passed_tests / total_tests * 100) if total_tests > 0 else 0
        
        duration = time.time() - self.start_time
        
        summary = {
            "total_tests": total_tests,
            "passed": passed_tests,
            "failed": failed_tests,
            "success_rate": round(success_rate, 2),
            "duration_seconds": round(duration, 2),
            "timestamp": datetime.now().isoformat(),
            "results": self.results
        }
        
        # Log du résumé
        logger.info(f"📊 Tests terminés: {passed_tests}/{total_tests} réussis ({success_rate:.1f}%)")
        
        if failed_tests > 0:
            logger.warning(f"❌ {failed_tests} tests ont échoué")
            failed_test_names = [r["test"] for r in self.results if not r["success"]]
            logger.warning(f"Tests échoués: {', '.join(failed_test_names)}")
        else:
            logger.info("✅ Tous les tests ont réussi!")
        
        return summary

async def main():
    """Fonction principale pour exécuter les tests."""
    test_suite = InfrastructureTestSuite()
    results = await test_suite.run_all_tests()
    
    # Sauvegarder les résultats
    with open("infrastructure_test_results.json", "w") as f:
        json.dump(results, f, indent=2)
    
    print(f"\n📋 Résultats sauvegardés dans infrastructure_test_results.json")
    print(f"🎯 Score final: {results['success_rate']}%")
    
    return results

if __name__ == "__main__":
    asyncio.run(main())

