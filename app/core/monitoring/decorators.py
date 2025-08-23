"""
Décorateurs pour instrumenter facilement les fonctions avec des métriques.
"""

import time
import logging
import asyncio
import functools
from typing import Any, Callable, Dict, Optional, Union
from datetime import datetime

from ...services.metrics_service import get_metrics_collector
from ...models.metrics import MetricType, MetricCategory

logger = logging.getLogger(__name__)


def monitor_function(
    metric_name: Optional[str] = None,
    category: MetricCategory = MetricCategory.SYSTEM,
    labels: Optional[Dict[str, Any]] = None,
    track_errors: bool = True,
    track_performance: bool = True
):
    """
    Décorateur pour monitorer automatiquement une fonction.
    
    Args:
        metric_name: Nom de la métrique (par défaut: nom de la fonction)
        category: Catégorie de la métrique
        labels: Labels additionnels
        track_errors: Suivre les erreurs
        track_performance: Suivre les performances
    """
    def decorator(func: Callable) -> Callable:
        actual_metric_name = metric_name or f"{func.__module__}.{func.__name__}"
        collector = get_metrics_collector()
        
        if asyncio.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start_time = time.time()
                function_labels = (labels or {}).copy()
                function_labels.update({
                    "function": func.__name__,
                    "module": func.__module__
                })
                
                # Métrique d'appel de fonction
                collector.record_metric(
                    name=f"{actual_metric_name}_calls",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=category,
                    labels=function_labels,
                    description=f"Appel de {func.__name__}"
                )
                
                try:
                    result = await func(*args, **kwargs)
                    
                    # Métrique de succès
                    collector.record_metric(
                        name=f"{actual_metric_name}_success",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=category,
                        labels=function_labels,
                        description=f"Succès de {func.__name__}"
                    )
                    
                    return result
                    
                except Exception as e:
                    if track_errors:
                        error_labels = function_labels.copy()
                        error_labels.update({
                            "error_type": type(e).__name__,
                            "error_message": str(e)[:200]
                        })
                        
                        collector.record_metric(
                            name=f"{actual_metric_name}_errors",
                            value=1,
                            metric_type=MetricType.COUNTER,
                            category=category,
                            labels=error_labels,
                            description=f"Erreur dans {func.__name__}"
                        )
                    
                    raise
                    
                finally:
                    if track_performance:
                        duration = time.time() - start_time
                        collector.record_metric(
                            name=f"{actual_metric_name}_duration",
                            value=duration,
                            metric_type=MetricType.TIMER,
                            category=MetricCategory.PERFORMANCE,
                            labels=function_labels,
                            description=f"Durée d'exécution de {func.__name__}"
                        )
            
            return async_wrapper
        
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                start_time = time.time()
                function_labels = (labels or {}).copy()
                function_labels.update({
                    "function": func.__name__,
                    "module": func.__module__
                })
                
                # Métrique d'appel de fonction
                collector.record_metric(
                    name=f"{actual_metric_name}_calls",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=category,
                    labels=function_labels,
                    description=f"Appel de {func.__name__}"
                )
                
                try:
                    result = func(*args, **kwargs)
                    
                    # Métrique de succès
                    collector.record_metric(
                        name=f"{actual_metric_name}_success",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=category,
                        labels=function_labels,
                        description=f"Succès de {func.__name__}"
                    )
                    
                    return result
                    
                except Exception as e:
                    if track_errors:
                        error_labels = function_labels.copy()
                        error_labels.update({
                            "error_type": type(e).__name__,
                            "error_message": str(e)[:200]
                        })
                        
                        collector.record_metric(
                            name=f"{actual_metric_name}_errors",
                            value=1,
                            metric_type=MetricType.COUNTER,
                            category=category,
                            labels=error_labels,
                            description=f"Erreur dans {func.__name__}"
                        )
                    
                    raise
                    
                finally:
                    if track_performance:
                        duration = time.time() - start_time
                        collector.record_metric(
                            name=f"{actual_metric_name}_duration",
                            value=duration,
                            metric_type=MetricType.TIMER,
                            category=MetricCategory.PERFORMANCE,
                            labels=function_labels,
                            description=f"Durée d'exécution de {func.__name__}"
                        )
            
            return sync_wrapper
    
    return decorator


