"""
Service de métriques de base de données pour surveiller les performances SQL.
"""

import time
import functools
from typing import Any, Callable, Dict, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text, event
from sqlalchemy.engine import Engine
from contextlib import contextmanager

from ..services.metrics_service import get_metrics_collector
from ..models.metrics import MetricType, MetricCategory


class DatabaseMetricsService:
    """Service de surveillance des performances de base de données."""
    
    def __init__(self):
        self.collector = get_metrics_collector()
        self._query_count = 0
        self._slow_query_threshold = 1.0  # 1 seconde
    
    def setup_database_monitoring(self, engine: Engine):
        """Configure le monitoring automatique des requêtes SQL."""
        
        @event.listens_for(engine, "before_cursor_execute")
        def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Avant l'exécution d'une requête."""
            context._query_start_time = time.time()
            context._query_statement = statement
        
        @event.listens_for(engine, "after_cursor_execute")
        def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
            """Après l'exécution d'une requête."""
            if hasattr(context, '_query_start_time'):
                execution_time = time.time() - context._query_start_time
                self._record_query_metrics(statement, execution_time, success=True)
        
        @event.listens_for(engine, "handle_error")
        def receive_handle_error(exception_context):
            """En cas d'erreur SQL."""
            if hasattr(exception_context.execution_context, '_query_start_time'):
                execution_time = time.time() - exception_context.execution_context._query_start_time
                statement = getattr(exception_context.execution_context, '_query_statement', 'unknown')
                self._record_query_metrics(statement, execution_time, success=False, error=str(exception_context.original_exception))
    
    def _record_query_metrics(self, statement: str, execution_time: float, success: bool = True, error: Optional[str] = None):
        """Enregistre les métriques d'une requête SQL."""
        self._query_count += 1
        
        # Analyser le type de requête
        query_type = self._get_query_type(statement)
        table_name = self._extract_table_name(statement)
        
        # Métrique de temps d'exécution
        self.collector.record_metric(
            name="database_query_duration_seconds",
            value=execution_time,
            metric_type=MetricType.TIMER,
            category=MetricCategory.TECHNICAL,
            labels={
                "query_type": query_type,
                "table": table_name,
                "success": str(success),
                "performance_level": self._get_performance_level(execution_time)
            },
            description="Durée d'exécution des requêtes SQL"
        )
        
        # Métrique de comptage des requêtes
        self.collector.record_metric(
            name="database_queries_total",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.TECHNICAL,
            labels={
                "query_type": query_type,
                "table": table_name,
                "success": str(success)
            },
            description="Nombre total de requêtes SQL exécutées"
        )
        
        # Requêtes lentes
        if execution_time > self._slow_query_threshold:
            self.collector.record_metric(
                name="database_slow_queries_total",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.TECHNICAL,
                labels={
                    "query_type": query_type,
                    "table": table_name,
                    "slowness_level": self._get_slowness_level(execution_time)
                },
                description="Nombre de requêtes lentes"
            )
        
        # Erreurs SQL
        if not success and error:
            self.collector.record_metric(
                name="database_query_errors_total",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.TECHNICAL,
                labels={
                    "query_type": query_type,
                    "table": table_name,
                    "error_type": self._categorize_error(error)
                },
                description="Nombre d'erreurs SQL"
            )
    
    def _get_query_type(self, statement: str) -> str:
        """Détermine le type de requête SQL."""
        statement_upper = statement.strip().upper()
        
        if statement_upper.startswith('SELECT'):
            return "SELECT"
        elif statement_upper.startswith('INSERT'):
            return "INSERT"
        elif statement_upper.startswith('UPDATE'):
            return "UPDATE"
        elif statement_upper.startswith('DELETE'):
            return "DELETE"
        elif statement_upper.startswith('CREATE'):
            return "CREATE"
        elif statement_upper.startswith('ALTER'):
            return "ALTER"
        elif statement_upper.startswith('DROP'):
            return "DROP"
        else:
            return "OTHER"
    
    def _extract_table_name(self, statement: str) -> str:
        """Extrait le nom de la table principale de la requête."""
        try:
            statement_upper = statement.strip().upper()
            
            # Pour SELECT
            if 'FROM' in statement_upper:
                parts = statement_upper.split('FROM')[1].strip().split()
                if parts:
                    table = parts[0].strip('(),')
                    return table.lower()
            
            # Pour INSERT
            elif statement_upper.startswith('INSERT INTO'):
                parts = statement_upper.split('INSERT INTO')[1].strip().split()
                if parts:
                    table = parts[0].strip('(),')
                    return table.lower()
            
            # Pour UPDATE
            elif statement_upper.startswith('UPDATE'):
                parts = statement_upper.split('UPDATE')[1].strip().split()
                if parts:
                    table = parts[0].strip('(),')
                    return table.lower()
            
            # Pour DELETE
            elif statement_upper.startswith('DELETE FROM'):
                parts = statement_upper.split('DELETE FROM')[1].strip().split()
                if parts:
                    table = parts[0].strip('(),')
                    return table.lower()
            
            return "unknown"
        except:
            return "unknown"
    
    def _get_performance_level(self, execution_time: float) -> str:
        """Catégorise la performance de la requête."""
        if execution_time < 0.01:  # 10ms
            return "excellent"
        elif execution_time < 0.1:  # 100ms
            return "good"
        elif execution_time < 0.5:  # 500ms
            return "acceptable"
        elif execution_time < 1.0:  # 1s
            return "slow"
        else:
            return "very_slow"
    
    def _get_slowness_level(self, execution_time: float) -> str:
        """Catégorise le niveau de lenteur."""
        if execution_time < 2.0:
            return "moderate"
        elif execution_time < 5.0:
            return "slow"
        elif execution_time < 10.0:
            return "very_slow"
        else:
            return "critical"
    
    def _categorize_error(self, error: str) -> str:
        """Catégorise le type d'erreur SQL."""
        error_lower = error.lower()
        
        if 'timeout' in error_lower or 'time out' in error_lower:
            return "timeout"
        elif 'connection' in error_lower:
            return "connection"
        elif 'syntax' in error_lower:
            return "syntax"
        elif 'constraint' in error_lower or 'foreign key' in error_lower:
            return "constraint"
        elif 'duplicate' in error_lower or 'unique' in error_lower:
            return "duplicate"
        elif 'not found' in error_lower or 'does not exist' in error_lower:
            return "not_found"
        elif 'permission' in error_lower or 'access' in error_lower:
            return "permission"
        else:
            return "other"
    
    @contextmanager
    def monitor_transaction(self, operation_name: str):
        """Monitore une transaction complète."""
        start_time = time.time()
        success = True
        error_msg = None
        
        try:
            yield
        except Exception as e:
            success = False
            error_msg = str(e)
            raise
        finally:
            execution_time = time.time() - start_time
            
            # Métrique de transaction
            self.collector.record_metric(
                name="database_transaction_duration_seconds",
                value=execution_time,
                metric_type=MetricType.TIMER,
                category=MetricCategory.TECHNICAL,
                labels={
                    "operation": operation_name,
                    "success": str(success),
                    "performance_level": self._get_performance_level(execution_time)
                },
                description="Durée des transactions de base de données"
            )
            
            if not success:
                self.collector.record_metric(
                    name="database_transaction_errors_total",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.TECHNICAL,
                    labels={
                        "operation": operation_name,
                        "error_type": self._categorize_error(error_msg) if error_msg else "unknown"
                    },
                    description="Nombre d'erreurs de transaction"
                )
    
    def monitor_connection_pool(self, engine: Engine):
        """Surveille le pool de connexions."""
        pool = engine.pool
        
        # Métriques du pool de connexions
        self.collector.record_metric(
            name="database_connection_pool_size",
            value=pool.size(),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.TECHNICAL,
            description="Taille du pool de connexions"
        )
        
        self.collector.record_metric(
            name="database_connection_pool_checked_in",
            value=pool.checkedin(),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.TECHNICAL,
            description="Connexions disponibles dans le pool"
        )
        
        self.collector.record_metric(
            name="database_connection_pool_checked_out",
            value=pool.checkedout(),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.TECHNICAL,
            description="Connexions utilisées du pool"
        )
        
        # Calcul du taux d'utilisation
        if pool.size() > 0:
            utilization_rate = (pool.checkedout() / pool.size()) * 100
            self.collector.record_metric(
                name="database_connection_pool_utilization_percent",
                value=utilization_rate,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.TECHNICAL,
                labels={"utilization_level": self._get_utilization_level(utilization_rate)},
                description="Taux d'utilisation du pool de connexions"
            )
    
    def _get_utilization_level(self, utilization_percent: float) -> str:
        """Catégorise le niveau d'utilisation du pool."""
        if utilization_percent < 25:
            return "low"
        elif utilization_percent < 50:
            return "moderate"
        elif utilization_percent < 75:
            return "high"
        else:
            return "critical"
    
    def record_table_operation_metrics(self, table_name: str, operation: str, record_count: int = 1):
        """Enregistre des métriques spécifiques à une table."""
        self.collector.record_metric(
            name=f"database_table_{operation}_total",
            value=record_count,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={
                "table": table_name,
                "operation": operation
            },
            description=f"Nombre d'opérations {operation} sur la table {table_name}"
        )
    
    def get_database_health_metrics(self, db: Session) -> Dict[str, Any]:
        """Collecte les métriques de santé de la base de données."""
        try:
            # Test de connectivité
            start_time = time.time()
            db.execute(text("SELECT 1"))
            connectivity_time = time.time() - start_time
            
            self.collector.record_metric(
                name="database_connectivity_check_duration",
                value=connectivity_time,
                metric_type=MetricType.TIMER,
                category=MetricCategory.TECHNICAL,
                description="Temps de vérification de connectivité"
            )
            
            # Statistiques des tables principales
            table_stats = {}
            # Tables autorisées (whitelist pour sécurité)
            allowed_tables = {
                'users': 'users',
                'trips': 'trips', 
                'payments': 'payments',
                'ratings': 'ratings',
                'driver_locations': 'driver_locations'
            }
            
            for table_key, table_name in allowed_tables.items():
                try:
                    # Utilisation de paramètres sécurisés
                    query = text("SELECT COUNT(*) FROM " + table_name)
                    result = db.execute(query).scalar()
                    table_stats[table_key] = result
                    
                    self.collector.record_metric(
                        name="database_table_row_count",
                        value=result,
                        metric_type=MetricType.GAUGE,
                        category=MetricCategory.TECHNICAL,
                        labels={"table": table_key},
                        description=f"Nombre de lignes dans la table {table_key}"
                    )
                except Exception as e:
                    table_stats[table_key] = -1  # Erreur
            
            return {
                "connectivity_time": connectivity_time,
                "table_stats": table_stats,
                "status": "healthy"
            }
            
        except Exception as e:
            self.collector.record_metric(
                name="database_health_check_errors",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.TECHNICAL,
                labels={"error_type": self._categorize_error(str(e))},
                description="Erreurs lors de la vérification de santé de la DB"
            )
            
            return {
                "status": "unhealthy",
                "error": str(e)
            }


# Décorateur pour monitorer les opérations de base de données
def monitor_db_operation(operation_name: str, table_name: str = None):
    """Décorateur pour monitorer les opérations de base de données."""
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            db_metrics = DatabaseMetricsService()
            
            with db_metrics.monitor_transaction(operation_name):
                result = func(*args, **kwargs)
                
                # Enregistrer l'opération réussie
                if table_name:
                    db_metrics.record_table_operation_metrics(table_name, operation_name)
                
                return result
        
        return wrapper
    return decorator


# Instance globale du service
_db_metrics_service = None

def get_database_metrics_service() -> DatabaseMetricsService:
    """Récupère l'instance du service de métriques de base de données."""
    global _db_metrics_service
    if _db_metrics_service is None:
        _db_metrics_service = DatabaseMetricsService()
    return _db_metrics_service

