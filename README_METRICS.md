# 📊 Système de Métriques VTC - Guide Complet

## 🎯 Vue d'ensemble

Cette application VTC intègre un système de monitoring complet avec **55+ métriques métier** pour surveiller les performances, la satisfaction client et la santé technique en temps réel.

## 🚀 Installation Rapide

### 1. Configuration Automatique
```bash
# Lancer le script de configuration
python setup_metrics.py
```

### 2. Configuration Manuelle
```bash
# Installer les dépendances
pip install -r requirements.txt

# Créer le fichier .env (voir exemple ci-dessous)
cp .env.example .env

# Lancer l'application
python -m app.main
```

## ⚙️ Configuration

### Fichier .env
```env
# Application
APP_NAME=Uber API
ENVIRONMENT=development
DEBUG=true

# Base de données
DATABASE_URL=sqlite:///./uber_api.db

# Sécurité
SECRET_KEY=your-secret-key-here
JWT_SECRET_KEY=your-jwt-secret-key-here

# Métriques
METRICS_ENABLED=true
METRICS_BUFFER_SIZE=1000
METRICS_FLUSH_INTERVAL=30
```

## 📊 Métriques Disponibles

### 🔐 Authentification (9 métriques)
- `auth_access_tokens_created` - Tokens d'accès créés
- `auth_refresh_tokens_created` - Tokens de rafraîchissement créés
- `auth_token_verified_success` - Vérifications réussies
- `auth_token_expired` - Tokens expirés
- `auth_token_invalid` - Tokens invalides
- `auth_sessions_created` - Sessions créées

### 🚗 Courses (9 métriques)
- `trip_estimation_distance_km` - Distance estimée
- `trip_estimation_price` - Prix estimé
- `trip_requests_by_vehicle_type` - Demandes par véhicule
- `trip_assignment_wait_time` - Temps d'attente attribution
- `trip_completion_revenue` - Revenus générés
- `trip_actual_duration` - Durée réelle
- `trip_cancellations_by_role` - Annulations

### 💰 Tarification (10 métriques)
- `pricing_calculations_by_vehicle_type` - Calculs de prix
- `pricing_base_price` - Prix de base
- `pricing_final_price` - Prix final
- `pricing_surge_multiplier_applied` - Surge pricing
- `pricing_platform_commission` - Commissions
- `pricing_estimated_driver_earnings` - Gains conducteurs

### 📍 Localisation (12 métriques)
- `location_driver_distance_moved` - Distance parcourue
- `location_driver_speed` - Vitesse conducteur
- `location_gps_accuracy` - Précision GPS
- `location_nearby_drivers_found` - Conducteurs à proximité
- `location_trip_positions_recorded` - Positions de course

### ⭐ Satisfaction Client (15 métriques)
- `satisfaction_ratings_created` - Évaluations créées
- `satisfaction_rating_value` - Valeur des notes
- `satisfaction_punctuality_rating` - Ponctualité
- `satisfaction_cleanliness_rating` - Propreté
- `satisfaction_communication_rating` - Communication
- `satisfaction_safety_rating` - Sécurité
- `satisfaction_user_average_rating` - Note moyenne utilisateur

### 🗄️ Base de Données (6 métriques)
- `database_query_duration_seconds` - Durée des requêtes
- `database_queries_total` - Nombre de requêtes
- `database_slow_queries_total` - Requêtes lentes
- `database_connection_pool_utilization` - Utilisation du pool

## 🔌 API des Métriques

### Endpoints Disponibles

#### Métriques en Temps Réel
```http
GET /api/v1/metrics/realtime
Authorization: Bearer <admin_token>
```

#### Historique des Métriques
```http
GET /api/v1/metrics/history?limit=100&category=business
Authorization: Bearer <admin_token>
```

#### Résumé des Métriques
```http
GET /api/v1/metrics/summary
Authorization: Bearer <admin_token>
```

#### Métriques par Utilisateur
```http
GET /api/v1/metrics/user/{user_id}
Authorization: Bearer <admin_token>
```

#### Alertes Actives
```http
GET /api/v1/metrics/alerts
Authorization: Bearer <admin_token>
```

### Exemples de Réponses

#### Résumé des Métriques
```json
{
  "summary": {
    "business": {
      "total_metrics": 45,
      "avg_trip_rating": 4.2,
      "total_revenue": 15420.50,
      "active_drivers": 23
    },
    "technical": {
      "avg_response_time": 0.15,
      "error_rate": 0.02,
      "db_pool_utilization": 45.2
    }
  },
  "period": "last_24h"
}
```

