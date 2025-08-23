"""
Application principale Uber API - Version fonctionnelle sécurisée avec Swagger UI corrigé.
"""

import os
import logging
import sys
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.openapi.docs import get_swagger_ui_html, get_redoc_html
from fastapi.openapi.utils import get_openapi
from sqlalchemy import create_engine

from .core.config.settings import get_settings, validate_production_config
from .core.database.session import get_db, create_tables
from .core.middleware.advanced_rate_limit import AdvancedRateLimitMiddleware, RateLimitConfig, RateLimitAlgorithm
from .core.middleware.metrics_middleware import MetricsMiddleware, BusinessMetricsMiddleware
from .core.middleware.security_monitoring_middleware import SecurityMonitoringMiddleware
from .core.security.security_headers import SecurityHeadersMiddleware
from .core.exceptions import setup_error_handlers, RequestLoggingMiddleware
from .services.metrics_service import start_metrics_collection, stop_metrics_collection
from .core.simple_mode import simple_manager
from .core.service_manager import service_manager
from .api.v1.auth import router as auth_router
from .api.v1.metrics import router as metrics_router
from .api.v1.metrics_public import router as metrics_public_router
from .api.v1.trips import router as trips_router
from .api.v1.websocket import router as websocket_router
from .api.v1.eta import router as eta_router
from .api.v1.notifications import router as notifications_router
from .api.v1.notifications_bulk import router as notifications_bulk_router
from .api.v1.monitoring_simple import router as monitoring_router
from .api.v1.fiscal import router as fiscal_router
from .api.v1.endpoints import location, payment, notifications as notifications_endpoints, metrics as metrics_endpoints
from .api.v1.endpoints import emergency

# Configuration
settings = get_settings()

# Configuration du logging sécurisé
log_level = settings.log_level.upper()
if log_level in ['DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL']:
    logging_level = getattr(logging, log_level)
else:
    logging_level = logging.INFO

logging.basicConfig(
    level=logging_level,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s - %(pathname)s:%(lineno)d',
    handlers=[logging.StreamHandler(sys.stdout)]
)

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestionnaire de cycle de vie de l'application."""
    # Startup
    logger.info(f"Démarrage de {settings.app_name} v{settings.app_version}")
    logger.info(f"Environnement: {settings.environment}")
    
    # Activer le mode simple si nécessaire
    if os.getenv("SIMPLE_MODE", "true").lower() == "true":
        simple_manager.init_simple_mode()
    
    # Initialiser le gestionnaire de services
    service_manager.init_services()
    
    try:
        # Créer les tables de base de données
        create_tables()
        logger.info("Base de données initialisée avec succès")
        
        # Démarrer la collecte de métriques
        start_metrics_collection()
        logger.info("Système de métriques démarré")
        
        # Validation de la configuration en production
        if settings.is_production:
            validate_production_config()
            logger.info("Configuration de production validée")
        
    except Exception as e:
        logger.critical(f"Erreur critique au démarrage: {e}")
        raise RuntimeError(f"Impossible de démarrer l'application: {e}")
    
    yield
    
    # Shutdown
    logger.info(f"Arrêt de {settings.app_name}")
    stop_metrics_collection()
    logger.info("Système de métriques arrêté")


