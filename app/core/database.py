"""
Configuration de la base de données
Module de connexion et gestion de la base de données PostgreSQL
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import QueuePool
import asyncpg
from databases import Database
from config.secure_config import get_config
from app.utils.production_logger import ProductionLogger
import asyncio

logger = ProductionLogger(__name__)
config = get_config()

# Configuration SQLAlchemy
engine = create_engine(
    config.database_url,
    poolclass=QueuePool,
    pool_size=10,
    max_overflow=20,
    pool_recycle=3600,
    echo=config.debug
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# Configuration asynchrone
database = Database(config.database_url)

async def init_db():
    """Initialise la base de données"""
    try:
        await database.connect()
        logger.info("✅ Connexion à la base de données établie")
        return True
    except Exception as e:
        logger.error(f"❌ Erreur de connexion à la base de données: {e}")
        raise

async def close_db():
    """Ferme la connexion à la base de données"""
    try:
        await database.disconnect()
        logger.info("Base de données déconnectée")
    except Exception as e:
        logger.error(f"Erreur lors de la fermeture de la base de données: {e}")

def get_db() -> Session:
    """Générateur de session de base de données"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

async def test_connection() -> bool:
    """Test de connexion à la base de données"""
    try:
        await database.fetch_one("SELECT 1")
        return True
    except Exception:
        return False
