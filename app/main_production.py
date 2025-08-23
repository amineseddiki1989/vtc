"""
Application FastAPI optimisée pour la production.
Intégration complète de tous les composants de sécurité et monitoring.
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any

from fastapi import FastAPI, Request, Response, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from fastapi.openapi.docs import get_swagger_ui_html
from fastapi.openapi.utils import get_openapi

# Imports locaux
from .core.config.production_settings import get_settings
from .core.database.postgresql import init_database, close_database
from .core.cache.redis_manager import init_redis, close_redis
from .core.logging.production_logger import setup_logging, RequestLoggingMiddleware
from .core.security.security_headers import (
    SecurityHeadersMiddleware,
    RateLimitMiddleware,
    RequestValidationMiddleware
)
from .core.monitoring.health_checks import health_checker

# Import des routers
from .api.v1.auth import router as auth_router
from .api.v1.trips import router as trips_router
from .api.v1.interfaces import router as interfaces_router

# Configuration du logging dès le démarrage
setup_logging()
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application."""
    logger.info("🚀 Démarrage de l'application Uber API Production")
    
    try:
        # Initialisation des services
        logger.info("Initialisation de la base de données...")
        await init_database()
        
        logger.info("Initialisation de Redis...")
        await init_redis()
        
        logger.info("✅ Tous les services sont initialisés")
        
        # L'application est prête
        yield
        
    except Exception as e:
        logger.error(f"❌ Erreur lors de l'initialisation: {e}")
        raise
    
    finally:
        # Nettoyage lors de l'arrêt
        logger.info("🛑 Arrêt de l'application...")
        
        try:
            await close_redis()
            await close_database()
            logger.info("✅ Nettoyage terminé")
        except Exception as e:
            logger.error(f"❌ Erreur lors du nettoyage: {e}")

