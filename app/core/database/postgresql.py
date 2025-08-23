"""
Configuration PostgreSQL optimisée pour la production.
Architecture asynchrone avec pool de connexions et monitoring.
"""

import asyncio
import logging
from typing import AsyncGenerator, Optional
from contextlib import asynccontextmanager

import asyncpg
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker
)
from sqlalchemy.pool import NullPool
from sqlalchemy.orm import declarative_base

from ..config.settings import get_settings

logger = logging.getLogger(__name__)

# Base pour les modèles asynchrones
AsyncBase = declarative_base()

class DatabaseManager:
    """Gestionnaire de base de données PostgreSQL asynchrone optimisé."""
    
    def __init__(self):
        self.settings = get_settings()
        self._engine: Optional[AsyncEngine] = None
        self._session_factory: Optional[async_sessionmaker] = None
        self._connection_pool: Optional[asyncpg.Pool] = None
        
    async def initialize(self) -> None:
        """Initialise la connexion à la base de données."""
        try:
            # Configuration du moteur SQLAlchemy asynchrone
            self._engine = create_async_engine(
                self.settings.async_database_url,
                echo=self.settings.database_echo,
                pool_size=self.settings.db_pool_size,
                max_overflow=self.settings.db_max_overflow,
                pool_timeout=self.settings.db_pool_timeout,
                pool_recycle=self.settings.db_pool_recycle,
                pool_pre_ping=True,
                poolclass=NullPool if self.settings.environment == "test" else None,
                connect_args={
                    "server_settings": {
                        "application_name": f"{self.settings.app_name}_v{self.settings.app_version}",
                        "jit": "off"  # Optimisation pour les requêtes courtes
                    }
                }
            )
            
            # Factory de sessions
            self._session_factory = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
            
            # Pool de connexions asyncpg pour les opérations avancées
            self._connection_pool = await asyncpg.create_pool(
                self.settings.database_url,
                min_size=self.settings.asyncpg_min_size,
                max_size=self.settings.asyncpg_max_size,
                command_timeout=self.settings.asyncpg_command_timeout,
                server_settings={
                    "application_name": f"{self.settings.app_name}_asyncpg",
                    "jit": "off"
                }
            )
            
            logger.info("✅ Base de données PostgreSQL initialisée avec succès")
            
        except Exception as e:
            logger.error(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
            raise
    
    async def close(self) -> None:
        """Ferme toutes les connexions à la base de données."""
        try:
            if self._connection_pool:
                await self._connection_pool.close()
                logger.info("Pool asyncpg fermé")
                
            if self._engine:
                await self._engine.dispose()
                logger.info("Moteur SQLAlchemy fermé")
                
        except Exception as e:
            logger.error(f"Erreur lors de la fermeture de la base de données: {e}")
    
    @asynccontextmanager
    async def get_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager pour obtenir une session de base de données."""
        if not self._session_factory:
            raise RuntimeError("Base de données non initialisée")
            
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise
            finally:
                await session.close()
    
    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[asyncpg.Connection, None]:
        """Context manager pour obtenir une connexion asyncpg."""
        if not self._connection_pool:
            raise RuntimeError("Pool de connexions non initialisé")
            
        async with self._connection_pool.acquire() as connection:
            yield connection
    
    async def execute_raw_query(self, query: str, *args) -> list:
        """Exécute une requête SQL brute avec asyncpg."""
        async with self.get_connection() as conn:
            return await conn.fetch(query, *args)
    
    async def health_check(self) -> dict:
        """Vérifie l'état de santé de la base de données."""
        try:
            async with self.get_session() as session:
                result = await session.execute("SELECT 1 as health")
                health_result = result.scalar()
                
            pool_stats = {
                "size": self._connection_pool.get_size(),
                "idle": self._connection_pool.get_idle_size(),
                "max_size": self._connection_pool.get_max_size(),
                "min_size": self._connection_pool.get_min_size()
            } if self._connection_pool else {}
            
            return {
                "status": "healthy" if health_result == 1 else "unhealthy",
                "database": "postgresql",
                "pool_stats": pool_stats,
                "timestamp": asyncio.get_event_loop().time()
            }
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": asyncio.get_event_loop().time()
            }

# Instance globale du gestionnaire
db_manager = DatabaseManager()

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """Dépendance FastAPI pour obtenir une session de base de données."""
    async with db_manager.get_session() as session:
        yield session

async def init_database() -> None:
    """Initialise la base de données au démarrage de l'application."""
    await db_manager.initialize()

async def close_database() -> None:
    """Ferme la base de données à l'arrêt de l'application."""
    await db_manager.close()

