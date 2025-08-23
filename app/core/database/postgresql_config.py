"""
Configuration PostgreSQL pour l'application VTC.
Gestion des connexions, pools et optimisations.
"""

import os
from typing import Optional
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.pool import QueuePool
from sqlalchemy.orm import sessionmaker
import logging

logger = logging.getLogger(__name__)

class PostgreSQLConfig:
    """Configuration PostgreSQL optimisée"""
    
    def __init__(self):
        self.host = os.getenv('POSTGRES_HOST', 'localhost')
        self.port = int(os.getenv('POSTGRES_PORT', 5432))
        self.database = os.getenv('POSTGRES_DB', 'uber_vtc')
        self.username = os.getenv('POSTGRES_USER', 'postgres')
        self.password = os.getenv('POSTGRES_PASSWORD', 'password')
        self.ssl_mode = os.getenv('POSTGRES_SSL_MODE', 'prefer')
        
        # Configuration du pool de connexions
        self.pool_size = int(os.getenv('POSTGRES_POOL_SIZE', 20))
        self.max_overflow = int(os.getenv('POSTGRES_MAX_OVERFLOW', 30))
        self.pool_timeout = int(os.getenv('POSTGRES_POOL_TIMEOUT', 30))
        self.pool_recycle = int(os.getenv('POSTGRES_POOL_RECYCLE', 3600))
        
    @property
    def database_url(self) -> str:
        """URL de connexion PostgreSQL"""
        return (
            f"postgresql://{self.username}:{self.password}@"
            f"{self.host}:{self.port}/{self.database}"
            f"?sslmode={self.ssl_mode}"
        )
    
    def create_engine(self) -> Engine:
        """Crée le moteur SQLAlchemy optimisé"""
        engine = create_engine(
            self.database_url,
            poolclass=QueuePool,
            pool_size=self.pool_size,
            max_overflow=self.max_overflow,
            pool_timeout=self.pool_timeout,
            pool_recycle=self.pool_recycle,
            pool_pre_ping=True,  # Vérification des connexions
            echo=os.getenv('SQL_DEBUG', 'false').lower() == 'true',
            future=True
        )
        
        # Optimisations PostgreSQL
        @event.listens_for(engine, "connect")
        def set_postgresql_optimizations(dbapi_connection, connection_record):
            with dbapi_connection.cursor() as cursor:
                # Optimisations de performance
                cursor.execute("SET statement_timeout = '30s'")
                cursor.execute("SET lock_timeout = '10s'")
                cursor.execute("SET idle_in_transaction_session_timeout = '5min'")
                cursor.execute("SET work_mem = '256MB'")
                cursor.execute("SET maintenance_work_mem = '512MB'")
                cursor.execute("SET effective_cache_size = '2GB'")
                cursor.execute("SET random_page_cost = 1.1")
                cursor.execute("SET seq_page_cost = 1.0")
        
        logger.info(f"✅ Moteur PostgreSQL créé: {self.host}:{self.port}/{self.database}")
        return engine
    
    def create_session_factory(self, engine: Engine):
        """Crée la factory de sessions"""
        return sessionmaker(
            bind=engine,
            autocommit=False,
            autoflush=False,
            expire_on_commit=False
        )
    
    def test_connection(self) -> bool:
        """Test de connexion PostgreSQL"""
        try:
            engine = self.create_engine()
            with engine.connect() as conn:
                result = conn.execute("SELECT version()")
                version = result.fetchone()[0]
                logger.info(f"✅ Connexion PostgreSQL réussie: {version}")
                return True
        except Exception as e:
            logger.error(f"❌ Erreur connexion PostgreSQL: {e}")
            return False

# Instance globale
postgresql_config = PostgreSQLConfig()

