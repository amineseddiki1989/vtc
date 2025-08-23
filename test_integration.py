#!/usr/bin/env python3
"""
Script de test d'intégration pour l'application VTC avec monitoring.
"""

import sys
import os
import asyncio
import traceback
from datetime import datetime

# Ajout du chemin de l'application
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test des imports des modules."""
    print("🔍 Test des imports...")
    
    try:
        # Test import de l'application principale
        from app.main import app
        print("✅ Import de l'application principale: OK")
        
        # Test import des modules de monitoring
        from app.core.monitoring import (
            get_audit_logger,
            get_threat_detector,
            get_alert_manager
        )
        print("✅ Import des modules de monitoring: OK")
        
        # Test import du middleware
        from app.core.middleware.security_monitoring_middleware import SecurityMonitoringMiddleware
        print("✅ Import du middleware de sécurité: OK")
        
        # Test import du router de monitoring
        from app.api.v1.monitoring import router
        print("✅ Import du router de monitoring: OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'import: {e}")
        traceback.print_exc()
        return False


def test_monitoring_components():
    """Test des composants de monitoring."""
    print("\n🔍 Test des composants de monitoring...")
    
    try:
        from app.core.monitoring import (
            get_audit_logger,
            get_threat_detector,
            get_alert_manager
        )
        
        # Test du logger d'audit
        audit_logger = get_audit_logger()
        stats = audit_logger.get_statistics()
        print(f"✅ Audit Logger: {stats['log_directory']}")
        
        # Test du détecteur de menaces
        threat_detector = get_threat_detector()
        threat_stats = threat_detector.get_threat_statistics()
        print(f"✅ Threat Detector: {threat_stats['blocked_ips']} IPs bloquées")
        
        # Test du gestionnaire d'alertes
        alert_manager = get_alert_manager()
        alert_stats = alert_manager.get_statistics()
        print(f"✅ Alert Manager: {alert_stats['total_rules']} règles configurées")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur des composants: {e}")
        traceback.print_exc()
        return False


async def test_audit_functionality():
    """Test de la fonctionnalité d'audit."""
    print("\n🔍 Test de la fonctionnalité d'audit...")
    
    try:
        from app.core.monitoring.audit import (
            AuditEvent,
            AuditEventType,
            AuditSeverity,
            get_audit_logger
        )
        
        # Création d'un événement de test
        event = AuditEvent(
            event_type=AuditEventType.API_CALL,
            severity=AuditSeverity.INFO,
            action="test_integration",
            user_id="test_user",
            ip_address="127.0.0.1",
            details={"test": True, "timestamp": datetime.utcnow().isoformat()}
        )
        
        # Test d'enregistrement
        audit_logger = get_audit_logger()
        success = await audit_logger.log_event(event)
        
        if success:
            print("✅ Enregistrement d'événement d'audit: OK")
        else:
            print("❌ Échec de l'enregistrement d'audit")
            return False
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'audit: {e}")
        traceback.print_exc()
        return False


async def test_threat_detection():
    """Test de la détection de menaces."""
    print("\n🔍 Test de la détection de menaces...")
    
    try:
        from app.core.monitoring.security.threat_detector import (
            SecurityContext,
            get_threat_detector
        )
        
        # Création d'un contexte de test
        context = SecurityContext(
            ip_address="192.168.1.100",
            user_id="test_user",
            user_agent="TestAgent/1.0",
            endpoint="/api/v1/test",
            method="GET"
        )
        
        # Test de détection
        threat_detector = get_threat_detector()
        threats = await threat_detector.analyze_request(context)
        
        print(f"✅ Détection de menaces: {len(threats)} menaces détectées")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de détection: {e}")
        traceback.print_exc()
        return False


async def test_alert_system():
    """Test du système d'alertes."""
    print("\n🔍 Test du système d'alertes...")
    
    try:
        from app.core.monitoring.alerts import get_alert_manager
        from app.core.monitoring.audit import (
            AuditEvent,
            AuditEventType,
            AuditSeverity
        )
        
        # Création d'un événement critique pour déclencher une alerte
        event = AuditEvent(
            event_type=AuditEventType.SECURITY_THREAT_DETECTED,
            severity=AuditSeverity.CRITICAL,
            action="test_security_alert",
            ip_address="192.168.1.100",
            details={"threat_type": "test_threat", "test": True}
        )
        
        # Test de traitement d'alerte
        alert_manager = get_alert_manager()
        alerts = await alert_manager.process_event(event)
        
        print(f"✅ Système d'alertes: {len(alerts)} alertes générées")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur d'alertes: {e}")
        traceback.print_exc()
        return False


