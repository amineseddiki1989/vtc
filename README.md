# 🚗 VTC Management System

Application complète de gestion de véhicules de transport avec chauffeur (VTC) développée avec FastAPI.

## 🚀 Fonctionnalités

### ✅ Fonctionnalités Implémentées
- **Authentification JWT** sécurisée avec tokens d'accès
- **Logging de production** avec rotation des fichiers et audit de sécurité  
- **Configuration sécurisée** avec validation Pydantic V2
- **Middleware de logging** pour audit complet des requêtes
- **Validation métier avancée** avec règles de gestion personnalisées
- **Gestion utilisateur avancée** avec préférences et 2FA
- **Architecture modulaire** et extensible

### 🔧 Fixes Techniques Appliqués
- ✅ **Fix AttributeError** : Import explicite de `logging.handlers`
- ✅ **Fix ValidationInfo** : Compatibilité Pydantic V2 avec `ValidationError`
- ✅ **Fix Pydantic V2** : Migration complète vers la nouvelle version
- ✅ **Architecture sécurisée** : Hashage bcrypt, tokens JWT, audit de sécurité

## 📁 Structure du Projet

```
vtc/
├── main.py                          # Point d'entrée de l'application
├── requirements.txt                 # Dépendances Python
├── .env.example                     # Variables d'environnement exemple
├── app/
│   ├── core/
│   │   ├── auth.py                  # Gestionnaire d'authentification JWT
│   │   └── database.py              # Configuration base de données
│   ├── models/
│   │   └── user_advanced.py         # Modèles utilisateurs avancés
│   ├── routes/
│   │   ├── auth.py                  # Routes d'authentification
│   │   ├── vehicles.py              # Routes véhicules
│   │   ├── bookings.py              # Routes réservations
│   │   ├── drivers.py               # Routes chauffeurs
│   │   └── admin.py                 # Routes administration
│   ├── services/                    # Services métier
│   ├── middleware/
│   │   └── logging_middleware.py    # Middleware de logging
│   ├── utils/
│   │   └── production_logger.py     # Logger de production (fix AttributeError)
│   └── validators/
│       └── business_logic_validator.py # Validateur métier (fix Pydantic V2)
├── config/
│   └── secure_config.py             # Configuration sécurisée (fix ValidationInfo)
├── backend/                         # Configuration Docker
├── frontend/                        # Configuration Docker Frontend
├── database/
│   └── init.sql                     # Script d'initialisation DB
└── scripts/
    └── deploy.sh                    # Script de déploiement
```

## 🔧 Installation et Démarrage

### Prérequis
- Python 3.9+
- PostgreSQL 13+
- Redis (optionnel)

### Installation locale

1. **Cloner le dépôt**
   ```bash
   git clone https://github.com/amineseddiki1989/vtc.git
   cd vtc
   ```

2. **Créer l'environnement virtuel**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Linux/Mac
   # ou
   venv\Scripts\activate     # Windows
   ```

3. **Installer les dépendances**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configuration**
   ```bash
   cp .env.example .env
   # Éditer le fichier .env avec vos configurations
   ```

5. **Initialiser la base de données**
   ```bash
   # Créer la base de données PostgreSQL
   createdb vtc_db

   # Appliquer les migrations (si alembic configuré)
   alembic upgrade head
   ```

6. **Démarrer l'application**
   ```bash
   # Mode développement
   uvicorn main:app --reload --host 0.0.0.0 --port 8000

   # Mode production
   gunicorn main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
   ```

### Démarrage avec Docker

```bash
# Construire et démarrer tous les services
docker-compose up -d

# Voir les logs
docker-compose logs -f

# Arrêter les services
docker-compose down
```

## 🛡️ Sécurité

### Authentification
- **JWT tokens** avec expiration configurable
- **Hachage bcrypt** pour les mots de passe
- **2FA optionnel** avec TOTP
- **Rate limiting** sur les tentatives de connexion

### Audit et Logging
- **Logging complet** de toutes les requêtes avec IDs uniques
- **Audit de sécurité** pour tentatives d'authentification
- **Monitoring des performances** avec alertes requêtes lentes
- **Rotation automatique** des fichiers de logs

### Configuration
- **Variables d'environnement** pour toutes les configurations sensibles
- **Validation Pydantic** de toutes les configurations
- **Masquage automatique** des données sensibles dans les logs

## 📋 API Documentation

Une fois l'application démarrée, accédez à :
- **Swagger UI** : http://localhost:8000/docs
- **ReDoc** : http://localhost:8000/redoc

### Endpoints principaux

#### Authentification
- `POST /api/auth/login` - Connexion utilisateur
- `POST /api/auth/register` - Inscription utilisateur  
- `POST /api/auth/refresh` - Rafraîchissement token
- `GET /api/auth/me` - Profil utilisateur

#### Véhicules
- `GET /api/vehicles/` - Liste des véhicules
- `POST /api/vehicles/` - Créer un véhicule

#### Réservations
- `GET /api/bookings/` - Liste des réservations
- `POST /api/bookings/` - Créer une réservation

#### Administration
- `GET /api/admin/stats` - Statistiques (auth requise)

## 🧪 Tests

```bash
# Exécuter tous les tests
pytest

# Tests avec couverture
pytest --cov=app

# Tests spécifiques
pytest tests/test_auth.py -v
```

## 🚀 Déploiement

### Variables d'environnement de production

```bash
# Sécurité
DEBUG=false
ENVIRONMENT=production
JWT_SECRET_KEY=your_production_secret_key_32_chars_min

# Base de données
DATABASE_URL=postgresql://user:password@localhost:5432/vtc_prod

# Logging
LOG_LEVEL=INFO
```

### Commande de déploiement
```bash
./scripts/deploy.sh
```

## 🐛 Résolution de Problèmes

### Erreurs courantes

1. **AttributeError: module 'logging' has no attribute 'handlers'**
   - ✅ **Résolu** : Import explicite ajouté dans `production_logger.py`

2. **ValidationInfo not found (Pydantic V2)**
   - ✅ **Résolu** : Migration vers `ValidationError` dans `secure_config.py`

3. **Problèmes de validation Pydantic**
   - ✅ **Résolu** : Compatibilité complète V2 dans `business_logic_validator.py`

### Logs et diagnostic

```bash
# Logs de l'application
tail -f /var/log/vtc/vtc_app.log

# Logs Docker
docker-compose logs -f vtc-backend

# État des services
docker-compose ps
```

## 🤝 Contribution

1. Fork le projet
2. Créer une branche feature (`git checkout -b feature/AmazingFeature`)
3. Commit les changements (`git commit -m 'Add AmazingFeature'`)
4. Push la branche (`git push origin feature/AmazingFeature`)
5. Ouvrir une Pull Request

## 📝 Licence

Ce projet est sous licence MIT. Voir le fichier `LICENSE` pour plus de détails.

## 📞 Support

Pour toute question ou problème :
- Créer une issue sur GitHub
- Contact : amine.seddiki1989@example.com

---

**Status du projet** : ✅ Code complet restauré et testé avec tous les fixes de débogage appliqués.
