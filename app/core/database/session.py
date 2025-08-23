"""
Configuration de session de base de données avec support PostgreSQL optimisé.
"""

import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool, QueuePool
from typing import Generator
import logging

from .base import Base
from ..config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

def create_database_engine():
    """Crée le moteur de base de données optimisé selon le type"""
    database_url = settings.database_url
    
    if database_url.startswith("sqlite"):
        # Configuration SQLite (développement)
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.environment == "development"
        )
        logger.info("✅ Moteur SQLite configuré")
        
    elif database_url.startswith("postgresql"):
        # Configuration PostgreSQL (production)
        pool_size = int(os.getenv('POSTGRES_POOL_SIZE', 20))
        max_overflow = int(os.getenv('POSTGRES_MAX_OVERFLOW', 30))
        pool_timeout = int(os.getenv('POSTGRES_POOL_TIMEOUT', 30))
        pool_recycle = int(os.getenv('POSTGRES_POOL_RECYCLE', 3600))
        
        engine = create_engine(
            database_url,
            poolclass=QueuePool,
            pool_size=pool_size,
            max_overflow=max_overflow,
            pool_timeout=pool_timeout,
            pool_recycle=pool_recycle,
            pool_pre_ping=True,  # Vérification des connexions
            echo=settings.environment == "development",
            future=True
        )
        
        # Optimisations PostgreSQL
        @event.listens_for(engine, "connect")
        def set_postgresql_optimizations(dbapi_connection, connection_record):
            with dbapi_connection.cursor() as cursor:
                # Optimisations de performance pour VTC
                cursor.execute("SET statement_timeout = '30s'")
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SET idle_in_transaction_session_timeout = '5min'")
                cursor.execute("SET work_mem = '256MB'")
                cursor.execute("SET maintenance_work_mem = '512MB'")
                cursor.execute("SET effective_cache_size = '2GB'")
                cursor.execute("SET random_page_cost = 1.1")
                cursor.execute("SET seq_page_cost = 1.0")
                # Optimisations spécifiques pour géolocalisation
                cursor.execute("SET enable_seqscan = off")  # Favoriser les index pour les requêtes géo
        
        logger.info(f"✅ Moteur PostgreSQL configuré (pool: {pool_size}, overflow: {max_overflow})")
        
    else:
        raise ValueError(f"Type de base de données non supporté: {database_url}")
    
    return engine

# Création du moteur
engine = create_database_engine()

# Configuration de la session
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    expire_on_commit=False  # Important pour PostgreSQL
)

def create_tables():
    """Créer toutes les tables avec optimisations PostgreSQL."""
    try:
        Base.metadata.create_all(bind=engine)
        
        # Créer des index spécialisés pour PostgreSQL
        if settings.database_url.startswith("postgresql"):
            create_postgresql_indexes()
        
        logger.info("✅ Tables créées avec succès")
    except Exception as e:
        logger.error(f"❌ Erreur création tables: {e}")
        raise

def create_postgresql_indexes():
    """Crée des index optimisés pour PostgreSQL"""
    with engine.connect() as conn:
        # Index géospatiaux pour la géolocalisation
        indexes = [
            # Index composites pour les requêtes fréquentes
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_passenger_status ON trips(passenger_id, status)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_driver_status ON trips(driver_id, status)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_trips_created_status ON trips(created_at, status)",
            
            # Index pour géolocalisation
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_driver_locations_available_coords ON driver_locations(is_available, latitude, longitude) WHERE is_available = true",
            
            # Index pour métriques
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_category_timestamp ON metrics(category, timestamp)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_metrics_timestamp_desc ON metrics(timestamp DESC)",
            
            # Index pour paiements
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_trip_status ON payments(trip_id, status)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_payments_created_status ON payments(created_at, status)",
            
            # Index pour utilisateurs
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_role_status ON users(role, status)",
            "CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_users_created_role ON users(created_at, role)"
        ]
        
        for index_sql in indexes:
            try:
                conn.execute(index_sql)
                logger.info(f"✅ Index créé: {index_sql.split('ON')[1].split('(')[0].strip()}")
            except Exception as e:
                logger.warning(f"⚠️ Index déjà existant ou erreur: {e}")
        
        conn.commit()

def get_db() -> Generator[Session, None, None]:
    """
    Générateur de session de base de données avec gestion d'erreurs améliorée.
    """
    db = SessionLocal()
    try:
        yield db
    except Exception as e:
        db.rollback()
        logger.error(f"❌ Erreur session DB: {e}")
        raise
    finally:
        db.close()

def get_db_session() -> Session:
    """
    Obtenir une session de base de données directe.
    """
    return SessionLocal()

def test_database_connection() -> bool:
    """Test la connexion à la base de données"""
    try:
        from sqlalchemy import text
        with engine.connect() as conn:
            if settings.database_url.startswith("postgresql"):
                result = conn.execute(text("SELECT version()"))
                version = result.fetchone()[0]
                logger.info(f"✅ Connexion PostgreSQL réussie: {version[:50]}...")
            else:
                result = conn.execute(text("SELECT 1"))
                logger.info("✅ Connexion SQLite réussie")
            return True
    except Exception as e:
        logger.error(f"❌ Erreur connexion DB: {e}")
        return False

def get_database_stats() -> dict:
    """Récupère les statistiques de la base de données"""
    try:
        with engine.connect() as conn:
            if settings.database_url.startswith("postgresql"):
                # Statistiques PostgreSQL
                result = conn.execute("""
                    SELECT 
                        schemaname,
                        tablename,
                        n_tup_ins as inserts,
                        n_tup_upd as updates,
                        n_tup_del as deletes,
                        n_live_tup as live_tuples
                    FROM pg_stat_user_tables
                    ORDER BY n_live_tup DESC
                """)
                tables = result.fetchall()
                
                # Taille de la base
                size_result = conn.execute("""
                    SELECT pg_size_pretty(pg_database_size(current_database()))
                """)
                db_size = size_result.fetchone()[0]
                
                return {
                    "type": "postgresql",
                    "size": db_size,
                    "tables": [dict(row) for row in tables]
                }
            else:
                # Statistiques SQLite basiques
                result = conn.execute("""
                    SELECT name FROM sqlite_master WHERE type='table'
                """)
                tables = [row[0] for row in result.fetchall()]
                
                return {
                    "type": "sqlite",
                    "tables": tables
                }
                
    except Exception as e:
        logger.error(f"❌ Erreur récupération stats: {e}")
        return {"error": str(e)}

