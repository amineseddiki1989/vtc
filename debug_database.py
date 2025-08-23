#!/usr/bin/env python3
"""
Script de débogage de la base de données.
"""

import sys
import os
import sqlite3

# Ajouter le répertoire de l'application au path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def debug_database():
    """Débogue la base de données"""
    
    db_path = "uber_api.db"
    
    if not os.path.exists(db_path):
        print("❌ Base de données non trouvée")
        return False
    
    print("🔍 Débogage de la base de données...")
    
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Vérifier les colonnes de la table trips
        cursor.execute("PRAGMA table_info(trips)")
        columns = cursor.fetchall()
        
        print("📋 Colonnes de la table trips:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        # Vérifier si payment_status existe
        column_names = [col[1] for col in columns]
        if 'payment_status' in column_names:
            print("✅ Colonne payment_status trouvée")
        else:
            print("❌ Colonne payment_status manquante")
            
            # Ajouter la colonne manquante
            print("🔧 Ajout de la colonne payment_status...")
            cursor.execute("ALTER TABLE trips ADD COLUMN payment_status VARCHAR(20) DEFAULT 'pending'")
            conn.commit()
            print("✅ Colonne payment_status ajoutée")
        
        # Vérifier les autres colonnes manquantes
        expected_columns = [
            'assigned_at', 'accepted_at', 'arrived_at', 'started_at', 
            'completed_at', 'cancelled_at', 'cancellation_reason', 
            'notes', 'updated_at', 'created_at'
        ]
        
        for col_name in expected_columns:
            if col_name not in column_names:
                print(f"🔧 Ajout de la colonne {col_name}...")
                if col_name in ['cancellation_reason', 'notes']:
                    cursor.execute(f"ALTER TABLE trips ADD COLUMN {col_name} TEXT")
                elif col_name == 'updated_at':
                    cursor.execute(f"ALTER TABLE trips ADD COLUMN {col_name} DATETIME")
                else:
                    cursor.execute(f"ALTER TABLE trips ADD COLUMN {col_name} DATETIME")
                conn.commit()
                print(f"✅ Colonne {col_name} ajoutée")
        
        # Vérifier à nouveau
        cursor.execute("PRAGMA table_info(trips)")
        columns = cursor.fetchall()
        
        print("\n📋 Colonnes finales de la table trips:")
        for col in columns:
            print(f"  - {col[1]} ({col[2]})")
        
        conn.close()
        
        print("\n🎉 Base de données corrigée avec succès!")
        return True
        
    except Exception as e:
        print(f"❌ Erreur lors du débogage: {e}")
        return False

def main():
    """Fonction principale"""
    print("🔧 DÉBOGAGE BASE DE DONNÉES VTC")
    print("=" * 40)
    
    success = debug_database()
    
    if success:
        print("\n✅ Base de données corrigée!")
        print("🚀 L'application peut maintenant être redémarrée")
    else:
        print("\n❌ Échec du débogage")
        print("🔧 Vérifiez les erreurs ci-dessus")
    
    return success

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)

