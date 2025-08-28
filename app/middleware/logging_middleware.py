"""
Middleware de logging pour FastAPI
Enregistrement des requêtes HTTP et métriques de performance
"""

import time
import uuid
from fastapi import Request, Response
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp
from app.utils.production_logger import ProductionLogger
import json

logger = ProductionLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """
    Middleware pour logger toutes les requêtes HTTP
    Inclut les métriques de performance et l'audit de sécurité
    """

    def __init__(self, app: ASGIApp):
        super().__init__(app)

    async def dispatch(self, request: Request, call_next) -> Response:
        """Traite chaque requête HTTP"""

        # Générer un ID de requête unique
        request_id = str(uuid.uuid4())

        # Informations de base sur la requête
        start_time = time.time()
        method = request.method
        url = str(request.url)
        client_ip = self._get_client_ip(request)
        user_agent = request.headers.get("User-Agent", "Unknown")

        # Ajouter l'ID de requête aux headers
        request.state.request_id = request_id

        # Logger le début de la requête
        logger.info(
            f"Requête {method} {url}",
            request_id=request_id,
            client_ip=client_ip,
            user_agent=user_agent
        )

        # Variables pour capturer les erreurs
        response = None
        error_occurred = False

        try:
            # Traiter la requête
            response = await call_next(request)

        except Exception as e:
            error_occurred = True
            logger.error(
                f"Erreur lors du traitement de la requête {method} {url}: {str(e)}",
                request_id=request_id,
                client_ip=client_ip,
                error_type=type(e).__name__
            )

            # Créer une réponse d'erreur
            response = JSONResponse(
                status_code=500,
                content={"detail": "Erreur interne du serveur", "request_id": request_id}
            )

        finally:
            # Calculer la durée de traitement
            process_time = time.time() - start_time

            # Ajouter les headers de réponse
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Process-Time"] = f"{process_time:.3f}"

            # Logger la fin de la requête
            status_code = response.status_code if response else 500

            log_data = {
                "request_id": request_id,
                "method": method,
                "url": url,
                "status_code": status_code,
                "process_time": round(process_time, 3),
                "client_ip": client_ip,
                "user_agent": user_agent
            }

            if error_occurred:
                logger.error("Requête terminée avec erreur", **log_data)
            elif status_code >= 400:
                logger.warning(f"Requête terminée avec erreur {status_code}", **log_data)
            else:
                logger.info("Requête terminée avec succès", **log_data)

            # Logger les métriques de performance
            if process_time > 2.0:  # Requêtes lentes (> 2 secondes)
                logger.warning(
                    f"Requête lente détectée: {method} {url}",
                    **log_data,
                    performance_alert=True
                )

            # Audit de sécurité pour certaines requêtes
            await self._security_audit(request, response, log_data)

        return response

    def _get_client_ip(self, request: Request) -> str:
        """Récupère l'IP réelle du client (gestion des proxies)"""
        # Vérifier les headers de proxy
        forwarded_for = request.headers.get("X-Forwarded-For")
        if forwarded_for:
            # Prendre la première IP (client original)
            return forwarded_for.split(",")[0].strip()

        real_ip = request.headers.get("X-Real-IP")
        if real_ip:
            return real_ip

        # IP directe
        return request.client.host if request.client else "Unknown"

    async def _security_audit(self, request: Request, response: Response, log_data: dict):
        """Audit de sécurité pour certains événements"""

        # Tentatives d'authentification
        if "/auth/" in str(request.url):
            if response.status_code == 401:
                logger.log_security_event(
                    "failed_authentication",
                    {
                        "client_ip": log_data["client_ip"],
                        "user_agent": log_data["user_agent"],
                        "endpoint": log_data["url"]
                    }
                )
            elif response.status_code == 200 and request.method == "POST":
                logger.log_security_event(
                    "successful_authentication",
                    {
                        "client_ip": log_data["client_ip"],
                        "endpoint": log_data["url"]
                    }
                )

        # Tentatives d'accès aux endpoints protégés
        if response.status_code == 403:
            logger.log_security_event(
                "forbidden_access_attempt",
                {
                    "client_ip": log_data["client_ip"],
                    "user_agent": log_data["user_agent"],
                    "endpoint": log_data["url"]
                }
            )

        # Requêtes suspectes (trop d'erreurs 4xx)
        if 400 <= response.status_code < 500:
            # En production, on pourrait implémenter un compteur
            # pour détecter les patterns d'attaque
            pass

    async def _extract_request_body(self, request: Request) -> dict:
        """Extrait le body de la requête de manière sécurisée"""
        try:
            if request.headers.get("Content-Type", "").startswith("application/json"):
                body = await request.body()
                if body:
                    return json.loads(body.decode())
        except Exception as e:
            logger.warning(f"Impossible de lire le body de la requête: {e}")

        return {}
