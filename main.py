"""
Application VTC - Point d'entrée principal
Système de gestion de véhicules de transport avec chauffeur
"""

from fastapi import FastAPI, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from contextlib import asynccontextmanager
import uvicorn
import logging

# Imports locaux
from app.core.database import get_db, init_db
from app.core.auth import AuthManager
from app.routes import auth, vehicles, bookings, drivers, admin
from app.middleware.logging_middleware import LoggingMiddleware
from app.utils.production_logger import ProductionLogger
from config.secure_config import SecureConfig

# Configuration du logging
logger = ProductionLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire du cycle de vie de l'application"""
    # Startup
    logger.info("🚀 Démarrage de l'application VTC")
    try:
        await init_db()
        logger.info("✅ Base de données initialisée")
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation de la base de données: {e}")
        raise

    yield

    # Shutdown
    logger.info("🛑 Arrêt de l'application VTC")

# Création de l'application FastAPI
app = FastAPI(
    title="VTC Management System",
    description="Système de gestion complet pour véhicules de transport avec chauffeur",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan
)

# Configuration CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=SecureConfig.get_cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Middleware de logging
app.add_middleware(LoggingMiddleware)

# Gestionnaire d'authentification
security = HTTPBearer()
auth_manager = AuthManager()

async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Middleware d'authentification"""
    try:
        token = credentials.credentials
        user_data = auth_manager.verify_token(token)
        return user_data
    except Exception as e:
        logger.warning(f"Tentative d'authentification échouée: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide ou expiré",
            headers={"WWW-Authenticate": "Bearer"},
        )

# Inclusion des routes
app.include_router(auth.router, prefix="/api/auth", tags=["Authentification"])
app.include_router(vehicles.router, prefix="/api/vehicles", tags=["Véhicules"])
app.include_router(bookings.router, prefix="/api/bookings", tags=["Réservations"])
app.include_router(drivers.router, prefix="/api/drivers", tags=["Chauffeurs"])
app.include_router(admin.router, prefix="/api/admin", tags=["Administration"], dependencies=[Depends(get_current_user)])

@app.get("/")
async def root():
    """Endpoint de santé"""
    return {
        "message": "VTC Management System API",
        "status": "running",
        "version": "1.0.0"
    }

@app.get("/health")
async def health_check():
    """Vérification de la santé de l'application"""
    try:
        # Test de connexion à la base de données
        from app.core.database import test_connection
        db_status = await test_connection()

        return {
            "status": "healthy",
            "database": "connected" if db_status else "disconnected",
            "services": {
                "auth": "operational",
                "booking": "operational",
                "vehicles": "operational"
            }
        }
    except Exception as e:
        logger.error(f"Erreur lors du health check: {e}")
        raise HTTPException(status_code=503, detail="Service indisponible")

if __name__ == "__main__":
    # Configuration pour le développement
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