# Création de l'application FastAPI avec configuration Swagger corrigée
app = FastAPI(
    title="VTC API - Système de Transport Algérien",
    version=settings.app_version,
    description="""
    ## API complète pour application VTC avec système fiscal algérien

    Cette API fournit tous les services nécessaires pour une application de transport VTC :
    
    ### Fonctionnalités principales
    * **Authentification sécurisée** - Gestion des utilisateurs avec JWT
    * **Système fiscal algérien** - Calculs conformes à la réglementation DGI
    * **Gestion des trajets** - Création, suivi et historique
    * **Monitoring avancé** - Métriques et surveillance en temps réel
    * **Notifications** - Système de notifications push et bulk
    * **Géolocalisation** - Services de localisation et ETA
    * **Paiements** - Intégration des systèmes de paiement
    
    ### Sécurité
    * Validation stricte des données avec Pydantic
    * Protection contre les attaques courantes (SQL injection, XSS)
    * Rate limiting et monitoring de sécurité
    * Audit trail complet
    
    ### Performance
    * Cache intelligent pour les calculs fiscaux
    * Architecture asynchrone avec FastAPI
    * Optimisations de base de données
    """,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    contact={
        "name": "Support VTC API",
        "email": "support@vtc-api.com",
        "url": "https://vtc-api.com/support"
    },
    license_info={
        "name": "Propriétaire",
        "url": "https://vtc-api.com/license"
    },
    openapi_tags=[
        {
            "name": "Authentication",
            "description": "Gestion des utilisateurs, inscription, connexion et authentification JWT"
        },
        {
            "name": "Fiscal System", 
            "description": "Système fiscal algérien - Calculs de taxes conformes à la réglementation DGI"
        },
        {
            "name": "Trips",
            "description": "Gestion des trajets - Création, suivi, historique et tarification"
        },
        {
            "name": "monitoring",
            "description": "Surveillance système - Métriques, alertes et dashboard de monitoring"
        },
        {
            "name": "Public Metrics",
            "description": "Métriques publiques - Statistiques générales et indicateurs de performance"
        },
        {
            "name": "WebSocket",
            "description": "Communications temps réel - Notifications et mises à jour en direct"
        },
        {
            "name": "ETA",
            "description": "Estimation des temps d'arrivée et calculs de trajets optimaux"
        },
        {
            "name": "Notifications",
            "description": "Système de notifications - Push, email et notifications en masse"
        },
        {
            "name": "Location",
            "description": "Services de géolocalisation - Tracking et positionnement"
        },
        {
            "name": "Payment",
            "description": "Gestion des paiements - Transactions et facturation"
        },
        {
            "name": "Emergency SOS",
            "description": "Services d'urgence - Alertes et assistance d'urgence"
        }
    ]
)

# Configuration des gestionnaires d'erreurs sécurisés
setup_error_handlers(app)

# Configuration du rate limiting avancé
rate_limit_config = RateLimitConfig(
    requests_per_minute=60,
    requests_per_hour=1000,
    burst_limit=15,
    algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    whitelist_ips=["127.0.0.1", "::1"],  # IPs locales
    endpoint_specific_limits={
        "/api/v1/auth/login": 5,
        "/api/v1/auth/register": 3,
        "/api/v1/trips/request": 10,
        "/api/v1/emergency/sos": 2,
        "/api/v1/fiscal/calculate": 20,
        "/api/v1/payment/process": 15
    }
)

# Middlewares (ordre important) - VERSION PRODUCTION CORRIGÉE
app.add_middleware(SecurityMonitoringMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(BusinessMetricsMiddleware)
app.add_middleware(MetricsMiddleware)
app.add_middleware(AdvancedRateLimitMiddleware, config=rate_limit_config)

# MIDDLEWARE NATIFS FASTAPI
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_allowed_origins,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_allowed_methods,
    allow_headers=settings.cors_allowed_headers,
)

# Configuration des assets statiques pour Swagger UI
if not settings.is_production:
    # Créer le répertoire static s'il n'existe pas
    static_dir = os.path.join(os.path.dirname(__file__), "..", "static")
    os.makedirs(static_dir, exist_ok=True)
    
    # Monter les fichiers statiques
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Configuration personnalisée de Swagger UI
def custom_openapi():
    """Configuration OpenAPI personnalisée."""
    if app.openapi_schema:
        return app.openapi_schema
    
    openapi_schema = get_openapi(
        title=settings.app_name,
        version=settings.app_version,
        description="API complète pour service VTC avec système fiscal algérien intégré",
        routes=app.routes,
    )
    
    # Ajout d'informations supplémentaires
    openapi_schema["info"]["contact"] = {
        "name": "Support API VTC Algérie",
        "email": "support@vtc-algerie.com"
    }
    
    openapi_schema["info"]["license"] = {
        "name": "Propriétaire",
        "url": "https://vtc-algerie.com/license"
    }
    
    # Configuration des serveurs
    openapi_schema["servers"] = [
        {
            "url": f"http://localhost:{settings.port}",
            "description": "Serveur de développement"
        }
    ]
    
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi


