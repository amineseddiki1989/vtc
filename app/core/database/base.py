"""
Configuration de base de données SQLAlchemy.
"""

from sqlalchemy import create_engine, MetaData
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from ..config.settings import get_settings

settings = get_settings()

# Configuration du moteur de base de données
engine = create_engine(
    settings.database_url,
    echo=settings.database_echo,
    connect_args={"check_same_thread": False} if "sqlite" in settings.database_url else {}
)

# Session factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base pour les modèles
Base = declarative_base()

# Métadonnées pour les migrations
metadata = MetaData()


def get_db() -> Generator[Session, None, None]:
    """
    Générateur de session de base de données pour FastAPI.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Crée toutes les tables de base de données.
    """
    Base.metadata.create_all(bind=engine)


def drop_tables():
    """
    Supprime toutes les tables de base de données.
    """
    Base.metadata.drop_all(bind=engine)

