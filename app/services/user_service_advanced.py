"""
Service de gestion des utilisateurs avancé.
Gestion complète des profils, vérifications et authentification.
"""

import asyncio
import uuid
import hashlib
import secrets
from datetime import datetime, timezone, timedelta, date
from decimal import Decimal
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass

from sqlalchemy import and_, or_, func, desc, asc
from sqlalchemy.orm import Session, selectinload
from sqlalchemy.ext.asyncio import AsyncSession
from fastapi import HTTPException, status, UploadFile
from passlib.context import CryptContext
import pyotp

from ..models.user_advanced import User, UserDocument, UserRole, UserStatus, VerificationStatus, DocumentType
from ..core.database.postgresql import get_async_session
from ..core.cache.redis_manager import redis_manager
from ..core.logging.production_logger import get_logger, log_performance
from ..core.security.advanced_auth import create_access_token, verify_password, hash_password
from .notification_service import NotificationService
from .file_service import FileService

logger = get_logger(__name__)

@dataclass
class UserRegistrationRequest:
    """Demande d'inscription utilisateur."""
    email: str
    phone: str
    password: str
    first_name: str
    last_name: str
    role: UserRole = UserRole.PASSENGER
    date_of_birth: Optional[date] = None
    language: str = "fr"
    marketing_consent: bool = False

@dataclass
class UserProfileUpdate:
    """Mise à jour de profil utilisateur."""
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    date_of_birth: Optional[date] = None
    gender: Optional[str] = None
    address_line1: Optional[str] = None
    address_line2: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None
    language: Optional[str] = None
    timezone: Optional[str] = None
    notifications_email: Optional[bool] = None
    notifications_sms: Optional[bool] = None
    notifications_push: Optional[bool] = None

@dataclass
class DriverProfileUpdate:
    """Mise à jour spécifique au profil conducteur."""
    driver_license_number: Optional[str] = None
    driver_license_expiry: Optional[date] = None
    driving_experience_years: Optional[int] = None
    professional_driver: Optional[bool] = None