def test_middleware_creation():
    """Test de la création du middleware."""
    print("\n🔍 Test de la création du middleware...")
    
    try:
        from app.core.middleware.security_monitoring_middleware import SecurityMonitoringMiddleware
        from fastapi import FastAPI
        
        # Création d'une application de test
        test_app = FastAPI()
        
        # Ajout du middleware
        test_app.add_middleware(SecurityMonitoringMiddleware)
        
        print("✅ Création du middleware: OK")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de middleware: {e}")
        traceback.print_exc()
        return False


def test_application_structure():
    """Test de la structure de l'application."""
    print("\n🔍 Test de la structure de l'application...")
    
    try:
        from app.main import app
        
        # Vérification des routes
        routes = [route.path for route in app.routes]
        
        # Vérification des routes essentielles
        essential_routes = ["/", "/health", "/api/v1/monitoring/health"]
        
        for route in essential_routes:
            if any(r.startswith(route) for r in routes):
                print(f"✅ Route {route}: OK")
            else:
                print(f"❌ Route {route}: MANQUANTE")
                return False
        
        print(f"✅ Structure de l'application: {len(routes)} routes configurées")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de structure: {e}")
        traceback.print_exc()
        return False


def test_configuration():
    """Test de la configuration."""
    print("\n🔍 Test de la configuration...")
    
    try:
        from app.core.config.settings import get_settings
        
        settings = get_settings()
        
        print(f"✅ Configuration: {settings.app_name} v{settings.app_version}")
        print(f"✅ Environnement: {settings.environment}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur de configuration: {e}")
        traceback.print_exc()
        return False


async def run_all_tests():
    """Exécute tous les tests."""
    print("🚀 Démarrage des tests d'intégration VTC avec monitoring")
    print("=" * 60)
    
    tests = [
        ("Imports", test_imports),
        ("Configuration", test_configuration),
        ("Composants de monitoring", test_monitoring_components),
        ("Structure de l'application", test_application_structure),
        ("Création du middleware", test_middleware_creation),
        ("Fonctionnalité d'audit", test_audit_functionality),
        ("Détection de menaces", test_threat_detection),
        ("Système d'alertes", test_alert_system),
    ]
    
    results = []
    
    for test_name, test_func in tests:
        print(f"\n📋 Test: {test_name}")
        print("-" * 40)
        
        try:
            if asyncio.iscoroutinefunction(test_func):
                result = await test_func()
            else:
                result = test_func()
            
            results.append((test_name, result))
            
        except Exception as e:
            print(f"❌ Erreur inattendue dans {test_name}: {e}")
            results.append((test_name, False))
    
    # Résumé des résultats
    print("\n" + "=" * 60)
    print("📊 RÉSUMÉ DES TESTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for test_name, result in results:
        status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
        print(f"{test_name:<30} {status}")
        
        if result:
            passed += 1
        else:
            failed += 1
    
    print("-" * 60)
    print(f"Total: {len(results)} tests")
    print(f"Passés: {passed}")
    print(f"Échoués: {failed}")
    
    if failed == 0:
        print("\n🎉 TOUS LES TESTS SONT PASSÉS!")
        print("✅ L'intégration du monitoring est réussie!")
        return True
    else:
        print(f"\n⚠️  {failed} test(s) ont échoué")
        print("❌ L'intégration nécessite des corrections")
        return False


if __name__ == "__main__":
    # Configuration de l'environnement de test
    os.environ.setdefault("ENVIRONMENT", "development")  # Utiliser un environnement valide
    os.environ.setdefault("DATABASE_URL", "sqlite:///./test.db")
    os.environ.setdefault("JWT_SECRET_KEY", "test_secret_key_for_integration_tests_minimum_32_chars")
    os.environ.setdefault("ENCRYPTION_PASSWORD", "test_encryption_password_for_tests")
    os.environ.setdefault("AUDIT_LOG_DIRECTORY", "./test_logs")  # Répertoire accessible
    
    # Exécution des tests
    success = asyncio.run(run_all_tests())
    
    # Code de sortie
    sys.exit(0 if success else 1)