@app.get("/docs", include_in_schema=False)
async def custom_swagger_ui_html():
    """Documentation Swagger UI personnalisée."""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Documentation non disponible en production")
    
    return get_swagger_ui_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Documentation Interactive",
        swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
        swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        swagger_favicon_url="https://fastapi.tiangolo.com/img/favicon.png",
    )


@app.get("/redoc", include_in_schema=False)
async def redoc_html():
    """Documentation ReDoc."""
    if settings.is_production:
        raise HTTPException(status_code=404, detail="Documentation non disponible en production")
    
    return get_redoc_html(
        openapi_url=app.openapi_url,
        title=f"{app.title} - Documentation ReDoc",
        redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.1.3/bundles/redoc.standalone.js",
    )


# Endpoints de base
@app.get("/", tags=["System"])
async def root():
    """Endpoint racine avec informations détaillées."""
    return {
        "message": f"Bienvenue sur {settings.app_name}",
        "version": settings.app_version,
        "status": "running",
        "environment": settings.environment,
        "documentation": "/docs" if not settings.is_production else "Non disponible en production",
        "health_check": "/health",
        "fiscal_system": "/api/v1/fiscal/health"
    }


@app.get("/health", tags=["System"])
async def health_check():
    """Endpoint de vérification de santé détaillé."""
    return {
        "status": "healthy",
        "version": settings.app_version,
        "environment": settings.environment,
        "timestamp": "2025-08-04T13:00:00Z",
        "services": {
            "database": "operational",
            "metrics": "operational",
            "fiscal_system": "operational"
        }
    }


# Inclusion des routers avec gestion d'erreurs
try:
    app.include_router(auth_router, prefix="/api/v1", tags=["Authentication"])
    app.include_router(metrics_router, prefix="/api/v1", tags=["Metrics"])
    app.include_router(metrics_public_router, prefix="/api/v1", tags=["Public Metrics"])
    app.include_router(trips_router, prefix="/api/v1", tags=["Trips"])
    app.include_router(websocket_router, prefix="/api/v1", tags=["WebSocket"])
    app.include_router(eta_router, prefix="/api/v1", tags=["ETA"])
    app.include_router(notifications_router, prefix="/api/v1", tags=["Notifications"])
    app.include_router(notifications_bulk_router, prefix="/api/v1", tags=["Bulk Notifications"])
    app.include_router(monitoring_router, prefix="/api/v1", tags=["monitoring"])
    app.include_router(fiscal_router, prefix="/api/v1", tags=["Fiscal System"])
    
    # Endpoints spécialisés
    app.include_router(location.router, prefix="/api/v1/location", tags=["Location"])
    app.include_router(payment.router, prefix="/api/v1/payment", tags=["Payment"])
    
    # Import et ajout de l'endpoint de paiement fiscal
    from .api.v1.endpoints import payment_fiscal
    app.include_router(payment_fiscal.router, prefix="/api/v1/payment-fiscal", tags=["Payment Fiscal"])
    
    app.include_router(notifications_endpoints.router, prefix="/api/v1/notifications", tags=["Notification Endpoints"])
    app.include_router(metrics_endpoints.router, prefix="/api/v1/metrics", tags=["Metrics Endpoints"])
    app.include_router(emergency.router, prefix="/api/v1", tags=["Emergency SOS"])
    
    logger.info("Tous les routers ont été inclus avec succès")
    
except Exception as e:
    logger.error(f"Erreur lors de l'inclusion des routers: {e}")
    # Continuer le démarrage même si certains routers échouent


if __name__ == "__main__":
    import uvicorn
    
    uvicorn_config = {
        "app": "app.main:app",
        "host": settings.host,
        "port": settings.port,
        "reload": settings.debug and not settings.is_production,
        "log_level": settings.log_level.lower(),
        "access_log": True,
    }
    
    logger.info(f"Démarrage du serveur sur {settings.host}:{settings.port}")
    uvicorn.run(**uvicorn_config)

