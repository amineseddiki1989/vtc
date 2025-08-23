"""
Endpoints d'authentification sécurisés.
"""

import logging
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from ...core.database.base import get_db
from ...core.security.auth_service import AuthService
from ...core.security.password_service import PasswordService
from ...core.exceptions.base import AuthenticationError, ValidationError, ConflictError
from ...core.validation.input_validator import InputValidator
from ...models.user import User, UserStatus
from ...schemas.user import UserCreate, UserResponse, Token, LoginResponse, UserLogin
from ...core.config.settings import get_settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])
security = HTTPBearer()
auth_service = AuthService()
password_service = PasswordService()
settings = get_settings()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """Dépendance pour obtenir l'utilisateur actuel."""
    try:
        token = credentials.credentials
        payload = auth_service.verify_access_token(token)
        user_id = payload.get("sub")
        
        user = db.query(User).filter(User.id == user_id).first()
        if not user or not user.is_active:
            raise AuthenticationError("Utilisateur non trouvé ou inactif")
        
        return user
    except AuthenticationError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide"
        )


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(user_data: UserCreate, db: Session = Depends(get_db)):
    """Inscription d'un nouvel utilisateur avec validation complète."""
    try:
        # Validation des données d'entrée
        InputValidator.validate_email(user_data.email)
        InputValidator.validate_password(user_data.password)
        InputValidator.validate_phone(user_data.phone)
        
        # Vérifier si l'email existe déjà
        existing_user = db.query(User).filter(User.email == user_data.email).first()
        if existing_user:
            raise ConflictError("Un compte avec cet email existe déjà")
        
        # Vérifier si le téléphone existe déjà
        existing_phone = db.query(User).filter(User.phone == user_data.phone).first()
        if existing_phone:
            raise ConflictError("Un compte avec ce numéro de téléphone existe déjà")
        
        # Créer l'utilisateur avec tous les champs et statut par défaut
        user = User(
            email=user_data.email,
            password_hash=password_service.hash_password(user_data.password),
            first_name=user_data.first_name,
            last_name=user_data.last_name,
            phone=user_data.phone,
            role=user_data.role,
            status=UserStatus.ACTIVE,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow()
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        # Log sécurisé avec informations détaillées
        logger.info(f"Nouvel utilisateur créé - ID: {user.id}, Email: {user.email[:3]}***, Rôle: {user.role}")
        
        return UserResponse(
            id=user.id,
            email=user.email,
            first_name=user.first_name,
            last_name=user.last_name,
            phone=user.phone,
            role=user.role,
            status=user.status,
            created_at=user.created_at,
            updated_at=user.updated_at,
            last_login_at=user.last_login_at
        )
        
    except ConflictError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))
    except ValidationError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e))
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Erreur lors de l'inscription: {type(e).__name__}: {str(e)}")
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, 
            detail="Erreur interne lors de la création du compte"
        )


@router.post("/login", response_model=LoginResponse)
async def login(user_data: UserLogin, db: Session = Depends(get_db)):
    """Connexion utilisateur."""
    try:
        user = db.query(User).filter(User.email == user_data.email).first()
        
        if not user:
            raise AuthenticationError("Email ou mot de passe incorrect")
        
        if user.is_locked:
            raise AuthenticationError("Compte temporairement verrouillé")
        
        if not password_service.verify_password(user_data.password, user.password_hash):
            # Incrémenter les tentatives échouées
            failed_attempts = int(user.failed_login_attempts) + 1
            user.failed_login_attempts = str(failed_attempts)
            
            if failed_attempts >= settings.max_login_attempts:
                user.locked_until = datetime.utcnow() + timedelta(minutes=settings.lockout_duration_minutes)
                logger.warning(f"Compte verrouillé pour l'utilisateur ID: {user.id}")
            
            db.commit()
            raise AuthenticationError("Email ou mot de passe incorrect")
        
        if not user.is_active:
            raise AuthenticationError("Compte désactivé")
        
        # Réinitialiser les tentatives échouées
        user.failed_login_attempts = "0"
        user.locked_until = None
        user.last_login_at = datetime.utcnow()
        db.commit()
        
        # Créer les tokens
        session_id = auth_service.generate_session_id()
        access_token = auth_service.create_access_token(user.id, user.role.value, session_id)
        refresh_token = auth_service.create_refresh_token(user.id, session_id)
        
        logger.info(f"Connexion réussie pour l'utilisateur ID: {user.id}")
        
        return LoginResponse(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_in=settings.access_token_expire_minutes * 60,
            user=UserResponse(
                id=user.id,
                email=user.email,
                first_name=user.first_name,
                last_name=user.last_name,
                phone=user.phone,
                role=user.role,
                status=user.status,
                created_at=user.created_at,
                updated_at=user.updated_at,
                last_login_at=user.last_login_at
            )
        )
        
    except AuthenticationError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=str(e))
    except Exception as e:
        logger.error(f"Erreur lors de la connexion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur interne")


@router.get("/me", response_model=UserResponse)
async def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Informations de l'utilisateur actuel."""
    return current_user


@router.post("/logout")
async def logout(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    current_user: User = Depends(get_current_user)
):
    """Déconnexion utilisateur."""
    try:
        token = credentials.credentials
        auth_service.revoke_token(token)
        logger.info(f"Déconnexion pour l'utilisateur ID: {current_user.id}")
        return {"message": "Déconnexion réussie"}
    except Exception as e:
        logger.error(f"Erreur lors de la déconnexion: {e}")
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail="Erreur interne")

