"""
Service TOTP pour l'authentification à deux facteurs (2FA).
Module d'amélioration VTC pour la sécurité renforcée.
"""

import pyotp
import qrcode
import io
import base64
import secrets
import time
from typing import Optional, Dict, Any, Tuple
from datetime import datetime, timedelta
from pydantic import BaseModel, Field
from cryptography.fernet import Fernet
import logging

logger = logging.getLogger(__name__)


class TOTPConfig(BaseModel):
    """Configuration pour le service TOTP."""
    issuer_name: str = Field(default="VTC Secure App", description="Nom de l'émetteur")
    window: int = Field(default=1, description="Fenêtre de tolérance pour la validation")
    interval: int = Field(default=30, description="Intervalle en secondes pour les codes")
    digits: int = Field(default=6, description="Nombre de chiffres du code")
    backup_codes_count: int = Field(default=10, description="Nombre de codes de secours")


class TOTPSecret(BaseModel):
    """Modèle pour les secrets TOTP."""
    user_id: str
    secret_key: str
    backup_codes: list[str]
    created_at: datetime
    last_used: Optional[datetime] = None
    is_verified: bool = False


class BackupCode(BaseModel):
    """Modèle pour les codes de secours."""
    code: str
    used_at: Optional[datetime] = None
    is_used: bool = False


class TOTPValidationResult(BaseModel):
    """Résultat de validation TOTP."""
    is_valid: bool
    used_backup_code: bool = False
    remaining_backup_codes: int = 0
    error_message: Optional[str] = None


