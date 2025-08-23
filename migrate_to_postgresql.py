#!/usr/bin/env python3
"""
Script de migration de SQLite vers PostgreSQL pour l'application VTC.
Migration automatisée avec validation et rollback.
"""

import os
import sys
import json
import sqlite3
import psycopg2
from datetime import datetime
from typing import Dict, List, Any, Optional
import logging

# Configuration du logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('migration.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class PostgreSQLMigrator:
    """Gestionnaire de migration SQLite vers PostgreSQL"""
    
    def __init__(self, sqlite_db: str, postgres_config: Dict[str, str]):
        self.sqlite_db = sqlite_db
        self.postgres_config = postgres_config
        self.migration_log = []
        
    def connect_sqlite(self) -> sqlite3.Connection:
        """Connexion à SQLite"""
        try:
            conn = sqlite3.connect(self.sqlite_db)
            conn.row_factory = sqlite3.Row
            logger.info(f"✅ Connexion SQLite établie: {self.sqlite_db}")
            return conn
        except Exception as e:
            logger.error(f"❌ Erreur connexion SQLite: {e}")
            raise
    
    def connect_postgresql(self) -> psycopg2.extensions.connection:
        """Connexion à PostgreSQL"""
        try:
            conn = psycopg2.connect(**self.postgres_config)
            logger.info(f"✅ Connexion PostgreSQL établie: {self.postgres_config['host']}")
            return conn
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            raise
    
    def get_sqlite_schema(self) -> Dict[str, List[Dict]]:
        """Récupère le schéma SQLite"""
        sqlite_conn = self.connect_sqlite()
        schema = {}
        
        try:
            cursor = sqlite_conn.cursor()
            
            # Récupérer toutes les tables
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            for table in tables:
                # Récupérer les colonnes de chaque table
                cursor.execute(f"PRAGMA table_info({table})")
                columns = []
                for row in cursor.fetchall():
                    columns.append({
                        'name': row[1],
                        'type': row[2],
                        'not_null': row[3],
                        'default': row[4],
                        'primary_key': row[5]
                    })
                schema[table] = columns
                
            logger.info(f"✅ Schéma SQLite récupéré: {len(tables)} tables")
            return schema
            
        finally:
            sqlite_conn.close()
    
    def convert_sqlite_to_postgresql_type(self, sqlite_type: str) -> str:
        """Convertit les types SQLite vers PostgreSQL"""
        type_mapping = {
            'INTEGER': 'INTEGER',
            'TEXT': 'TEXT',
            'REAL': 'REAL',
            'BLOB': 'BYTEA',
            'NUMERIC': 'NUMERIC',
            'VARCHAR': 'VARCHAR',
            'DATETIME': 'TIMESTAMP',
            'FLOAT': 'REAL',
            'BOOLEAN': 'BOOLEAN'
        }
        
        # Gestion des types avec taille
        if '(' in sqlite_type:
            base_type = sqlite_type.split('(')[0].upper()
            size = sqlite_type.split('(')[1].split(')')[0]
            if base_type in ['VARCHAR', 'CHAR']:
                return f"VARCHAR({size})"
        
        return type_mapping.get(sqlite_type.upper(), 'TEXT')
    
    def create_postgresql_schema(self, schema: Dict[str, List[Dict]]) -> None:
        """Crée le schéma PostgreSQL"""
        pg_conn = self.connect_postgresql()
        
        try:
            cursor = pg_conn.cursor()
            
            # Supprimer les tables existantes (ordre inverse pour les FK)
            table_order = list(schema.keys())
            for table in reversed(table_order):
                cursor.execute(f"DROP TABLE IF EXISTS {table} CASCADE")
                logger.info(f"🗑️ Table {table} supprimée")
            
            # Créer les tables
            for table_name, columns in schema.items():
                create_sql = f"CREATE TABLE {table_name} (\n"
                column_defs = []
                
                for col in columns:
                    col_def = f"  {col['name']} {self.convert_sqlite_to_postgresql_type(col['type'])}"
                    
                    if col['not_null']:
                        col_def += " NOT NULL"
                    
                    if col['default'] is not None:
                        if col['default'].upper() == 'CURRENT_TIMESTAMP':
                            col_def += " DEFAULT CURRENT_TIMESTAMP"
                        else:
                            col_def += f" DEFAULT {col['default']}"
                    
                    if col['primary_key']:
                        col_def += " PRIMARY KEY"
                    
                    column_defs.append(col_def)
                
                create_sql += ",\n".join(column_defs) + "\n)"
                
                cursor.execute(create_sql)
                logger.info(f"✅ Table {table_name} créée")
            
            pg_conn.commit()
            logger.info("✅ Schéma PostgreSQL créé avec succès")
            
        except Exception as e:
            pg_conn.rollback()
            logger.error(f"❌ Erreur création schéma: {e}")
            raise
        finally:
            pg_conn.close()
    
    def migrate_data(self, schema: Dict[str, List[Dict]]) -> None:
        """Migre les données de SQLite vers PostgreSQL"""
        sqlite_conn = self.connect_sqlite()
        pg_conn = self.connect_postgresql()
        
        try:
            sqlite_cursor = sqlite_conn.cursor()
            pg_cursor = pg_conn.cursor()
            
            total_rows = 0
            
            for table_name in schema.keys():
                # Compter les lignes
                sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                row_count = sqlite_cursor.fetchone()[0]
                
                if row_count == 0:
                    logger.info(f"⏭️ Table {table_name} vide, ignorée")
                    continue
                
                # Récupérer toutes les données
                sqlite_cursor.execute(f"SELECT * FROM {table_name}")
                rows = sqlite_cursor.fetchall()
                
                # Préparer l'insertion PostgreSQL
                columns = [col['name'] for col in schema[table_name]]
                placeholders = ','.join(['%s'] * len(columns))
                insert_sql = f"INSERT INTO {table_name} ({','.join(columns)}) VALUES ({placeholders})"
                
                # Insérer les données
                for row in rows:
                    try:
                        pg_cursor.execute(insert_sql, tuple(row))
                    except Exception as e:
                        logger.warning(f"⚠️ Erreur insertion ligne {table_name}: {e}")
                        continue
                
                pg_conn.commit()
                total_rows += row_count
                logger.info(f"✅ Table {table_name}: {row_count} lignes migrées")
            
            logger.info(f"✅ Migration complète: {total_rows} lignes au total")
            
        except Exception as e:
            pg_conn.rollback()
            logger.error(f"❌ Erreur migration données: {e}")
            raise
        finally:
            sqlite_conn.close()
            pg_conn.close()
    
    def validate_migration(self, schema: Dict[str, List[Dict]]) -> bool:
        """Valide la migration"""
        sqlite_conn = self.connect_sqlite()
        pg_conn = self.connect_postgresql()
        
        try:
            sqlite_cursor = sqlite_conn.cursor()
            pg_cursor = pg_conn.cursor()
            
            validation_passed = True
            
            for table_name in schema.keys():
                # Comparer le nombre de lignes
                sqlite_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                sqlite_count = sqlite_cursor.fetchone()[0]
                
                pg_cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                pg_count = pg_cursor.fetchone()[0]
                
                if sqlite_count != pg_count:
                    logger.error(f"❌ Validation échouée {table_name}: SQLite={sqlite_count}, PostgreSQL={pg_count}")
                    validation_passed = False
                else:
                    logger.info(f"✅ Validation {table_name}: {pg_count} lignes")
            
            return validation_passed
            
        finally:
            sqlite_conn.close()
            pg_conn.close()
    
    def create_indexes(self) -> None:
        """Crée les index pour optimiser les performances"""
        pg_conn = self.connect_postgresql()
        
        try:
            cursor = pg_conn.cursor()
            
            # Index pour les tables principales
            indexes = [
                "CREATE INDEX IF NOT EXISTS idx_users_email ON users(email)",
                "CREATE INDEX IF NOT EXISTS idx_users_role ON users(role)",
                "CREATE INDEX IF NOT EXISTS idx_trips_passenger ON trips(passenger_id)",
                "CREATE INDEX IF NOT EXISTS idx_trips_driver ON trips(driver_id)",
                "CREATE INDEX IF NOT EXISTS idx_trips_status ON trips(status)",
                "CREATE INDEX IF NOT EXISTS idx_trips_created ON trips(created_at)",
                "CREATE INDEX IF NOT EXISTS idx_driver_locations_driver ON driver_locations(driver_id)",
                "CREATE INDEX IF NOT EXISTS idx_driver_locations_available ON driver_locations(is_available)",
                "CREATE INDEX IF NOT EXISTS idx_metrics_timestamp ON metrics(timestamp)",
                "CREATE INDEX IF NOT EXISTS idx_metrics_category ON metrics(category)",
                "CREATE INDEX IF NOT EXISTS idx_payments_trip ON payments(trip_id)",
                "CREATE INDEX IF NOT EXISTS idx_payments_status ON payments(status)"
            ]
            
            for index_sql in indexes:
                cursor.execute(index_sql)
                logger.info(f"✅ Index créé: {index_sql.split('ON')[1].split('(')[0].strip()}")
            
            pg_conn.commit()
            logger.info("✅ Tous les index créés")
            
        except Exception as e:
            logger.error(f"❌ Erreur création index: {e}")
            raise
        finally:
            pg_conn.close()
    
    def run_migration(self) -> bool:
        """Exécute la migration complète"""
        start_time = datetime.now()
        logger.info("🚀 DÉBUT DE LA MIGRATION SQLite → PostgreSQL")
        
        try:
            # 1. Récupérer le schéma SQLite
            logger.info("📋 Étape 1: Analyse du schéma SQLite")
            schema = self.get_sqlite_schema()
            
            # 2. Créer le schéma PostgreSQL
            logger.info("🏗️ Étape 2: Création du schéma PostgreSQL")
            self.create_postgresql_schema(schema)
            
            # 3. Migrer les données
            logger.info("📦 Étape 3: Migration des données")
            self.migrate_data(schema)
            
            # 4. Créer les index
            logger.info("⚡ Étape 4: Création des index")
            self.create_indexes()
            
            # 5. Valider la migration
            logger.info("✅ Étape 5: Validation de la migration")
            if not self.validate_migration(schema):
                raise Exception("Validation de la migration échouée")
            
            end_time = datetime.now()
            duration = end_time - start_time
            
            logger.info(f"🎉 MIGRATION RÉUSSIE en {duration.total_seconds():.2f} secondes")
            return True
            
        except Exception as e:
            logger.error(f"❌ MIGRATION ÉCHOUÉE: {e}")
            return False

