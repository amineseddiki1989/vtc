"""
Schémas Pydantic pour les utilisateurs.
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, EmailStr, ConfigDict

from ..models.user import UserRole, UserStatus


class UserBase(BaseModel):
    """Schéma de base pour les utilisateurs."""
    email: EmailStr


class UserCreate(UserBase):
    """Schéma pour créer un utilisateur."""
    password: str = Field(..., min_length=8, max_length=128)
    first_name: str = Field(..., min_length=1, max_length=100)
    last_name: str = Field(..., min_length=1, max_length=100)
    phone: str = Field(..., min_length=10, max_length=20)
    role: Optional[UserRole] = UserRole.PASSENGER


class UserLogin(BaseModel):
    """Schéma pour la connexion."""
    email: EmailStr
    password: str


class UserUpdate(BaseModel):
    """Schéma pour mettre à jour un utilisateur."""
    email: Optional[EmailStr] = None
    role: Optional[UserRole] = None
    status: Optional[UserStatus] = None


class UserResponse(UserBase):
    """Schéma de réponse utilisateur."""
    model_config = ConfigDict(from_attributes=True)
    
    id: str
    role: UserRole
    status: UserStatus
    created_at: datetime
    updated_at: datetime
    last_login_at: Optional[datetime] = None


class Token(BaseModel):
    """Schéma de réponse token."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class LoginResponse(BaseModel):
    """Schéma de réponse login avec informations utilisateur."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserResponse


class TokenData(BaseModel):
    """Données du token."""
    user_id: Optional[str] = None
    role: Optional[str] = None
    session_id: Optional[str] = None

