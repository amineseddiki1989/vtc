"""
Module de gestion du mode simple pour l'application VTC.
"""

import logging
import os
from typing import Dict, Any

logger = logging.getLogger(__name__)


class SimpleManager:
    """Gestionnaire du mode simple de l'application."""
    
    def __init__(self):
        self.is_simple_mode = False
        self.simple_config = {}
    
    def init_simple_mode(self) -> None:
        """Initialise le mode simple de l'application."""
        try:
            self.is_simple_mode = True
            self.simple_config = {
                "database_type": "sqlite",
                "cache_enabled": False,
                "metrics_simplified": True,
                "debug_mode": True,
                "rate_limiting_relaxed": True
            }
            logger.info("Mode simple activé avec succès")
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation du mode simple: {e}")
            self.is_simple_mode = False
    
    def get_config(self) -> Dict[str, Any]:
        """Retourne la configuration du mode simple."""
        return self.simple_config
    
    def is_enabled(self) -> bool:
        """Vérifie si le mode simple est activé."""
        return self.is_simple_mode


# Instance globale
simple_manager = SimpleManager()

