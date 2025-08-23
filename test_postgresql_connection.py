#!/usr/bin/env python3
"""Test de connexion PostgreSQL"""

import psycopg2
import sys

def test_connection():
    try:
        conn = psycopg2.connect(
            host='localhost',
            database='uber_vtc',
            user='uber_user',
            password='uber_password_2024',
            port='5432'
        )
        print("✅ Connexion PostgreSQL réussie !")
        
        # Test simple query
        cursor = conn.cursor()
        cursor.execute("SELECT version();")
        version = cursor.fetchone()
        print(f"📊 Version PostgreSQL: {version[0]}")
        
        cursor.close()
        conn.close()
        return True
        
    except Exception as e:
        print(f"❌ Erreur connexion PostgreSQL: {e}")
        return False

if __name__ == "__main__":
    success = test_connection()
    sys.exit(0 if success else 1)

