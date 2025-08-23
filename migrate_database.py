#!/usr/bin/env python3
"""
Script de migration de la base de données pour ajouter les nouvelles colonnes.
"""

import sys
import os
import sqlite3
from datetime import datetime

# Ajouter le répertoire de l'application au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """Migre la base de données avec les nouvelles colonnes"""
    
    db_path = "app.db"
    
    if not os.path.exists(db_path):
        print("❌ Base de données non trouvée")
        return False
    
    print("🔄 Migration de la base de données...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Vérifier les colonnes existantes dans trips
        cursor.execute("PRAGMA table_info(trips)")
        existing_columns = [row[1] for row in cursor.fetchall()]
        print(f"📋 Colonnes existantes: {existing_columns}")
        
        # Colonnes à ajouter
        new_columns = [
            ("payment_status", "VARCHAR(20) DEFAULT 'pending'"),
            ("assigned_at", "DATETIME"),
            ("accepted_at", "DATETIME"),
            ("arrived_at", "DATETIME"),
            ("started_at", "DATETIME"),
            ("completed_at", "DATETIME"),
            ("cancelled_at", "DATETIME"),
            ("cancellation_reason", "TEXT"),
            ("notes", "TEXT"),
            ("updated_at", "DATETIME DEFAULT CURRENT_TIMESTAMP")
        ]
        
        # Ajouter les colonnes manquantes
        for column_name, column_def in new_columns:
            if column_name not in existing_columns:
                try:
                    cursor.execute(f"ALTER TABLE trips ADD COLUMN {column_name} {column_def}")
                    print(f"✅ Colonne ajoutée: {column_name}")
                except sqlite3.OperationalError as e:
                    print(f"⚠️  Erreur ajout {column_name}: {e}")
        
        # Créer les nouvelles tables si elles n'existent pas
        
        # Table driver_locations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS driver_locations (
                id VARCHAR PRIMARY KEY,
                driver_id VARCHAR NOT NULL UNIQUE,
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                heading FLOAT,
                speed FLOAT,
                accuracy FLOAT,
                is_online BOOLEAN DEFAULT 0,
                is_available BOOLEAN DEFAULT 0,
                current_trip_id VARCHAR,
                last_updated DATETIME DEFAULT CURRENT_TIMESTAMP,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (driver_id) REFERENCES users(id)
            )
        """)
        print("✅ Table driver_locations créée/vérifiée")
        
        # Table vehicles
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS vehicles (
                id VARCHAR PRIMARY KEY,
                driver_id VARCHAR NOT NULL,
                make VARCHAR(50) NOT NULL,
                model VARCHAR(50) NOT NULL,
                year VARCHAR(4) NOT NULL,
                color VARCHAR(30) NOT NULL,
                license_plate VARCHAR(20) NOT NULL UNIQUE,
                vehicle_type VARCHAR(20) DEFAULT 'standard',
                status VARCHAR(20) DEFAULT 'active',
                max_passengers VARCHAR(1) DEFAULT '4',
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (driver_id) REFERENCES users(id)
            )
        """)
        print("✅ Table vehicles créée/vérifiée")
        
        # Table ratings
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ratings (
                id VARCHAR PRIMARY KEY,
                trip_id VARCHAR NOT NULL UNIQUE,
                passenger_rating FLOAT,
                driver_rating FLOAT,
                passenger_comment TEXT,
                driver_comment TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips(id)
            )
        """)
        print("✅ Table ratings créée/vérifiée")
        
        # Table payments
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                id VARCHAR PRIMARY KEY,
                trip_id VARCHAR NOT NULL UNIQUE,
                amount FLOAT NOT NULL,
                currency VARCHAR(3) DEFAULT 'EUR',
                platform_fee FLOAT DEFAULT 0.0,
                driver_amount FLOAT DEFAULT 0.0,
                status VARCHAR(20) DEFAULT 'pending',
                payment_method VARCHAR(20) DEFAULT 'card',
                stripe_payment_intent_id VARCHAR(255) UNIQUE,
                stripe_charge_id VARCHAR(255),
                stripe_transfer_id VARCHAR(255),
                failure_reason TEXT,
                refund_reason TEXT,
                refund_amount FLOAT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                processed_at DATETIME,
                completed_at DATETIME,
                failed_at DATETIME,
                refunded_at DATETIME,
                FOREIGN KEY (trip_id) REFERENCES trips(id)
            )
        """)
        print("✅ Table payments créée/vérifiée")
        
        # Table trip_locations
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS trip_locations (
                id VARCHAR PRIMARY KEY,
                trip_id VARCHAR NOT NULL,
                latitude FLOAT NOT NULL,
                longitude FLOAT NOT NULL,
                heading FLOAT,
                speed FLOAT,
                recorded_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (trip_id) REFERENCES trips(id)
            )
        """)
        print("✅ Table trip_locations créée/vérifiée")
        
        # Valider les changements
        conn.commit()
        conn.close()
        
        print("🎉 Migration terminée avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors de la migration: {e}")
        return False

def main():
    """Fonction principale"""
    print("🔧 MIGRATION BASE DE DONNÉES VTC")
    print("=" * 40)
    
    success = migrate_database()
    
    if success:
        print("\n✅ Base de données migrée avec succès!")
        print("🚀 L'application peut maintenant être redémarrée")
    else:
        print("\n❌ Échec de la migration")
        print("🔧 Vérifiez les erreurs ci-dessus")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