def monitor_database_operation(
    operation_type: str = "query",
    table_name: Optional[str] = None
):
    """
    Décorateur spécialisé pour les opérations de base de données.
    
    Args:
        operation_type: Type d'opération (query, insert, update, delete)
        table_name: Nom de la table concernée
    """
    def decorator(func: Callable) -> Callable:
        collector = get_metrics_collector()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            labels = {
                "operation": operation_type,
                "function": func.__name__,
                "table": table_name or "unknown"
            }
            
            # Métrique d'opération DB
            collector.record_metric(
                name="database_operations_total",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.SYSTEM,
                labels=labels,
                description=f"Opération DB {operation_type}"
            )
            
            try:
                result = func(*args, **kwargs)
                
                # Métrique de succès DB
                collector.record_metric(
                    name="database_operations_success",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.SYSTEM,
                    labels=labels,
                    description=f"Succès opération DB {operation_type}"
                )
                
                return result
                
            except Exception as e:
                error_labels = labels.copy()
                error_labels.update({
                    "error_type": type(e).__name__
                })
                
                collector.record_metric(
                    name="database_operations_errors",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.SYSTEM,
                    labels=error_labels,
                    description=f"Erreur opération DB {operation_type}"
                )
                
                raise
                
            finally:
                duration = time.time() - start_time
                collector.record_metric(
                    name="database_operation_duration",
                    value=duration,
                    metric_type=MetricType.TIMER,
                    category=MetricCategory.PERFORMANCE,
                    labels=labels,
                    description=f"Durée opération DB {operation_type}"
                )
        
        return wrapper
    
    return decorator


def monitor_business_operation(
    operation_name: str,
    business_entity: str,
    track_value: bool = False,
    value_field: Optional[str] = None
):
    """
    Décorateur pour monitorer les opérations métier.
    
    Args:
        operation_name: Nom de l'opération métier
        business_entity: Entité métier concernée (trip, user, payment, etc.)
        track_value: Suivre une valeur numérique
        value_field: Champ contenant la valeur à suivre
    """
    def decorator(func: Callable) -> Callable:
        collector = get_metrics_collector()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            labels = {
                "operation": operation_name,
                "entity": business_entity,
                "function": func.__name__
            }
            
            # Métrique d'opération métier
            collector.record_metric(
                name=f"business_{business_entity}_{operation_name}",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels=labels,
                description=f"Opération {operation_name} sur {business_entity}"
            )
            
            try:
                result = func(*args, **kwargs)
                
                # Suivre une valeur spécifique si demandé
                if track_value and value_field and result:
                    if hasattr(result, value_field):
                        value = getattr(result, value_field)
                        if isinstance(value, (int, float)):
                            collector.record_metric(
                                name=f"business_{business_entity}_{value_field}",
                                value=value,
                                metric_type=MetricType.GAUGE,
                                category=MetricCategory.BUSINESS,
                                labels=labels,
                                description=f"Valeur {value_field} pour {business_entity}"
                            )
                
                return result
                
            except Exception as e:
                error_labels = labels.copy()
                error_labels.update({
                    "error_type": type(e).__name__
                })
                
                collector.record_metric(
                    name=f"business_{business_entity}_{operation_name}_errors",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels=error_labels,
                    description=f"Erreur {operation_name} sur {business_entity}"
                )
                
                raise
                
            finally:
                duration = time.time() - start_time
                collector.record_metric(
                    name=f"business_{business_entity}_{operation_name}_duration",
                    value=duration,
                    metric_type=MetricType.TIMER,
                    category=MetricCategory.PERFORMANCE,
                    labels=labels,
                    description=f"Durée {operation_name} sur {business_entity}"
                )
        
        return wrapper
    
    return decorator


