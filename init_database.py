#!/usr/bin/env python3
"""
Script d'initialisation complète de la base de données VTC.
"""

import sys
import os

# Ajouter le répertoire de l'application au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def init_database():
    """Initialise complètement la base de données"""
    
    print("🔄 Initialisation de la base de données...")
    
    try:
        # Importer les modèles et la base
        from app.core.database.base import Base, engine
        from app.models import (
            User, Trip, DriverLocation, Vehicle, Rating, 
            Payment, DriverPayout, PaymentRefund, TripLocation
        )
        
        # Créer toutes les tables
        Base.metadata.create_all(bind=engine)
        
        print("✅ Toutes les tables créées avec succès!")
        
        # Vérifier les tables créées
        from sqlalchemy import inspect
        inspector = inspect(engine)
        tables = inspector.get_table_names()
        
        print(f"📋 Tables créées: {tables}")
        
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de l'initialisation: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    """Fonction principale"""
    print("🔧 INITIALISATION BASE DE DONNÉES VTC")
    print("=" * 40)
    
    success = init_database()
    
    if success:
        print("\n✅ Base de données initialisée avec succès!")
        print("🚀 L'application peut maintenant être démarrée")
    else:
        print("\n❌ Échec de l'initialisation")
        print("🔧 Vérifiez les erreurs ci-dessus")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

