"""
Routes d'authentification
Endpoints pour la gestion des utilisateurs et l'authentification
"""

from fastapi import APIRouter, HTTPException, Depends, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, EmailStr
from typing import Optional
from app.core.auth import auth_manager
from app.utils.production_logger import ProductionLogger

logger = ProductionLogger(__name__)
router = APIRouter()
security = HTTPBearer()

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class RegisterRequest(BaseModel):
    email: EmailStr
    password: str
    first_name: str
    last_name: str
    phone: Optional[str] = None

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int

@router.post("/login", response_model=TokenResponse)
async def login(credentials: LoginRequest):
    """Authentification utilisateur"""
    try:
        # Simulation de vérification en base de données
        # En production: vérifier email/password en base

        if credentials.email == "test@vtc.com" and credentials.password == "password123":
            token_data = {
                "sub": credentials.email,
                "user_id": 1,
                "role": "user"
            }

            access_token = auth_manager.create_access_token(token_data)

            logger.info(f"Connexion réussie pour {credentials.email}")

            return TokenResponse(
                access_token=access_token,
                expires_in=3600
            )
        else:
            logger.warning(f"Tentative de connexion échouée pour {credentials.email}")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Email ou mot de passe incorrect"
            )

    except Exception as e:
        logger.error(f"Erreur lors de la connexion: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur interne du serveur"
        )

@router.post("/register", response_model=TokenResponse)
async def register(user_data: RegisterRequest):
    """Inscription d'un nouvel utilisateur"""
    try:
        # Simulation d'inscription
        # En production: créer l'utilisateur en base

        hashed_password = auth_manager.hash_password(user_data.password)

        token_data = {
            "sub": user_data.email,
            "user_id": 2,  # ID généré par la base
            "role": "user"
        }

        access_token = auth_manager.create_access_token(token_data)

        logger.info(f"Nouvel utilisateur inscrit: {user_data.email}")

        return TokenResponse(
            access_token=access_token,
            expires_in=3600
        )

    except Exception as e:
        logger.error(f"Erreur lors de l'inscription: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Erreur lors de l'inscription"
        )

@router.post("/refresh")
async def refresh_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Rafraîchissement du token"""
    try:
        new_token = auth_manager.refresh_token(credentials.credentials)

        return TokenResponse(
            access_token=new_token,
            expires_in=3600
        )

    except Exception as e:
        logger.error(f"Erreur lors du rafraîchissement: {e}")
        raise

@router.get("/me")
async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """Récupération du profil utilisateur actuel"""
    try:
        payload = auth_manager.verify_token(credentials.credentials)

        # Simulation de récupération des données utilisateur
        user_data = {
            "id": payload.get("user_id"),
            "email": payload.get("sub"),
            "role": payload.get("role"),
            "first_name": "Test",
            "last_name": "User"
        }

        return user_data

    except Exception as e:
        logger.error(f"Erreur lors de la récupération du profil: {e}")
        raise
