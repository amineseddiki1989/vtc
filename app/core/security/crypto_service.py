"""
Service de chiffrement sécurisé pour l'application VTC.
Utilise des algorithmes cryptographiques forts et des pratiques sécurisées.
"""

import os
import base64
import secrets
import hashlib
from typing import Optional, Union, Dict, Any
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import bcrypt
import json
from datetime import datetime, timedelta


class CryptoService:
    """Service de chiffrement centralisé avec algorithmes forts."""
    
    def __init__(self, encryption_password: str = None, encryption_salt: str = None):
        """
        Initialise le service de chiffrement.
        
        Args:
            encryption_password: Mot de passe pour la dérivation de clé
            encryption_salt: Salt pour la dérivation de clé
        """
        self.encryption_password = encryption_password or os.getenv("ENCRYPTION_PASSWORD", "default_password")
        self.encryption_salt = encryption_salt or os.getenv("ENCRYPTION_SALT", "default_salt")
        
        # Dériver les clés de chiffrement
        self.fernet_key = self._derive_fernet_key()
        self.aes_key = self._derive_aes_key()
        
        # Initialiser Fernet pour le chiffrement simple
        self.fernet = Fernet(self.fernet_key)
    
    def _derive_fernet_key(self) -> bytes:
        """Dérive une clé Fernet à partir du mot de passe."""
        password = self.encryption_password.encode()
        salt = self.encryption_salt.encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        key = base64.urlsafe_b64encode(kdf.derive(password))
        return key
    
    def _derive_aes_key(self) -> bytes:
        """Dérive une clé AES-256 à partir du mot de passe."""
        password = self.encryption_password.encode()
        salt = (self.encryption_salt + "_aes").encode()
        
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256 bits
            salt=salt,
            iterations=100000,
            backend=default_backend()
        )
        
        return kdf.derive(password)
    
    def encrypt_simple(self, data: str) -> str:
        """
        Chiffrement simple avec Fernet.
        
        Args:
            data: Données à chiffrer
            
        Returns:
            Données chiffrées en base64
        """
        if not data:
            return ""
        
        try:
            encrypted_data = self.fernet.encrypt(data.encode('utf-8'))
            return base64.urlsafe_b64encode(encrypted_data).decode('utf-8')
        except Exception as e:
            raise ValueError(f"Erreur de chiffrement simple: {e}")
    
    def decrypt_simple(self, encrypted_data: str) -> str:
        """
        Déchiffrement simple avec Fernet.
        
        Args:
            encrypted_data: Données chiffrées en base64
            
        Returns:
            Données déchiffrées
        """
        if not encrypted_data:
            return ""
        
        try:
            decoded_data = base64.urlsafe_b64decode(encrypted_data.encode('utf-8'))
            decrypted_data = self.fernet.decrypt(decoded_data)
            return decrypted_data.decode('utf-8')
        except Exception as e:
            raise ValueError(f"Erreur de déchiffrement simple: {e}")
    
    def encrypt_advanced(self, data: str, additional_data: str = None) -> Dict[str, str]:
        """
        Chiffrement avancé avec AES-256-GCM.
        
        Args:
            data: Données à chiffrer
            additional_data: Données additionnelles pour l'authentification
            
        Returns:
            Dictionnaire avec les données chiffrées et métadonnées
        """
        if not data:
            return {"encrypted": "", "iv": "", "tag": "", "timestamp": ""}
        
        try:
            # Générer un IV aléatoire
            iv = secrets.token_bytes(12)  # 96 bits pour GCM
            
            # Créer le cipher AES-256-GCM
            cipher = Cipher(
                algorithms.AES(self.aes_key),
                modes.GCM(iv),
                backend=default_backend()
            )
            
            encryptor = cipher.encryptor()
            
            # Ajouter des données additionnelles si fournies
            if additional_data:
                encryptor.authenticate_additional_data(additional_data.encode('utf-8'))
            
            # Chiffrer les données
            ciphertext = encryptor.update(data.encode('utf-8')) + encryptor.finalize()
            
            return {
                "encrypted": base64.urlsafe_b64encode(ciphertext).decode('utf-8'),
                "iv": base64.urlsafe_b64encode(iv).decode('utf-8'),
                "tag": base64.urlsafe_b64encode(encryptor.tag).decode('utf-8'),
                "timestamp": datetime.utcnow().isoformat(),
                "algorithm": "AES-256-GCM"
            }
            
        except Exception as e:
            raise ValueError(f"Erreur de chiffrement avancé: {e}")
    
    def decrypt_advanced(self, encrypted_dict: Dict[str, str], additional_data: str = None) -> str:
        """
        Déchiffrement avancé avec AES-256-GCM.
        
        Args:
            encrypted_dict: Dictionnaire avec les données chiffrées
            additional_data: Données additionnelles pour l'authentification
            
        Returns:
            Données déchiffrées
        """
        if not encrypted_dict.get("encrypted"):
            return ""
        
        try:
            # Décoder les composants
            ciphertext = base64.urlsafe_b64decode(encrypted_dict["encrypted"].encode('utf-8'))
            iv = base64.urlsafe_b64decode(encrypted_dict["iv"].encode('utf-8'))
            tag = base64.urlsafe_b64decode(encrypted_dict["tag"].encode('utf-8'))
            
            # Créer le cipher AES-256-GCM
            cipher = Cipher(
                algorithms.AES(self.aes_key),
                modes.GCM(iv, tag),
                backend=default_backend()
            )
            
            decryptor = cipher.decryptor()
            
            # Ajouter des données additionnelles si fournies
            if additional_data:
                decryptor.authenticate_additional_data(additional_data.encode('utf-8'))
            
            # Déchiffrer les données
            plaintext = decryptor.update(ciphertext) + decryptor.finalize()
            
            return plaintext.decode('utf-8')
            
        except Exception as e:
            raise ValueError(f"Erreur de déchiffrement avancé: {e}")
    
    def hash_password(self, password: str) -> str:
        """
        Hache un mot de passe avec bcrypt.
        
        Args:
            password: Mot de passe en clair
            
        Returns:
            Hash du mot de passe
        """
        if not password:
            raise ValueError("Le mot de passe ne peut pas être vide")
        
        # Générer un salt et hacher le mot de passe
        salt = bcrypt.gensalt(rounds=12)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        
        return hashed.decode('utf-8')
    
    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        Vérifie un mot de passe contre son hash.
        
        Args:
            password: Mot de passe en clair
            hashed_password: Hash du mot de passe
            
        Returns:
            True si le mot de passe correspond
        """
        if not password or not hashed_password:
            return False
        
        try:
            return bcrypt.checkpw(
                password.encode('utf-8'),
                hashed_password.encode('utf-8')
            )
        except Exception:
            return False
    
    def generate_secure_token(self, length: int = 32) -> str:
        """
        Génère un token sécurisé.
        
        Args:
            length: Longueur du token
            
        Returns:
            Token sécurisé en base64
        """
        return secrets.token_urlsafe(length)
    
    def generate_secure_key(self, length: int = 32) -> str:
        """
        Génère une clé sécurisée.
        
        Args:
            length: Longueur de la clé en bytes
            
        Returns:
            Clé sécurisée en hexadécimal
        """
        return secrets.token_hex(length)
    
    def hash_data(self, data: str, algorithm: str = "sha256") -> str:
        """
        Hache des données avec l'algorithme spécifié.
        
        Args:
            data: Données à hacher
            algorithm: Algorithme de hachage (sha256, sha512)
            
        Returns:
            Hash des données en hexadécimal
        """
        if not data:
            return ""
        
        if algorithm == "sha256":
            return hashlib.sha256(data.encode('utf-8')).hexdigest()
        elif algorithm == "sha512":
            return hashlib.sha512(data.encode('utf-8')).hexdigest()
        else:
            raise ValueError(f"Algorithme non supporté: {algorithm}")
    
    def encrypt_json(self, data: Dict[str, Any]) -> str:
        """
        Chiffre un objet JSON.
        
        Args:
            data: Dictionnaire à chiffrer
            
        Returns:
            JSON chiffré en base64
        """
        json_str = json.dumps(data, ensure_ascii=False, separators=(',', ':'))
        return self.encrypt_simple(json_str)
    
    def decrypt_json(self, encrypted_json: str) -> Dict[str, Any]:
        """
        Déchiffre un objet JSON.
        
        Args:
            encrypted_json: JSON chiffré en base64
            
        Returns:
            Dictionnaire déchiffré
        """
        if not encrypted_json:
            return {}
        
        json_str = self.decrypt_simple(encrypted_json)
        return json.loads(json_str)
    
    def test_encryption_decryption(self) -> bool:
        """
        Teste le chiffrement/déchiffrement.
        
        Returns:
            True si les tests passent
        """
        try:
            # Test chiffrement simple
            test_data = "Données de test sensibles"
            encrypted = self.encrypt_simple(test_data)
            decrypted = self.decrypt_simple(encrypted)
            
            if decrypted != test_data:
                return False
            
            # Test chiffrement avancé
            encrypted_dict = self.encrypt_advanced(test_data, "metadata")
            decrypted_advanced = self.decrypt_advanced(encrypted_dict, "metadata")
            
            if decrypted_advanced != test_data:
                return False
            
            # Test hachage de mot de passe
            password = "test_password_123"
            hashed = self.hash_password(password)
            
            if not self.verify_password(password, hashed):
                return False
            
            return True
            
        except Exception:
            return False


# Instance globale du service de chiffrement
crypto_service = CryptoService()


def get_crypto_service() -> CryptoService:
    """Retourne l'instance du service de chiffrement."""
    return crypto_service


def initialize_crypto_service(encryption_password: str = None, encryption_salt: str = None) -> CryptoService:
    """
    Initialise le service de chiffrement avec des paramètres personnalisés.
    
    Args:
        encryption_password: Mot de passe de chiffrement
        encryption_salt: Salt de chiffrement
        
    Returns:
        Instance du service de chiffrement
    """
    global crypto_service
    crypto_service = CryptoService(encryption_password, encryption_salt)
    return crypto_service