class UserServiceAdvanced:
    """Service avancé de gestion des utilisateurs."""
    
    def __init__(self):
        self.pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
        self.notification_service = NotificationService()
        self.file_service = FileService()
    
    # === INSCRIPTION ET AUTHENTIFICATION ===
    
    @log_performance("user_registration")
    async def register_user(
        self,
        request: UserRegistrationRequest,
        db: AsyncSession
    ) -> Tuple[User, str]:
        """Inscrit un nouvel utilisateur."""
        try:
            # Vérifier l'unicité de l'email et du téléphone
            existing_user = await self._get_user_by_email_or_phone(request.email, request.phone, db)
            if existing_user:
                if existing_user.email == request.email:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Un compte avec cet email existe déjà"
                    )
                else:
                    raise HTTPException(
                        status_code=status.HTTP_409_CONFLICT,
                        detail="Un compte avec ce numéro de téléphone existe déjà"
                    )
            
            # Valider l'âge pour les conducteurs
            if request.role == UserRole.DRIVER and request.date_of_birth:
                age = self._calculate_age(request.date_of_birth)
                if age < 21:
                    raise HTTPException(
                        status_code=status.HTTP_400_BAD_REQUEST,
                        detail="L'âge minimum pour être conducteur est de 21 ans"
                    )
            
            # Créer l'utilisateur
            user = User(
                email=request.email.lower(),
                phone=request.phone,
                first_name=request.first_name.strip(),
                last_name=request.last_name.strip(),
                password_hash=hash_password(request.password),
                role=request.role,
                date_of_birth=request.date_of_birth,
                language=request.language,
                marketing_emails=request.marketing_consent,
                status=UserStatus.PENDING
            )
            
            # Générer le numéro d'utilisateur
            user.user_number = user.generate_user_number()
            
            db.add(user)
            await db.flush()  # Pour obtenir l'ID
            
            # Créer le token d'accès
            access_token = create_access_token(
                data={"sub": str(user.id), "role": user.role}
            )
            
            await db.commit()
            
            # Envoyer l'email de vérification
            await self._send_verification_email(user)
            
            # Envoyer le SMS de vérification
            await self._send_verification_sms(user)
            
            logger.info(f"Nouvel utilisateur inscrit: {user.user_number} ({user.email})")
            
            return user, access_token
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de l'inscription: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'inscription"
            )
    
    @log_performance("user_login")
    async def authenticate_user(
        self,
        email_or_phone: str,
        password: str,
        db: AsyncSession
    ) -> Tuple[User, str]:
        """Authentifie un utilisateur."""
        try:
            # Trouver l'utilisateur
            user = await self._get_user_by_email_or_phone(email_or_phone, email_or_phone, db)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Identifiants incorrects"
                )
            
            # Vérifier si le compte est verrouillé
            if user.account_locked:
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail="Compte temporairement verrouillé. Réessayez plus tard."
                )
            
            # Vérifier le mot de passe
            if not verify_password(password, user.password_hash):
                user.record_failed_login()
                await db.commit()
                
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Identifiants incorrects"
                )
            
            # Vérifier le statut du compte
            if user.status == UserStatus.BANNED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Compte banni"
                )
            elif user.status == UserStatus.SUSPENDED:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Compte suspendu"
                )
            
            # Enregistrer la connexion réussie
            user.record_successful_login()
            
            # Créer le token d'accès
            access_token = create_access_token(
                data={"sub": str(user.id), "role": user.role}
            )
            
            await db.commit()
            
            logger.info(f"Connexion réussie: {user.user_number}")
            
            return user, access_token
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de l'authentification: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'authentification"
            )
    
    # === GESTION DES PROFILS ===
    
    @log_performance("update_user_profile")
    async def update_user_profile(
        self,
        user_id: str,
        update_data: UserProfileUpdate,
        db: AsyncSession
    ) -> User:
        """Met à jour le profil d'un utilisateur."""
        try:
            user = await self._get_user_by_id(user_id, db)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Utilisateur non trouvé"
                )
            
            # Mettre à jour les champs modifiés
            for field, value in update_data.__dict__.items():
                if value is not None:
                    setattr(user, field, value)
            
            user.updated_at = datetime.now(timezone.utc)
            await db.commit()
            
            logger.info(f"Profil mis à jour: {user.user_number}")
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la mise à jour du profil: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la mise à jour"
            )
    
    @log_performance("update_driver_profile")
    async def update_driver_profile(
        self,
        user_id: str,
        update_data: DriverProfileUpdate,
        db: AsyncSession
    ) -> User:
        """Met à jour le profil conducteur."""
        try:
            user = await self._get_user_by_id(user_id, db)
            if not user or user.role != UserRole.DRIVER:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Conducteur non trouvé"
                )
            
            # Mettre à jour les champs conducteur
            for field, value in update_data.__dict__.items():
                if value is not None:
                    setattr(user, field, value)
            
            user.updated_at = datetime.now(timezone.utc)
            await db.commit()
            
            logger.info(f"Profil conducteur mis à jour: {user.user_number}")
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la mise à jour du profil conducteur: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la mise à jour"
            )
    
    # === VÉRIFICATION D'IDENTITÉ ===
    
    @log_performance("verify_email")
    async def verify_email(self, user_id: str, verification_code: str, db: AsyncSession) -> bool:
        """Vérifie l'email d'un utilisateur."""
        try:
            # Vérifier le code en cache
            cache_key = f"email_verification:{user_id}"
            cached_code = await redis_manager.get(cache_key)
            
            if not cached_code or cached_code != verification_code:
                return False
            
            # Marquer l'email comme vérifié
            user = await self._get_user_by_id(user_id, db)
            if user:
                user.email_verified = True
                user.updated_at = datetime.now(timezone.utc)
                
                # Activer le compte si toutes les vérifications sont faites
                if user.phone_verified and user.status == UserStatus.PENDING:
                    user.status = UserStatus.ACTIVE
                
                await db.commit()
                
                # Supprimer le code du cache
                await redis_manager.delete(cache_key)
                
                logger.info(f"Email vérifié: {user.user_number}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'email: {e}")
            return False
    
    @log_performance("verify_phone")
    async def verify_phone(self, user_id: str, verification_code: str, db: AsyncSession) -> bool:
        """Vérifie le téléphone d'un utilisateur."""
        try:
            # Vérifier le code en cache
            cache_key = f"phone_verification:{user_id}"
            cached_code = await redis_manager.get(cache_key)
            
            if not cached_code or cached_code != verification_code:
                return False
            
            # Marquer le téléphone comme vérifié
            user = await self._get_user_by_id(user_id, db)
            if user:
                user.phone_verified = True
                user.updated_at = datetime.now(timezone.utc)
                
                # Activer le compte si toutes les vérifications sont faites
                if user.email_verified and user.status == UserStatus.PENDING:
                    user.status = UserStatus.ACTIVE
                
                await db.commit()
                
                # Supprimer le code du cache
                await redis_manager.delete(cache_key)
                
                logger.info(f"Téléphone vérifié: {user.user_number}")
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de téléphone: {e}")
            return False
    
    # === GESTION DES DOCUMENTS ===
    
    @log_performance("upload_document")
    async def upload_document(
        self,
        user_id: str,
        document_type: DocumentType,
        file: UploadFile,
        document_number: Optional[str] = None,
        expiry_date: Optional[date] = None,
        db: AsyncSession = None
    ) -> UserDocument:
        """Upload un document utilisateur."""
        if db is None:
            async with get_async_session() as db:
                return await self.upload_document(user_id, document_type, file, document_number, expiry_date, db)
        
        try:
            # Vérifier l'utilisateur
            user = await self._get_user_by_id(user_id, db)
            if not user:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Utilisateur non trouvé"
                )
            
            # Valider le fichier
            if not file.content_type.startswith(('image/', 'application/pdf')):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Type de fichier non supporté"
                )
            
            # Sauvegarder le fichier
            file_path = await self.file_service.save_document(
                file=file,
                user_id=user_id,
                document_type=document_type
            )
            
            # Créer l'enregistrement du document
            document = UserDocument(
                user_id=user_id,
                document_type=document_type,
                document_number=document_number,
                file_path=file_path,
                file_name=file.filename,
                file_size=file.size,
                mime_type=file.content_type,
                expiry_date=expiry_date
            )
            
            db.add(document)
            await db.commit()
            
            # Déclencher la vérification automatique
            asyncio.create_task(self._auto_verify_document(str(document.id)))
            
            logger.info(f"Document uploadé: {document_type} pour {user.user_number}")
            
            return document
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de l'upload de document: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de l'upload"
            )
    
    @log_performance("verify_document")
    async def verify_document(
        self,
        document_id: str,
        verifier_id: str,
        approved: bool,
        rejection_reason: Optional[str] = None,
        db: AsyncSession = None
    ) -> UserDocument:
        """Vérifie un document utilisateur."""
        if db is None:
            async with get_async_session() as db:
                return await self.verify_document(document_id, verifier_id, approved, rejection_reason, db)
        
        try:
            # Récupérer le document
            document = await self._get_document_by_id(document_id, db)
            if not document:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Document non trouvé"
                )
            
            # Mettre à jour le statut
            if approved:
                document.verification_status = VerificationStatus.VERIFIED
                document.verified_by = verifier_id
                document.verified_at = datetime.now(timezone.utc)
                document.rejection_reason = None
            else:
                document.verification_status = VerificationStatus.REJECTED
                document.rejection_reason = rejection_reason
            
            document.updated_at = datetime.now(timezone.utc)
            
            # Vérifier si l'utilisateur peut être approuvé comme conducteur
            if approved and document.user.role == UserRole.DRIVER:
                await self._check_driver_approval(str(document.user_id), db)
            
            await db.commit()
            
            # Notifier l'utilisateur
            await self.notification_service.send_document_verification_result(
                user_id=str(document.user_id),
                document_type=document.document_type,
                approved=approved,
                reason=rejection_reason
            )
            
            logger.info(f"Document {'approuvé' if approved else 'rejeté'}: {document_id}")
            
            return document
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la vérification de document: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la vérification"
            )
    
    # === GESTION DES CONDUCTEURS ===
    
    async def _check_driver_approval(self, user_id: str, db: AsyncSession):
        """Vérifie si un conducteur peut être approuvé."""
        try:
            user = await self._get_user_by_id(user_id, db)
            if not user or user.role != UserRole.DRIVER:
                return
            
            # Vérifier les documents requis
            required_docs = [
                DocumentType.IDENTITY_CARD,
                DocumentType.DRIVING_LICENSE,
                DocumentType.BACKGROUND_CHECK
            ]
            
            verified_docs = await self._get_verified_documents(user_id, db)
            verified_types = [doc.document_type for doc in verified_docs]
            
            # Vérifier si tous les documents requis sont vérifiés
            all_verified = all(doc_type in verified_types for doc_type in required_docs)
            
            if all_verified and user.email_verified and user.phone_verified:
                user.driver_approved = True
                user.verification_status = VerificationStatus.VERIFIED
                
                # Notifier l'approbation
                await self.notification_service.send_driver_approval(user_id)
                
                logger.info(f"Conducteur approuvé: {user.user_number}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification d'approbation conducteur: {e}")
    
    @log_performance("set_driver_availability")
    async def set_driver_availability(
        self,
        user_id: str,
        available: bool,
        latitude: Optional[float] = None,
        longitude: Optional[float] = None,
        db: AsyncSession = None
    ) -> User:
        """Définit la disponibilité d'un conducteur."""
        if db is None:
            async with get_async_session() as db:
                return await self.set_driver_availability(user_id, available, latitude, longitude, db)
        
        try:
            user = await self._get_user_by_id(user_id, db)
            if not user or not user.can_drive:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Conducteur non autorisé"
                )
            
            # Mettre à jour la disponibilité
            user.set_driver_availability(available)
            
            # Mettre à jour la localisation si fournie
            if available and latitude is not None and longitude is not None:
                user.update_location(latitude, longitude)
            
            user.updated_at = datetime.now(timezone.utc)
            await db.commit()
            
            logger.info(f"Disponibilité conducteur mise à jour: {user.user_number} -> {'disponible' if available else 'indisponible'}")
            
            return user
            
        except HTTPException:
            raise
        except Exception as e:
            await db.rollback()
            logger.error(f"Erreur lors de la mise à jour de disponibilité: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la mise à jour"
            )
    
    # === RECHERCHE ET FILTRAGE ===
    
    @log_performance("search_users")
    async def search_users(
        self,
        query: Optional[str] = None,
        role: Optional[UserRole] = None,
        status: Optional[UserStatus] = None,
        verification_status: Optional[VerificationStatus] = None,
        page: int = 1,
        page_size: int = 20,
        db: AsyncSession = None
    ) -> Dict[str, Any]:
        """Recherche des utilisateurs."""
        if db is None:
            async with get_async_session() as db:
                return await self.search_users(query, role, status, verification_status, page, page_size, db)
        
        try:
            query_builder = db.query(User)
            
            # Filtres
            if query:
                search_filter = or_(
                    User.first_name.ilike(f"%{query}%"),
                    User.last_name.ilike(f"%{query}%"),
                    User.email.ilike(f"%{query}%"),
                    User.phone.ilike(f"%{query}%"),
                    User.user_number.ilike(f"%{query}%")
                )
                query_builder = query_builder.filter(search_filter)
            
            if role:
                query_builder = query_builder.filter(User.role == role)
            
            if status:
                query_builder = query_builder.filter(User.status == status)
            
            if verification_status:
                query_builder = query_builder.filter(User.verification_status == verification_status)
            
            # Compter le total
            total = await query_builder.count()
            
            # Pagination
            offset = (page - 1) * page_size
            users = await query_builder.offset(offset).limit(page_size).order_by(desc(User.created_at)).all()
            
            return {
                "users": [user.to_dict() for user in users],
                "total": total,
                "page": page,
                "page_size": page_size,
                "total_pages": (total + page_size - 1) // page_size
            }
            
        except Exception as e:
            logger.error(f"Erreur lors de la recherche d'utilisateurs: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la recherche"
            )
    
    # === MÉTHODES UTILITAIRES ===
    
    async def _get_user_by_id(self, user_id: str, db: AsyncSession) -> Optional[User]:
        """Récupère un utilisateur par son ID."""
        result = await db.execute(
            db.query(User)
            .options(selectinload(User.documents))
            .filter(User.id == user_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_user_by_email_or_phone(self, email: str, phone: str, db: AsyncSession) -> Optional[User]:
        """Récupère un utilisateur par email ou téléphone."""
        result = await db.execute(
            db.query(User).filter(
                or_(User.email == email.lower(), User.phone == phone)
            )
        )
        return result.scalar_one_or_none()
    
    async def _get_document_by_id(self, document_id: str, db: AsyncSession) -> Optional[UserDocument]:
        """Récupère un document par son ID."""
        result = await db.execute(
            db.query(UserDocument)
            .options(selectinload(UserDocument.user))
            .filter(UserDocument.id == document_id)
        )
        return result.scalar_one_or_none()
    
    async def _get_verified_documents(self, user_id: str, db: AsyncSession) -> List[UserDocument]:
        """Récupère les documents vérifiés d'un utilisateur."""
        result = await db.execute(
            db.query(UserDocument).filter(
                and_(
                    UserDocument.user_id == user_id,
                    UserDocument.verification_status == VerificationStatus.VERIFIED
                )
            )
        )
        return result.scalars().all()
    
    def _calculate_age(self, birth_date: date) -> int:
        """Calcule l'âge à partir de la date de naissance."""
        today = date.today()
        return today.year - birth_date.year - ((today.month, today.day) < (birth_date.month, birth_date.day))
    
    async def _send_verification_email(self, user: User):
        """Envoie l'email de vérification."""
        try:
            # Générer un code de vérification
            verification_code = secrets.token_hex(3).upper()
            
            # Stocker en cache pour 24 heures
            cache_key = f"email_verification:{user.id}"
            await redis_manager.set(cache_key, verification_code, expire=86400)
            
            # Envoyer l'email
            await self.notification_service.send_email_verification(
                user_id=str(user.id),
                email=user.email,
                code=verification_code,
                name=user.first_name
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi d'email de vérification: {e}")
    
    async def _send_verification_sms(self, user: User):
        """Envoie le SMS de vérification."""
        try:
            # Générer un code de vérification
            verification_code = secrets.randbelow(900000) + 100000  # 6 chiffres
            
            # Stocker en cache pour 10 minutes
            cache_key = f"phone_verification:{user.id}"
            await redis_manager.set(cache_key, str(verification_code), expire=600)
            
            # Envoyer le SMS
            await self.notification_service.send_sms_verification(
                user_id=str(user.id),
                phone=user.phone,
                code=str(verification_code)
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de l'envoi de SMS de vérification: {e}")
    
    async def _auto_verify_document(self, document_id: str):
        """Vérification automatique de document (simulation)."""
        try:
            await asyncio.sleep(5)  # Simulation du traitement
            
            async with get_async_session() as db:
                document = await self._get_document_by_id(document_id, db)
                if document and document.verification_status == VerificationStatus.PENDING:
                    # Simulation: 90% de chance d'approbation automatique avec générateur sécurisé
                    import secrets
                    # Utilisation de secrets.SystemRandom() pour la sécurité
                    secure_random = secrets.SystemRandom()
                    if secure_random.random() < 0.9:
                        await self.verify_document(
                            document_id=document_id,
                            verifier_id="system",
                            approved=True,
                            db=db
                        )
                    else:
                        await self.verify_document(
                            document_id=document_id,
                            verifier_id="system",
                            approved=False,
                            rejection_reason="Document illisible ou incomplet",
                            db=db
                        )
                        
        except Exception as e:
            logger.error(f"Erreur lors de la vérification automatique: {e}")

