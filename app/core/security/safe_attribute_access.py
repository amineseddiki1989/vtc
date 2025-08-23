"""
Module pour l'accès sécurisé aux attributs et la prévention des vulnérabilités de désérialisation.
"""

import logging
from typing import Any, Optional, Dict, List, Union, Type
from functools import wraps

logger = logging.getLogger(__name__)


class SafeAttributeAccess:
    """Classe pour l'accès sécurisé aux attributs."""
    
    # Liste blanche des attributs autorisés
    ALLOWED_ATTRIBUTES = {
        'request': {
            'method', 'url', 'headers', 'query_params', 'path_params',
            'client', 'state', 'scope', 'receive', 'send'
        },
        'client': {
            'host', 'port'
        },
        'state': {
            'user', 'request_id', 'start_time', 'metrics'
        },
        'user': {
            'id', 'email', 'role', 'status', 'is_active', 'is_admin'
        },
        'response': {
            'status_code', 'headers', 'body'
        },
        'settings': {
            'log_level', 'debug', 'environment', 'app_name', 'app_version'
        },
        'info': {
            'data', 'context', 'field_name'
        }
    }
    
    @classmethod
    def safe_getattr(cls, obj: Any, attr_name: str, default: Any = None, 
                     obj_type: Optional[str] = None) -> Any:
        """
        Accès sécurisé aux attributs avec validation.
        
        Args:
            obj: Objet dont on veut accéder à l'attribut
            attr_name: Nom de l'attribut
            default: Valeur par défaut si l'attribut n'existe pas
            obj_type: Type d'objet pour la validation (optionnel)
        
        Returns:
            Valeur de l'attribut ou valeur par défaut
        """
        if obj is None:
            return default
        
        # Validation du nom d'attribut
        if not cls._is_safe_attribute_name(attr_name):
            logger.warning(f"Tentative d'accès à un attribut non sécurisé: {attr_name}")
            return default
        
        # Validation selon le type d'objet
        if obj_type and not cls._is_allowed_attribute(obj_type, attr_name):
            logger.warning(f"Attribut {attr_name} non autorisé pour le type {obj_type}")
            return default
        
        try:
            # Vérifier que l'objet a bien l'attribut
            if hasattr(obj, attr_name):
                value = getattr(obj, attr_name)
                
                # Validation de la valeur retournée
                if cls._is_safe_value(value):
                    return value
                else:
                    logger.warning(f"Valeur non sécurisée pour l'attribut {attr_name}")
                    return default
            else:
                return default
                
        except Exception as e:
            logger.error(f"Erreur lors de l'accès à l'attribut {attr_name}: {e}")
            return default
    
    @classmethod
    def safe_hasattr(cls, obj: Any, attr_name: str, obj_type: Optional[str] = None) -> bool:
        """
        Vérification sécurisée de l'existence d'un attribut.
        
        Args:
            obj: Objet à vérifier
            attr_name: Nom de l'attribut
            obj_type: Type d'objet pour la validation (optionnel)
        
        Returns:
            True si l'attribut existe et est sécurisé, False sinon
        """
        if obj is None:
            return False
        
        # Validation du nom d'attribut
        if not cls._is_safe_attribute_name(attr_name):
            return False
        
        # Validation selon le type d'objet
        if obj_type and not cls._is_allowed_attribute(obj_type, attr_name):
            return False
        
        try:
            return hasattr(obj, attr_name)
        except Exception as e:
            logger.error(f"Erreur lors de la vérification de l'attribut {attr_name}: {e}")
            return False
    
    @classmethod
    def _is_safe_attribute_name(cls, attr_name: str) -> bool:
        """Vérifie si le nom d'attribut est sécurisé."""
        if not isinstance(attr_name, str):
            return False
        
        # Interdire les attributs privés et magiques
        if attr_name.startswith('_'):
            return False
        
        # Interdire les attributs dangereux
        dangerous_attrs = {
            '__class__', '__dict__', '__doc__', '__module__', '__weakref__',
            '__getattribute__', '__setattr__', '__delattr__', '__getattr__',
            '__call__', '__init__', '__new__', '__del__', '__repr__', '__str__',
            'exec', 'eval', 'compile', '__import__', 'open', 'file'
        }
        
        if attr_name in dangerous_attrs:
            return False
        
        # Vérifier que le nom ne contient que des caractères alphanumériques et underscore
        if not attr_name.replace('_', '').isalnum():
            return False
        
        return True
    
    @classmethod
    def _is_allowed_attribute(cls, obj_type: str, attr_name: str) -> bool:
        """Vérifie si l'attribut est autorisé pour ce type d'objet."""
        allowed_attrs = cls.ALLOWED_ATTRIBUTES.get(obj_type, set())
        return attr_name in allowed_attrs
    
    @classmethod
    def _is_safe_value(cls, value: Any) -> bool:
        """Vérifie si la valeur retournée est sécurisée."""
        # Interdire les types dangereux
        dangerous_types = (type, type(lambda: None), type(open))
        
        if isinstance(value, dangerous_types):
            return False
        
        # Autoriser les types de base
        safe_types = (str, int, float, bool, list, dict, tuple, type(None))
        
        if isinstance(value, safe_types):
            return True
        
        # Pour les autres types, vérifier qu'ils ne sont pas dangereux
        if hasattr(value, '__call__') and not hasattr(value, '__self__'):
            # Fonction libre (potentiellement dangereuse)
            return False
        
        return True


