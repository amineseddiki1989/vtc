"""
Module de validation des entrées utilisateur.
"""

import re
import phonenumbers
from typing import Any
from ..exceptions.base import ValidationError


class InputValidator:
    """Validateur d'entrées sécurisé."""
    
    @staticmethod
    def validate_email(email: str) -> bool:
        """Valide un email."""
        if not email or len(email) > 254:
            raise ValidationError("Email invalide")
        
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(pattern, email):
            raise ValidationError("Format d'email invalide")
        
        return True
    
    @staticmethod
    def validate_password(password: str) -> bool:
        """Valide un mot de passe."""
        if not password or len(password) < 8:
            raise ValidationError("Le mot de passe doit contenir au moins 8 caractères")
        
        if len(password) > 128:
            raise ValidationError("Le mot de passe est trop long")
        
        # Vérifier la complexité
        if not re.search(r'[A-Z]', password):
            raise ValidationError("Le mot de passe doit contenir au moins une majuscule")
        
        if not re.search(r'[a-z]', password):
            raise ValidationError("Le mot de passe doit contenir au moins une minuscule")
        
        if not re.search(r'\d', password):
            raise ValidationError("Le mot de passe doit contenir au moins un chiffre")
        
        return True
    
    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Valide un numéro de téléphone."""
        if not phone:
            raise ValidationError("Numéro de téléphone requis")
        
        try:
            parsed = phonenumbers.parse(phone, "DZ")  # Algérie par défaut
            if not phonenumbers.is_valid_number(parsed):
                raise ValidationError("Numéro de téléphone invalide")
        except phonenumbers.NumberParseException:
            raise ValidationError("Format de numéro de téléphone invalide")
        
        return True
    
    @staticmethod
    def validate_coordinates(latitude: float, longitude: float) -> bool:
        """Valide des coordonnées géographiques."""
        if not (-90 <= latitude <= 90):
            raise ValidationError("Latitude invalide")
        
        if not (-180 <= longitude <= 180):
            raise ValidationError("Longitude invalide")
        
        return True