#### Métriques Temps Réel
```json
{
  "metrics": [
    {
      "name": "trip_completion_revenue",
      "value": 850.0,
      "timestamp": "2024-07-05T10:30:00Z",
      "labels": {
        "vehicle_type": "standard",
        "zone": "city_center"
      }
    }
  ]
}
```

## 🧪 Tests

### Lancer les Tests Automatiques
```bash
# Tests complets du système de métriques
python test_metrics_collection.py
```

### Tests Manuels
```bash
# Test de santé de l'application
curl http://localhost:8000/health

# Test des métriques (nécessite un token admin)
curl -H "Authorization: Bearer <admin_token>" \
     http://localhost:8000/api/v1/metrics/summary
```

## 📈 Tableau de Bord

### Métriques Clés à Surveiller

#### 🎯 KPIs Business
1. **Revenus par heure** - `trip_completion_revenue`
2. **Temps d'attente moyen** - `trip_assignment_wait_time`
3. **Note de satisfaction** - `satisfaction_user_average_rating`
4. **Taux d'annulation** - `trip_cancellations_by_role`

#### ⚡ KPIs Techniques
1. **Temps de réponse API** - `http_request_duration`
2. **Taux d'erreur** - `http_request_errors`
3. **Utilisation DB** - `database_connection_pool_utilization`
4. **Requêtes lentes** - `database_slow_queries_total`

### Alertes Recommandées

#### 🚨 Alertes Critiques
- Temps d'attente > 10 minutes
- Note satisfaction < 3.0
- Taux d'erreur > 5%
- Utilisation DB > 90%

#### ⚠️ Alertes d'Avertissement
- Temps d'attente > 5 minutes
- Note satisfaction < 4.0
- Taux d'erreur > 2%
- Utilisation DB > 75%

## 🔧 Personnalisation

### Ajouter de Nouvelles Métriques

#### 1. Dans un Service
```python
from ..services.metrics_service import get_metrics_collector
from ..models.metrics import MetricType, MetricCategory

class MonService:
    def __init__(self):
        self.collector = get_metrics_collector()
    
    def ma_fonction(self):
        # Enregistrer une métrique
        self.collector.record_metric(
            name="mon_service_operation",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={"operation": "create"},
            description="Opération de mon service"
        )
```

#### 2. Avec un Décorateur
```python
from ..core.monitoring.decorators import monitor_business_operation

class MonService:
    @monitor_business_operation("user_creation", "user_management")
    def creer_utilisateur(self, user_data):
        # Logique métier
        return user
```

### Configuration des Alertes

#### Modifier les Seuils
```python
# Dans app/services/metrics_service.py
ALERT_THRESHOLDS = {
    "trip_assignment_wait_time": 600,  # 10 minutes
    "satisfaction_rating": 3.0,
    "error_rate": 0.05  # 5%
}
```

## 🚀 Déploiement en Production

### 1. Variables d'Environnement
```env
ENVIRONMENT=production
DEBUG=false
METRICS_ENABLED=true
DATABASE_URL=postgresql://user:pass@host:5432/db
```

### 2. Monitoring Externe
- Intégration avec Prometheus/Grafana
- Alertes par email/SMS
- Logs centralisés

### 3. Performance
- Buffer de métriques optimisé
- Flush asynchrone
- Compression des données historiques

## 🛠️ Dépannage

### Problèmes Courants

#### Métriques Non Collectées
```bash
# Vérifier le service de métriques
curl http://localhost:8000/api/v1/metrics/health
```

#### Base de Données Lente
```bash
# Analyser les requêtes lentes
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/v1/metrics/database/slow-queries
```

#### Erreurs d'Authentification
```bash
# Vérifier les tokens
curl -H "Authorization: Bearer <token>" \
     http://localhost:8000/api/v1/auth/verify
```

### Logs de Debug
```python
# Activer les logs détaillés
import logging
logging.getLogger("app.services.metrics_service").setLevel(logging.DEBUG)
```

## 📞 Support

### Documentation API Complète
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Fichiers Importants
- `app/services/metrics_service.py` - Service principal
- `app/models/metrics.py` - Modèles de données
- `app/api/v1/metrics.py` - API REST
- `test_metrics_collection.py` - Tests automatiques

### Contribution
1. Fork le projet
2. Créer une branche feature
3. Ajouter des tests
4. Soumettre une pull request

---

🎉 **Félicitations !** Votre application VTC dispose maintenant d'un système de monitoring professionnel complet.