def load_postgres_config() -> Dict[str, str]:
    """Charge la configuration PostgreSQL"""
    config = {
        'host': os.getenv('POSTGRES_HOST', 'localhost'),
        'port': os.getenv('POSTGRES_PORT', '5432'),
        'database': os.getenv('POSTGRES_DB', 'uber_vtc'),
        'user': os.getenv('POSTGRES_USER', 'ubuntu'),
        'password': os.getenv('POSTGRES_PASSWORD', 'ubuntu123')
    }
    
    # Vérifier que toutes les variables sont définies
    missing = [k for k, v in config.items() if not v]
    if missing:
        logger.error(f"❌ Variables d'environnement manquantes: {missing}")
        sys.exit(1)
    
    return config

def main():
    """Fonction principale"""
    print("🐘 MIGRATION SQLite → PostgreSQL")
    print("=" * 50)
    
    # Configuration
    sqlite_db = "uber_api.db"
    if not os.path.exists(sqlite_db):
        logger.error(f"❌ Base SQLite non trouvée: {sqlite_db}")
        sys.exit(1)
    
    postgres_config = load_postgres_config()
    
    # Confirmation
    print(f"📂 SQLite: {sqlite_db}")
    print(f"🐘 PostgreSQL: {postgres_config['host']}:{postgres_config['port']}/{postgres_config['database']}")
    
    confirm = input("\n⚠️ Continuer la migration ? (y/N): ")
    if confirm.lower() != 'y':
        print("❌ Migration annulée")
        sys.exit(0)
    
    # Migration
    migrator = PostgreSQLMigrator(sqlite_db, postgres_config)
    success = migrator.run_migration()
    
    if success:
        print("\n🎉 Migration terminée avec succès !")
        print("📄 Consultez migration.log pour les détails")
    else:
        print("\n❌ Migration échouée !")
        print("📄 Consultez migration.log pour les erreurs")
        sys.exit(1)

if __name__ == "__main__":
    main()