def create_production_app() -> FastAPI:
    """Crée l'application FastAPI pour la production."""
    settings = get_settings()
    
    # Configuration de l'application
    app = FastAPI(
        title=settings.app_name,
        version=settings.app_version,
        description="API de transport Uber - Version Production",
        lifespan=lifespan,
        docs_url=None,  # Désactivé par défaut en production
        redoc_url=None,  # Désactivé par défaut en production
        openapi_url="/api/openapi.json" if not settings.is_production else None,
        debug=settings.debug,
        root_path="/api" if settings.is_production else ""
    )
    
    # === MIDDLEWARE DE SÉCURITÉ ===
    
    # Validation des requêtes (en premier)
    app.add_middleware(RequestValidationMiddleware)
    
    # Rate limiting
    app.add_middleware(RateLimitMiddleware)
    
    # Headers de sécurité
    app.add_middleware(SecurityHeadersMiddleware)
    
    # Logging des requêtes
    app.add_middleware(RequestLoggingMiddleware)
    
    # === MIDDLEWARE STANDARD ===
    
    # Compression GZIP
    app.add_middleware(GZipMiddleware, minimum_size=1000)
    
    # Trusted hosts (protection contre Host header attacks)
    if settings.is_production:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["yourdomain.com", "*.yourdomain.com", "localhost"]
        )
    
    # CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.security.cors_allowed_origins,
        allow_credentials=settings.security.cors_allow_credentials,
        allow_methods=settings.security.cors_allowed_methods,
        allow_headers=settings.security.cors_allowed_headers,
        max_age=settings.security.cors_max_age
    )
    
    # === GESTIONNAIRES D'ERREURS ===
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Gestionnaire d'erreurs HTTP personnalisé."""
        logger.warning(
            f"HTTP Exception: {exc.status_code} - {exc.detail}",
            extra={
                "status_code": exc.status_code,
                "detail": exc.detail,
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host if request.client else "unknown"
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "timestamp": "2025-01-07T12:00:00Z",
                    "path": request.url.path
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Gestionnaire d'erreurs générales."""
        logger.error(
            f"Erreur non gérée: {type(exc).__name__}: {str(exc)}",
            extra={
                "exception_type": type(exc).__name__,
                "exception_message": str(exc),
                "path": request.url.path,
                "method": request.method,
                "client_ip": request.client.host if request.client else "unknown"
            },
            exc_info=True
        )
        
        # En production, ne pas exposer les détails de l'erreur
        if settings.is_production:
            message = "Une erreur interne s'est produite"
        else:
            message = str(exc)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": message,
                    "timestamp": "2025-01-07T12:00:00Z",
                    "path": request.url.path
                }
            }
        )
    
    # === ROUTES DE MONITORING ===
    
    @app.get("/health", tags=["Monitoring"])
    async def health_check():
        """Health check complet du système."""
        try:
            health = await health_checker.check_all()
            
            status_code = 200
            if health.status == "unhealthy":
                status_code = 503
            elif health.status == "degraded":
                status_code = 200  # Toujours 200 mais avec warning
            
            return JSONResponse(
                status_code=status_code,
                content=health.dict()
            )
            
        except Exception as e:
            logger.error(f"Erreur lors du health check: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "status": "unhealthy",
                    "error": "Health check failed",
                    "timestamp": "2025-01-07T12:00:00Z"
                }
            )
    
    @app.get("/health/ready", tags=["Monitoring"])
    async def readiness_check():
        """Vérifie si l'application est prête."""
        readiness = await health_checker.get_readiness()
        status_code = 200 if readiness["ready"] else 503
        return JSONResponse(status_code=status_code, content=readiness)
    
    @app.get("/health/live", tags=["Monitoring"])
    async def liveness_check():
        """Vérifie si l'application est vivante."""
        liveness = await health_checker.get_liveness()
        return JSONResponse(status_code=200, content=liveness)
    
    @app.get("/health/{component}", tags=["Monitoring"])
    async def component_health_check(component: str):
        """Health check d'un composant spécifique."""
        try:
            health = await health_checker.check_component(component)
            status_code = 200 if health.status == "healthy" else 503
            return JSONResponse(status_code=status_code, content=health.dict())
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erreur lors du health check du composant {component}: {e}")
            return JSONResponse(
                status_code=503,
                content={
                    "name": component,
                    "status": "unknown",
                    "error": str(e),
                    "timestamp": "2025-01-07T12:00:00Z"
                }
            )
    
    # === ROUTES DE MÉTRIQUES ===
    
    @app.get("/metrics", tags=["Monitoring"])
    async def metrics():
        """Endpoint pour Prometheus metrics."""
        # Ici on pourrait intégrer prometheus_client
        return Response(
            content="# Metrics endpoint - À implémenter avec prometheus_client\n",
            media_type="text/plain"
        )
    
    # === DOCUMENTATION SÉCURISÉE ===
    
    if not settings.is_production:
        @app.get("/docs", include_in_schema=False)
        async def custom_swagger_ui_html():
            """Documentation Swagger sécurisée."""
            return get_swagger_ui_html(
                openapi_url="/api/openapi.json",
                title=f"{settings.app_name} - Documentation",
                swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js",
                swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css",
            )
        
        @app.get("/api/openapi.json", include_in_schema=False)
        async def get_openapi_endpoint():
            """Schema OpenAPI personnalisé."""
            return get_openapi(
                title=settings.app_name,
                version=settings.app_version,
                description="API de transport Uber - Version Production",
                routes=app.routes,
            )
    
    # === ROUTES PRINCIPALES ===
    
    @app.get("/", tags=["Root"])
    async def root():
        """Endpoint racine avec informations de l'API."""
        return {
            "name": settings.app_name,
            "version": settings.app_version,
            "environment": settings.environment,
            "status": "running",
            "timestamp": "2025-01-07T12:00:00Z",
            "docs_url": "/docs" if not settings.is_production else None
        }
    
    # === INCLUSION DES ROUTERS ===
    
    app.include_router(
        auth_router,
        prefix="/api/v1/auth",
        tags=["Authentication"]
    )
    
    app.include_router(
        trips_router,
        prefix="/api/v1/trips",
        tags=["Trips"]
    )
    
    app.include_router(
        interfaces_router,
        prefix="/api/v1/interfaces",
        tags=["Interfaces"]
    )
    
    logger.info(f"✅ Application {settings.app_name} v{settings.app_version} configurée pour {settings.environment}")
    
    return app

# Créer l'instance de l'application
app = create_production_app()

if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    
    # Configuration pour le développement
    uvicorn.run(
        "app.main_production:app",
        host=settings.host,
        port=settings.port,
        reload=not settings.is_production,
        log_level=settings.monitoring.log_level.lower(),
        access_log=True,
        server_header=False,
        date_header=False
    )