def monitor_performance(
    metric_name: Optional[str] = None,
    threshold_warning: float = 1.0,
    threshold_critical: float = 5.0
):
    """
    Décorateur spécialisé pour le monitoring de performance.
    
    Args:
        metric_name: Nom de la métrique de performance
        threshold_warning: Seuil d'alerte (secondes)
        threshold_critical: Seuil critique (secondes)
    """
    def decorator(func: Callable) -> Callable:
        actual_metric_name = metric_name or f"performance_{func.__name__}"
        collector = get_metrics_collector()
        
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start_time = time.time()
            
            try:
                result = func(*args, **kwargs)
                return result
                
            finally:
                duration = time.time() - start_time
                
                labels = {
                    "function": func.__name__,
                    "module": func.__module__
                }
                
                # Métrique de performance
                collector.record_metric(
                    name=actual_metric_name,
                    value=duration,
                    metric_type=MetricType.TIMER,
                    category=MetricCategory.PERFORMANCE,
                    labels=labels,
                    description=f"Performance de {func.__name__}"
                )
                
                # Alertes de performance
                if duration > threshold_critical:
                    collector.record_metric(
                        name=f"{actual_metric_name}_critical",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.PERFORMANCE,
                        labels=labels,
                        description=f"Performance critique de {func.__name__}"
                    )
                elif duration > threshold_warning:
                    collector.record_metric(
                        name=f"{actual_metric_name}_warning",
                        value=1,
                        metric_type=MetricType.COUNTER,
                        category=MetricCategory.PERFORMANCE,
                        labels=labels,
                        description=f"Performance dégradée de {func.__name__}"
                    )
        
        return wrapper
    
    return decorator


class MetricsContext:
    """Context manager pour collecter des métriques dans un bloc de code."""
    
    def __init__(
        self,
        metric_name: str,
        category: MetricCategory = MetricCategory.SYSTEM,
        labels: Optional[Dict[str, Any]] = None,
        description: Optional[str] = None
    ):
        self.metric_name = metric_name
        self.category = category
        self.labels = labels or {}
        self.description = description
        self.collector = get_metrics_collector()
        self.start_time = None
    
    def __enter__(self):
        self.start_time = time.time()
        
        # Métrique de début
        self.collector.record_metric(
            name=f"{self.metric_name}_started",
            value=1,
            metric_type=MetricType.COUNTER,
            category=self.category,
            labels=self.labels,
            description=f"Début de {self.description or self.metric_name}"
        )
        
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        duration = time.time() - self.start_time if self.start_time else 0
        
        if exc_type is None:
            # Succès
            self.collector.record_metric(
                name=f"{self.metric_name}_completed",
                value=1,
                metric_type=MetricType.COUNTER,
                category=self.category,
                labels=self.labels,
                description=f"Fin de {self.description or self.metric_name}"
            )
        else:
            # Erreur
            error_labels = self.labels.copy()
            error_labels.update({
                "error_type": exc_type.__name__ if exc_type else "unknown"
            })
            
            self.collector.record_metric(
                name=f"{self.metric_name}_failed",
                value=1,
                metric_type=MetricType.COUNTER,
                category=self.category,
                labels=error_labels,
                description=f"Échec de {self.description or self.metric_name}"
            )
        
        # Durée
        self.collector.record_metric(
            name=f"{self.metric_name}_duration",
            value=duration,
            metric_type=MetricType.TIMER,
            category=MetricCategory.PERFORMANCE,
            labels=self.labels,
            description=f"Durée de {self.description or self.metric_name}"
        )
    
    def record_value(self, name: str, value: Union[int, float], metric_type: MetricType = MetricType.GAUGE):
        """Enregistre une valeur dans le contexte."""
        self.collector.record_metric(
            name=f"{self.metric_name}_{name}",
            value=value,
            metric_type=metric_type,
            category=self.category,
            labels=self.labels,
            description=f"{name} pour {self.description or self.metric_name}"
        )

