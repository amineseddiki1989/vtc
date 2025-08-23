#!/usr/bin/env python3
"""
Script de test pour vérifier la collecte des métriques métier.
"""

import sys
import os
import time
import asyncio
from datetime import datetime, timedelta

# Ajouter le répertoire de l'application au path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'app'))

from app.core.database.base import get_db, create_tables
from app.models.user import User, UserRole
from app.models.trip import Trip, TripStatus, VehicleType
from app.models.rating import Rating
from app.services.metrics_service import get_metrics_collector, MetricsService
from app.services.trip_service import TripService
from app.services.pricing_service import PricingService
from app.services.location_service import LocationService
from app.services.customer_satisfaction_service import CustomerSatisfactionService
from app.services.database_metrics_service import get_database_metrics_service
from app.core.security.auth_service import AuthService
from app.schemas.trip import TripCreate


class MetricsTestSuite:
    """Suite de tests pour les métriques métier."""
    
    def __init__(self):
        self.db = next(get_db())
        self.collector = get_metrics_collector()
        self.metrics_service = MetricsService(self.db)
        
        # Services à tester
        self.trip_service = TripService(self.db)
        self.pricing_service = PricingService()
        self.location_service = LocationService(self.db)
        self.satisfaction_service = CustomerSatisfactionService(self.db)
        self.auth_service = AuthService()
        self.db_metrics = get_database_metrics_service()
        
        print("🔧 Suite de tests des métriques initialisée")
    
    def setup_test_data(self):
        """Crée des données de test."""
        print("📊 Création des données de test...")
        
        # Créer des utilisateurs de test
        passenger = User(
            id="test_passenger_001",
            email="passenger@test.com",
            phone="+213555000001",
            first_name="Ahmed",
            last_name="Benali",
            role=UserRole.PASSENGER,
            status="active"
        )
        
        driver = User(
            id="test_driver_001",
            email="driver@test.com",
            phone="+213555000002",
            first_name="Fatima",
            last_name="Khelifi",
            role=UserRole.DRIVER,
            status="active"
        )
        
        self.db.add(passenger)
        self.db.add(driver)
        self.db.commit()
        
        print("✅ Utilisateurs de test créés")
        return passenger, driver
    
    def test_auth_metrics(self):
        """Test des métriques d'authentification."""
        print("🔐 Test des métriques d'authentification...")
        
        try:
            # Test création de tokens
            session_id = self.auth_service.generate_session_id()
            access_token = self.auth_service.create_access_token(
                user_id="test_passenger_001",
                role="passenger",
                session_id=session_id
            )
            
            refresh_token = self.auth_service.create_refresh_token(
                user_id="test_passenger_001",
                session_id=session_id
            )
            
            # Test vérification de token
            payload = self.auth_service.verify_access_token(access_token)
            
            # Test révocation
            self.auth_service.revoke_token(access_token)
            
            print("✅ Métriques d'authentification testées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur dans les métriques d'authentification: {e}")
            return False
    
    def test_trip_metrics(self, passenger, driver):
        """Test des métriques de courses."""
        print("🚗 Test des métriques de courses...")
        
        try:
            # Test estimation de course
            trip_data = TripCreate(
                pickup_latitude=36.7538,
                pickup_longitude=3.0588,
                pickup_address="Alger Centre",
                destination_latitude=36.7755,
                destination_longitude=3.0597,
                destination_address="Bab El Oued",
                vehicle_type=VehicleType.STANDARD,
                notes="Test trip"
            )
            
            estimate = self.trip_service.estimate_trip(trip_data)
            print(f"   Estimation: {estimate.distance_km}km, {estimate.price}DZD")
            
            # Test création de course
            trip = self.trip_service.create_trip(trip_data, passenger.id)
            print(f"   Course créée: {trip.id}")
            
            # Test attribution de conducteur
            trip = self.trip_service.assign_driver(trip.id, driver.id)
            print(f"   Conducteur attribué")
            
            # Test démarrage de course
            trip = self.trip_service.start_trip(trip.id, driver.id)
            print(f"   Course démarrée")
            
            # Simuler un délai
            time.sleep(1)
            
            # Test finalisation de course
            trip = self.trip_service.complete_trip(trip.id, driver.id)
            print(f"   Course terminée")
            
            print("✅ Métriques de courses testées")
            return trip
            
        except Exception as e:
            print(f"❌ Erreur dans les métriques de courses: {e}")
            return None
    
    def test_pricing_metrics(self):
        """Test des métriques de tarification."""
        print("💰 Test des métriques de tarification...")
        
        try:
            # Test calcul de prix
            price = self.pricing_service.calculate_price(
                distance_km=5.2,
                duration_minutes=15,
                vehicle_type=VehicleType.COMFORT,
                pickup_zone="city_center",
                destination_zone="residential"
            )
            print(f"   Prix calculé: {price}DZD")
            
            # Test surge pricing
            self.pricing_service.set_surge_pricing(1.5)
            surge_price = self.pricing_service.calculate_price(
                distance_km=5.2,
                duration_minutes=15,
                vehicle_type=VehicleType.COMFORT
            )
            print(f"   Prix avec surge: {surge_price}DZD")
            
            # Test estimation de gains
            earnings = self.pricing_service.estimate_earnings(
                distance_km=5.2,
                vehicle_type=VehicleType.COMFORT
            )
            print(f"   Gains estimés: {earnings['net_earnings']}DZD")
            
            print("✅ Métriques de tarification testées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur dans les métriques de tarification: {e}")
            return False
    
    def test_location_metrics(self, driver):
        """Test des métriques de localisation."""
        print("📍 Test des métriques de localisation...")
        
        try:
            # Test mise à jour de position
            location = self.location_service.update_driver_location(
                driver_id=driver.id,
                latitude=36.7538,
                longitude=3.0588,
                heading=45.0,
                speed=30.0,
                accuracy=5.0
            )
            print(f"   Position mise à jour")
            
            # Test changement de disponibilité
            location = self.location_service.set_driver_availability(driver.id, True)
            print(f"   Disponibilité activée")
            
            # Test changement de statut en ligne
            location = self.location_service.set_driver_online_status(driver.id, True)
            print(f"   Statut en ligne activé")
            
            # Test recherche de conducteurs
            nearby_drivers = self.location_service.find_nearby_drivers(
                latitude=36.7540,
                longitude=3.0590,
                radius_km=5
            )
            print(f"   Conducteurs trouvés: {len(nearby_drivers)}")
            
            print("✅ Métriques de localisation testées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur dans les métriques de localisation: {e}")
            return False
    
    def test_satisfaction_metrics(self, trip, passenger, driver):
        """Test des métriques de satisfaction."""
        print("⭐ Test des métriques de satisfaction...")
        
        if not trip:
            print("   ⚠️ Pas de course disponible pour tester les ratings")
            return False
        
        try:
            # Test évaluation par le passager
            rating = self.satisfaction_service.create_rating(
                trip_id=trip.id,
                rater_id=passenger.id,
                rated_id=driver.id,
                rating=5,
                comment="Excellent service, conducteur très professionnel!",
                punctuality=5,
                cleanliness=4,
                communication=5,
                safety=5
            )
            print(f"   Évaluation passager créée: {rating.rating}/5")
            
            # Test évaluation par le conducteur
            rating2 = self.satisfaction_service.create_rating(
                trip_id=trip.id,
                rater_id=driver.id,
                rated_id=passenger.id,
                rating=4,
                comment="Passager ponctuel et respectueux",
                punctuality=5,
                communication=4
            )
            print(f"   Évaluation conducteur créée: {rating2.rating}/5")
            
            # Test statistiques utilisateur
            stats = self.satisfaction_service.calculate_user_rating_stats(
                driver.id, UserRole.DRIVER
            )
            print(f"   Stats conducteur: {stats['average_rating']}/5 ({stats['total_ratings']} évaluations)")
            
            print("✅ Métriques de satisfaction testées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur dans les métriques de satisfaction: {e}")
            return False
    
    def test_database_metrics(self):
        """Test des métriques de base de données."""
        print("🗄️ Test des métriques de base de données...")
        
        try:
            # Test santé de la base de données
            health = self.db_metrics.get_database_health_metrics(self.db)
            print(f"   Santé DB: {health['status']}")
            
            # Test opération avec monitoring
            with self.db_metrics.monitor_transaction("test_operation"):
                # Simuler une opération
                result = self.db.execute("SELECT COUNT(*) FROM users").scalar()
                print(f"   Nombre d'utilisateurs: {result}")
            
            print("✅ Métriques de base de données testées")
            return True
            
        except Exception as e:
            print(f"❌ Erreur dans les métriques de base de données: {e}")
            return False
    
    def test_metrics_collection(self):
        """Test de la collecte des métriques."""
        print("📈 Test de la collecte des métriques...")
        
        try:
            # Forcer le flush des métriques
            self.collector.flush_metrics()
            
            # Récupérer les métriques collectées
            metrics = self.metrics_service.get_realtime_metrics()
            print(f"   Métriques en temps réel: {len(metrics)} entrées")
            
            # Récupérer l'historique
            history = self.metrics_service.get_metrics(limit=50)
            print(f"   Historique: {len(history)} métriques")
            
            # Test résumé
            summary = self.metrics_service.get_metrics_summary()
            print(f"   Résumé: {len(summary)} catégories")
            
            print("✅ Collecte des métriques testée")
            return True
            
        except Exception as e:
            print(f"❌ Erreur dans la collecte des métriques: {e}")
            return False
    
    def run_all_tests(self):
        """Exécute tous les tests."""
        print("🚀 Démarrage des tests des métriques métier")
        print("=" * 50)
        
        # Créer les tables si nécessaire
        create_tables()
        
        # Créer les données de test
        passenger, driver = self.setup_test_data()
        
        # Exécuter les tests
        results = {}
        
        results['auth'] = self.test_auth_metrics()
        results['pricing'] = self.test_pricing_metrics()
        results['location'] = self.test_location_metrics(driver)
        results['trip'] = self.test_trip_metrics(passenger, driver)
        
        # Le test de satisfaction dépend du résultat du test de trip
        trip = None
        if results['trip']:
            # Récupérer la course créée
            trip = self.db.query(Trip).filter(Trip.passenger_id == passenger.id).first()
        
        results['satisfaction'] = self.test_satisfaction_metrics(trip, passenger, driver)
        results['database'] = self.test_database_metrics()
        results['collection'] = self.test_metrics_collection()
        
        # Résumé des résultats
        print("\n" + "=" * 50)
        print("📊 RÉSUMÉ DES TESTS")
        print("=" * 50)
        
        total_tests = len(results)
        passed_tests = sum(1 for result in results.values() if result)
        
        for test_name, result in results.items():
            status = "✅ PASSÉ" if result else "❌ ÉCHOUÉ"
            print(f"{test_name.upper():15} : {status}")
        
        print(f"\nRésultat global: {passed_tests}/{total_tests} tests passés")
        
        if passed_tests == total_tests:
            print("🎉 Tous les tests sont passés avec succès!")
            return True
        else:
            print("⚠️ Certains tests ont échoué")
            return False
    
    def cleanup(self):
        """Nettoie les données de test."""
        try:
            # Supprimer les données de test
            self.db.query(Rating).filter(Rating.rater_id.like("test_%")).delete()
            self.db.query(Trip).filter(Trip.passenger_id.like("test_%")).delete()
            self.db.query(User).filter(User.id.like("test_%")).delete()
            self.db.commit()
            print("🧹 Données de test nettoyées")
        except Exception as e:
            print(f"⚠️ Erreur lors du nettoyage: {e}")


def main():
    """Fonction principale."""
    test_suite = MetricsTestSuite()
    
    try:
        success = test_suite.run_all_tests()
        return 0 if success else 1
    except Exception as e:
        print(f"💥 Erreur fatale: {e}")
        return 1
    finally:
        test_suite.cleanup()


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)