def safe_getattr(obj: Any, attr_name: str, default: Any = None, 
                obj_type: Optional[str] = None) -> Any:
    """Fonction utilitaire pour l'accès sécurisé aux attributs."""
    return SafeAttributeAccess.safe_getattr(obj, attr_name, default, obj_type)


def safe_hasattr(obj: Any, attr_name: str, obj_type: Optional[str] = None) -> bool:
    """Fonction utilitaire pour la vérification sécurisée d'attributs."""
    return SafeAttributeAccess.safe_hasattr(obj, attr_name, obj_type)


def secure_attribute_access(obj_type: str):
    """
    Décorateur pour sécuriser l'accès aux attributs dans une fonction.
    
    Args:
        obj_type: Type d'objet pour la validation
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Remplacer getattr et hasattr dans l'espace de noms local
            original_getattr = getattr
            original_hasattr = hasattr
            
            def secure_getattr_wrapper(obj, attr_name, default=None):
                return safe_getattr(obj, attr_name, default, obj_type)
            
            def secure_hasattr_wrapper(obj, attr_name):
                return safe_hasattr(obj, attr_name, obj_type)
            
            # Injection des fonctions sécurisées
            func.__globals__['getattr'] = secure_getattr_wrapper
            func.__globals__['hasattr'] = secure_hasattr_wrapper
            
            try:
                result = func(*args, **kwargs)
            finally:
                # Restaurer les fonctions originales
                func.__globals__['getattr'] = original_getattr
                func.__globals__['hasattr'] = original_hasattr
            
            return result
        return wrapper
    return decorator


class SecureObjectWrapper:
    """Wrapper sécurisé pour les objets."""
    
    def __init__(self, obj: Any, obj_type: str):
        self._obj = obj
        self._obj_type = obj_type
    
    def __getattr__(self, name: str) -> Any:
        return safe_getattr(self._obj, name, obj_type=self._obj_type)
    
    def __hasattr__(self, name: str) -> bool:
        return safe_hasattr(self._obj, name, obj_type=self._obj_type)
    
    def get(self, name: str, default: Any = None) -> Any:
        """Méthode get sécurisée."""
        return safe_getattr(self._obj, name, default, self._obj_type)


def wrap_object_securely(obj: Any, obj_type: str) -> SecureObjectWrapper:
    """Enveloppe un objet dans un wrapper sécurisé."""
    return SecureObjectWrapper(obj, obj_type)

