"""
Gestionnaire de fichiers sécurisé pour prévenir les vulnérabilités de traversée de répertoires.
"""

import os
import logging
from pathlib import Path
from typing import Optional, Union, List, BinaryIO, TextIO
from contextlib import contextmanager
import mimetypes
import hashlib

from fastapi import HTTPException, status, UploadFile

logger = logging.getLogger(__name__)


class SecureFileHandler:
    """Gestionnaire de fichiers sécurisé."""
    
    # Répertoires autorisés (chemins absolus)
    ALLOWED_DIRECTORIES = {
        'uploads': '/app/uploads',
        'temp': '/app/temp',
        'static': '/app/static',
        'logs': '/app/logs'
    }
    
    # Extensions de fichiers autorisées
    ALLOWED_EXTENSIONS = {
        'images': {'.jpg', '.jpeg', '.png', '.gif', '.webp', '.svg'},
        'documents': {'.pdf', '.doc', '.docx', '.txt', '.csv'},
        'archives': {'.zip', '.tar', '.gz'},
        'data': {'.json', '.xml', '.yaml', '.yml'}
    }
    
    # Taille maximale des fichiers (en bytes)
    MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
    
    # Types MIME autorisés
    ALLOWED_MIME_TYPES = {
        'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/svg+xml',
        'application/pdf', 'text/plain', 'text/csv',
        'application/json', 'application/xml', 'text/xml',
        'application/zip', 'application/x-tar', 'application/gzip'
    }
    
    @classmethod
    def secure_path_join(cls, base_directory: str, *paths: str) -> Path:
        """
        Joint des chemins de manière sécurisée en prévenant la traversée de répertoires.
        
        Args:
            base_directory: Répertoire de base autorisé
            *paths: Chemins à joindre
            
        Returns:
            Path: Chemin sécurisé
            
        Raises:
            HTTPException: Si le chemin est dangereux
        """
        # Vérifier que le répertoire de base est autorisé
        if base_directory not in cls.ALLOWED_DIRECTORIES:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Répertoire non autorisé: {base_directory}"
            )
        
        base_path = Path(cls.ALLOWED_DIRECTORIES[base_directory])
        
        # Construire le chemin en validant chaque composant
        current_path = base_path
        for path_component in paths:
            if not path_component:
                continue
                
            # Nettoyer le composant de chemin
            clean_component = cls._sanitize_path_component(path_component)
            current_path = current_path / clean_component
        
        # Résoudre le chemin et vérifier qu'il reste dans le répertoire autorisé
        try:
            resolved_path = current_path.resolve()
            base_resolved = base_path.resolve()
            
            # Vérifier que le chemin résolu est bien dans le répertoire autorisé
            if not str(resolved_path).startswith(str(base_resolved)):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Tentative de traversée de répertoires détectée"
                )
            
            return resolved_path
            
        except (OSError, ValueError) as e:
            logger.warning(f"Chemin invalide détecté: {current_path} - {e}")
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Chemin de fichier invalide"
            )
    
    @classmethod
    def _sanitize_path_component(cls, component: str) -> str:
        """Nettoie un composant de chemin."""
        if not isinstance(component, str):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Composant de chemin invalide"
            )
        
        # Supprimer les caractères dangereux
        dangerous_chars = ['..', '/', '\\', ':', '*', '?', '"', '<', '>', '|']
        for char in dangerous_chars:
            if char in component:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Caractère non autorisé dans le nom de fichier: {char}"
                )
        
        # Supprimer les espaces en début/fin
        component = component.strip()
        
        # Vérifier que le composant n'est pas vide
        if not component:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom de fichier vide"
            )
        
        # Limiter la longueur
        if len(component) > 255:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom de fichier trop long"
            )
        
        return component
    
    @classmethod
    def validate_file_upload(cls, file: UploadFile, allowed_categories: List[str] = None) -> dict:
        """
        Valide un fichier uploadé.
        
        Args:
            file: Fichier uploadé
            allowed_categories: Catégories d'extensions autorisées
            
        Returns:
            dict: Informations sur le fichier validé
        """
        if not file.filename:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Nom de fichier manquant"
            )
        
        # Validation de l'extension
        file_extension = Path(file.filename).suffix.lower()
        if allowed_categories:
            allowed_extensions = set()
            for category in allowed_categories:
                if category in cls.ALLOWED_EXTENSIONS:
                    allowed_extensions.update(cls.ALLOWED_EXTENSIONS[category])
            
            if file_extension not in allowed_extensions:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Extension de fichier non autorisée: {file_extension}"
                )
        
        # Validation du type MIME
        if file.content_type and file.content_type not in cls.ALLOWED_MIME_TYPES:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Type de fichier non autorisé: {file.content_type}"
            )
        
        # Validation de la taille (si disponible)
        if hasattr(file, 'size') and file.size and file.size > cls.MAX_FILE_SIZE:
            raise HTTPException(
                status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                detail=f"Fichier trop volumineux. Taille max: {cls.MAX_FILE_SIZE} bytes"
            )
        
        return {
            'filename': cls._sanitize_path_component(file.filename),
            'content_type': file.content_type,
            'extension': file_extension,
            'size': getattr(file, 'size', None)
        }
    
    @classmethod
    @contextmanager
    def secure_open(cls, base_directory: str, filename: str, mode: str = 'r', **kwargs):
        """
        Ouvre un fichier de manière sécurisée.
        
        Args:
            base_directory: Répertoire de base autorisé
            filename: Nom du fichier
            mode: Mode d'ouverture
            **kwargs: Arguments supplémentaires pour open()
        """
        # Construire le chemin sécurisé
        secure_path = cls.secure_path_join(base_directory, filename)
        
        # Vérifier les permissions selon le mode
        if 'w' in mode or 'a' in mode:
            # Mode écriture - créer le répertoire parent si nécessaire
            secure_path.parent.mkdir(parents=True, exist_ok=True)
        elif 'r' in mode:
            # Mode lecture - vérifier que le fichier existe
            if not secure_path.exists():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Fichier non trouvé"
                )
        
        try:
            with open(secure_path, mode, **kwargs) as file:
                yield file
        except PermissionError:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Permissions insuffisantes"
            )
        except OSError as e:
            logger.error(f"Erreur d'accès au fichier {secure_path}: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur d'accès au fichier"
            )
    
    @classmethod
    def secure_save_upload(cls, file: UploadFile, base_directory: str, 
                          filename: Optional[str] = None, 
                          allowed_categories: List[str] = None) -> dict:
        """
        Sauvegarde un fichier uploadé de manière sécurisée.
        
        Args:
            file: Fichier uploadé
            base_directory: Répertoire de destination
            filename: Nom de fichier personnalisé (optionnel)
            allowed_categories: Catégories d'extensions autorisées
            
        Returns:
            dict: Informations sur le fichier sauvegardé
        """
        # Validation du fichier
        file_info = cls.validate_file_upload(file, allowed_categories)
        
        # Déterminer le nom de fichier final
        if filename:
            final_filename = cls._sanitize_path_component(filename)
            # Conserver l'extension originale
            if not final_filename.endswith(file_info['extension']):
                final_filename += file_info['extension']
        else:
            final_filename = file_info['filename']
        
        # Générer un nom unique si le fichier existe déjà
        secure_path = cls.secure_path_join(base_directory, final_filename)
        if secure_path.exists():
            name_part = secure_path.stem
            extension = secure_path.suffix
            counter = 1
            while secure_path.exists():
                new_name = f"{name_part}_{counter}{extension}"
                secure_path = cls.secure_path_join(base_directory, new_name)
                counter += 1
            final_filename = secure_path.name
        
        # Sauvegarder le fichier
        try:
            with cls.secure_open(base_directory, final_filename, 'wb') as dest_file:
                # Lire et écrire par chunks pour éviter les problèmes de mémoire
                chunk_size = 8192
                total_size = 0
                
                while chunk := file.file.read(chunk_size):
                    total_size += len(chunk)
                    
                    # Vérifier la taille totale
                    if total_size > cls.MAX_FILE_SIZE:
                        # Supprimer le fichier partiellement écrit
                        secure_path.unlink(missing_ok=True)
                        raise HTTPException(
                            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                            detail=f"Fichier trop volumineux. Taille max: {cls.MAX_FILE_SIZE} bytes"
                        )
                    
                    dest_file.write(chunk)
            
            # Calculer le hash du fichier pour vérification d'intégrité
            file_hash = cls._calculate_file_hash(secure_path)
            
            return {
                'filename': final_filename,
                'path': str(secure_path),
                'size': total_size,
                'content_type': file_info['content_type'],
                'extension': file_info['extension'],
                'hash': file_hash
            }
            
        except Exception as e:
            # Nettoyer en cas d'erreur
            if secure_path.exists():
                secure_path.unlink(missing_ok=True)
            logger.error(f"Erreur lors de la sauvegarde: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la sauvegarde du fichier"
            )
    
    @classmethod
    def secure_delete(cls, base_directory: str, filename: str) -> bool:
        """
        Supprime un fichier de manière sécurisée.
        
        Args:
            base_directory: Répertoire de base
            filename: Nom du fichier à supprimer
            
        Returns:
            bool: True si supprimé avec succès
        """
        try:
            secure_path = cls.secure_path_join(base_directory, filename)
            
            if secure_path.exists() and secure_path.is_file():
                secure_path.unlink()
                logger.info(f"Fichier supprimé: {secure_path}")
                return True
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Fichier non trouvé"
                )
                
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erreur lors de la suppression: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors de la suppression du fichier"
            )
    
    @classmethod
    def list_directory_secure(cls, base_directory: str, subdirectory: str = "") -> List[dict]:
        """
        Liste le contenu d'un répertoire de manière sécurisée.
        
        Args:
            base_directory: Répertoire de base autorisé
            subdirectory: Sous-répertoire (optionnel)
            
        Returns:
            List[dict]: Liste des fichiers et répertoires
        """
        try:
            if subdirectory:
                secure_path = cls.secure_path_join(base_directory, subdirectory)
            else:
                secure_path = Path(cls.ALLOWED_DIRECTORIES[base_directory])
            
            if not secure_path.exists() or not secure_path.is_dir():
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Répertoire non trouvé"
                )
            
            items = []
            for item in secure_path.iterdir():
                try:
                    stat = item.stat()
                    items.append({
                        'name': item.name,
                        'type': 'directory' if item.is_dir() else 'file',
                        'size': stat.st_size if item.is_file() else None,
                        'modified': stat.st_mtime
                    })
                except (OSError, PermissionError):
                    # Ignorer les fichiers inaccessibles
                    continue
            
            return sorted(items, key=lambda x: (x['type'], x['name']))
            
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Erreur lors du listage: {e}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Erreur lors du listage du répertoire"
            )
    
    @classmethod
    def _calculate_file_hash(cls, file_path: Path) -> str:
        """Calcule le hash SHA256 d'un fichier."""
        hash_sha256 = hashlib.sha256()
        with open(file_path, 'rb') as f:
            for chunk in iter(lambda: f.read(4096), b""):
                hash_sha256.update(chunk)
        return hash_sha256.hexdigest()


# Fonctions utilitaires pour compatibilité
def secure_open(base_directory: str, filename: str, mode: str = 'r', **kwargs):
    """Fonction utilitaire pour l'ouverture sécurisée de fichiers."""
    return SecureFileHandler.secure_open(base_directory, filename, mode, **kwargs)


def secure_path_join(base_directory: str, *paths: str) -> Path:
    """Fonction utilitaire pour la jointure sécurisée de chemins."""
    return SecureFileHandler.secure_path_join(base_directory, *paths)