class TOTPService:
    """Service de gestion TOTP pour l'authentification 2FA."""
    
    def __init__(self, config: Optional[TOTPConfig] = None):
        """Initialise le service TOTP."""
        self.config = config or TOTPConfig()
        self._encryption_key = self._get_encryption_key()
        self._fernet = Fernet(self._encryption_key)
        
    def _get_encryption_key(self) -> bytes:
        """Génère ou récupère la clé de chiffrement pour les secrets."""
        # En production, cette clé devrait être stockée de manière sécurisée
        # et récupérée depuis les variables d'environnement
        return Fernet.generate_key()
    
    def generate_secret(self, user_id: str, user_email: str) -> TOTPSecret:
        """
        Génère un nouveau secret TOTP pour un utilisateur.
        
        Args:
            user_id: Identifiant unique de l'utilisateur
            user_email: Email de l'utilisateur pour le QR code
            
        Returns:
            TOTPSecret: Objet contenant le secret et les codes de secours
        """
        try:
            # Générer un secret aléatoire sécurisé
            secret_key = pyotp.random_base32()
            
            # Générer les codes de secours
            backup_codes = self._generate_backup_codes()
            
            # Créer l'objet secret
            totp_secret = TOTPSecret(
                user_id=user_id,
                secret_key=secret_key,
                backup_codes=backup_codes,
                created_at=datetime.utcnow()
            )
            
            logger.info(f"Secret TOTP généré pour l'utilisateur {user_id}")
            return totp_secret
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du secret TOTP: {e}")
            raise
    
    def _generate_backup_codes(self) -> list[str]:
        """Génère des codes de secours aléatoires."""
        backup_codes = []
        for _ in range(self.config.backup_codes_count):
            # Générer un code de 8 caractères alphanumériques
            code = secrets.token_hex(4).upper()
            backup_codes.append(code)
        return backup_codes
    
    def generate_qr_code(self, totp_secret: TOTPSecret, user_email: str) -> str:
        """
        Génère un QR code pour la configuration TOTP.
        
        Args:
            totp_secret: Secret TOTP de l'utilisateur
            user_email: Email de l'utilisateur
            
        Returns:
            str: QR code encodé en base64
        """
        try:
            # Créer l'objet TOTP
            totp = pyotp.TOTP(
                totp_secret.secret_key,
                interval=self.config.interval,
                digits=self.config.digits
            )
            
            # Générer l'URI pour le QR code
            provisioning_uri = totp.provisioning_uri(
                name=user_email,
                issuer_name=self.config.issuer_name
            )
            
            # Créer le QR code
            qr = qrcode.QRCode(
                version=1,
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=10,
                border=4,
            )
            qr.add_data(provisioning_uri)
            qr.make(fit=True)
            
            # Convertir en image
            img = qr.make_image(fill_color="black", back_color="white")
            
            # Convertir en base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            img_str = base64.b64encode(buffer.getvalue()).decode()
            
            logger.info(f"QR code généré pour l'utilisateur {totp_secret.user_id}")
            return img_str
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération du QR code: {e}")
            raise
    
    def verify_totp_token(self, totp_secret: TOTPSecret, token: str) -> TOTPValidationResult:
        """
        Vérifie un token TOTP ou un code de secours.
        
        Args:
            totp_secret: Secret TOTP de l'utilisateur
            token: Token à vérifier (6 chiffres ou code de secours)
            
        Returns:
            TOTPValidationResult: Résultat de la validation
        """
        try:
            # Nettoyer le token
            token = token.strip().replace(" ", "").upper()
            
            # Vérifier si c'est un code de secours
            if len(token) == 8 and token.isalnum():
                return self._verify_backup_code(totp_secret, token)
            
            # Vérifier si c'est un token TOTP valide
            if len(token) == self.config.digits and token.isdigit():
                return self._verify_totp_code(totp_secret, token)
            
            return TOTPValidationResult(
                is_valid=False,
                error_message="Format de token invalide"
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du token: {e}")
            return TOTPValidationResult(
                is_valid=False,
                error_message="Erreur interne de validation"
            )
    
    def _verify_totp_code(self, totp_secret: TOTPSecret, token: str) -> TOTPValidationResult:
        """Vérifie un code TOTP."""
        try:
            # Créer l'objet TOTP
            totp = pyotp.TOTP(
                totp_secret.secret_key,
                interval=self.config.interval,
                digits=self.config.digits
            )
            
            # Vérifier le token avec une fenêtre de tolérance
            is_valid = totp.verify(token, valid_window=self.config.window)
            
            if is_valid:
                logger.info(f"Token TOTP valide pour l'utilisateur {totp_secret.user_id}")
                return TOTPValidationResult(
                    is_valid=True,
                    remaining_backup_codes=len([c for c in totp_secret.backup_codes if not c.endswith("_USED")])
                )
            else:
                logger.warning(f"Token TOTP invalide pour l'utilisateur {totp_secret.user_id}")
                return TOTPValidationResult(
                    is_valid=False,
                    error_message="Code TOTP invalide ou expiré"
                )
                
        except Exception as e:
            logger.error(f"Erreur lors de la vérification TOTP: {e}")
            return TOTPValidationResult(
                is_valid=False,
                error_message="Erreur de vérification TOTP"
            )
    
    def _verify_backup_code(self, totp_secret: TOTPSecret, code: str) -> TOTPValidationResult:
        """Vérifie un code de secours."""
        try:
            # Chercher le code dans la liste des codes de secours
            for i, backup_code in enumerate(totp_secret.backup_codes):
                if backup_code == code and not backup_code.endswith("_USED"):
                    # Marquer le code comme utilisé
                    totp_secret.backup_codes[i] = f"{backup_code}_USED"
                    
                    remaining_codes = len([c for c in totp_secret.backup_codes if not c.endswith("_USED")])
                    
                    logger.info(f"Code de secours utilisé pour l'utilisateur {totp_secret.user_id}")
                    return TOTPValidationResult(
                        is_valid=True,
                        used_backup_code=True,
                        remaining_backup_codes=remaining_codes
                    )
            
            logger.warning(f"Code de secours invalide pour l'utilisateur {totp_secret.user_id}")
            return TOTPValidationResult(
                is_valid=False,
                error_message="Code de secours invalide ou déjà utilisé"
            )
            
        except Exception as e:
            logger.error(f"Erreur lors de la vérification du code de secours: {e}")
            return TOTPValidationResult(
                is_valid=False,
                error_message="Erreur de vérification du code de secours"
            )
    
    def regenerate_backup_codes(self, totp_secret: TOTPSecret) -> list[str]:
        """
        Régénère les codes de secours pour un utilisateur.
        
        Args:
            totp_secret: Secret TOTP de l'utilisateur
            
        Returns:
            list[str]: Nouveaux codes de secours
        """
        try:
            # Générer de nouveaux codes de secours
            new_backup_codes = self._generate_backup_codes()
            totp_secret.backup_codes = new_backup_codes
            
            logger.info(f"Codes de secours régénérés pour l'utilisateur {totp_secret.user_id}")
            return new_backup_codes
            
        except Exception as e:
            logger.error(f"Erreur lors de la régénération des codes de secours: {e}")
            raise
    
    def encrypt_secret(self, totp_secret: TOTPSecret) -> str:
        """
        Chiffre un secret TOTP pour le stockage.
        
        Args:
            totp_secret: Secret TOTP à chiffrer
            
        Returns:
            str: Secret chiffré encodé en base64
        """
        try:
            # Sérialiser le secret en JSON
            secret_data = totp_secret.model_dump_json()
            
            # Chiffrer les données
            encrypted_data = self._fernet.encrypt(secret_data.encode())
            
            # Encoder en base64 pour le stockage
            return base64.b64encode(encrypted_data).decode()
            
        except Exception as e:
            logger.error(f"Erreur lors du chiffrement du secret: {e}")
            raise
    
    def decrypt_secret(self, encrypted_secret: str) -> TOTPSecret:
        """
        Déchiffre un secret TOTP depuis le stockage.
        
        Args:
            encrypted_secret: Secret chiffré encodé en base64
            
        Returns:
            TOTPSecret: Secret TOTP déchiffré
        """
        try:
            # Décoder depuis base64
            encrypted_data = base64.b64decode(encrypted_secret.encode())
            
            # Déchiffrer les données
            decrypted_data = self._fernet.decrypt(encrypted_data)
            
            # Désérialiser depuis JSON
            secret_dict = eval(decrypted_data.decode())
            return TOTPSecret(**secret_dict)
            
        except Exception as e:
            logger.error(f"Erreur lors du déchiffrement du secret: {e}")
            raise
    
    def is_setup_complete(self, totp_secret: TOTPSecret) -> bool:
        """
        Vérifie si la configuration 2FA est complète pour un utilisateur.
        
        Args:
            totp_secret: Secret TOTP de l'utilisateur
            
        Returns:
            bool: True si la configuration est complète
        """
        return totp_secret.is_verified
    
    def mark_as_verified(self, totp_secret: TOTPSecret) -> None:
        """
        Marque la configuration 2FA comme vérifiée.
        
        Args:
            totp_secret: Secret TOTP de l'utilisateur
        """
        totp_secret.is_verified = True
        totp_secret.last_used = datetime.utcnow()
        logger.info(f"Configuration 2FA vérifiée pour l'utilisateur {totp_secret.user_id}")
    
    def get_current_token(self, totp_secret: TOTPSecret) -> str:
        """
        Génère le token TOTP actuel (pour les tests).
        
        Args:
            totp_secret: Secret TOTP de l'utilisateur
            
        Returns:
            str: Token TOTP actuel
        """
        totp = pyotp.TOTP(
            totp_secret.secret_key,
            interval=self.config.interval,
            digits=self.config.digits
        )
        return totp.now()
    
    def get_time_remaining(self) -> int:
        """
        Retourne le temps restant avant le prochain token.
        
        Returns:
            int: Secondes restantes
        """
        return self.config.interval - (int(time.time()) % self.config.interval)


# Instance globale du service TOTP
totp_service = TOTPService()


def get_totp_service() -> TOTPService:
    """Retourne l'instance du service TOTP."""
    return totp_service

