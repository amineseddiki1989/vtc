"""
Authentification pour WebSocket.
"""

from typing import Optional
from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from jose import JWTError, jwt

from ..config.settings import get_settings
from ...models.user import User

settings = get_settings()

async def get_current_user_websocket(token: str, db: Session) -> User:
    """
    Authentifier un utilisateur via token JWT pour WebSocket.
    
    Args:
        token: JWT token
        db: Session de base de données
        
    Returns:
        User: Utilisateur authentifié
        
    Raises:
        HTTPException: Si l'authentification échoue
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    
    try:
        # Décoder le token JWT
        payload = jwt.decode(
            token, 
            settings.jwt_secret_key, 
            algorithms=[settings.jwt_algorithm]
        )
        
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
            
    except JWTError:
        raise credentials_exception
    
    # Récupérer l'utilisateur
    user = db.query(User).filter(User.id == user_id).first()
    if user is None:
        raise credentials_exception
        
    return user

