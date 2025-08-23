# 🚀 GUIDE DE DÉMARRAGE RAPIDE - APPLICATION VTC 60%

## ⚡ DÉMARRAGE EN 3 MINUTES

### 1. Extraction et Installation
```bash
# Extraire l'archive
tar -xzf uber_api_60_percent_functional.tar.gz
cd uber_api_fonctionnel

# Installer les dépendances
pip install -r requirements.txt
```

### 2. Démarrage de l'Application
```bash
# Démarrage automatique
python start_app.py

# OU démarrage manuel
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

### 3. Vérification du Fonctionnement
```bash
# Test de santé
curl http://localhost:8000/health
# ✅ Doit retourner: {"status":"healthy","version":"2.0.0"}

# Accès à la documentation
# Ouvrir dans le navigateur: http://localhost:8000/docs
```

---

## 🧪 TESTS RAPIDES

### ✅ Ce qui fonctionne
```bash
# Endpoint de santé
curl http://localhost:8000/health

# Documentation API
curl http://localhost:8000/docs

# Page d'accueil
curl http://localhost:8000/
```

### ❌ Ce qui ne fonctionne pas
```bash
# Création d'utilisateur (erreur 500)
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{"email":"test@test.com","password":"password123","role":"passenger"}'

# Endpoints protégés (erreur 403)
curl http://localhost:8000/api/v1/trips
```

---

## 📊 ACCÈS AUX MÉTRIQUES

Les métriques sont collectées automatiquement mais les endpoints sont protégés. Vous pouvez voir les données dans la base de données :

```bash
# Accéder à la base de données SQLite
sqlite3 uber_api.db

# Voir les métriques collectées
.tables
SELECT * FROM metrics LIMIT 10;
SELECT * FROM system_health LIMIT 5;
```

---

## 🔧 CONFIGURATION

### Variables d'Environnement (.env)
```env
# Base de données
DATABASE_URL=sqlite:///./uber_api.db

# JWT (clés générées automatiquement)
SECRET_KEY=<clé_générée_automatiquement>
JWT_SECRET_KEY=<clé_générée_automatiquement>

# Configuration
ENVIRONMENT=development
DEBUG=true
```

### Ports et URLs
- **Application** : http://localhost:8000
- **Documentation** : http://localhost:8000/docs
- **Redoc** : http://localhost:8000/redoc
- **Santé** : http://localhost:8000/health

---

## 🐛 PROBLÈMES CONNUS

### Authentification Cassée
- **Symptôme** : Erreur 500 sur `/api/v1/auth/register`
- **Cause** : Relations SQLAlchemy mal configurées
- **Impact** : Impossible de créer des utilisateurs

### Endpoints Protégés Inaccessibles
- **Symptôme** : Erreur 403 sur tous les endpoints métier
- **Cause** : Authentification non fonctionnelle
- **Impact** : API métier inutilisable

---

## 📁 STRUCTURE DES FICHIERS

```
uber_api_fonctionnel/
├── 📄 README_APPLICATION_60_PERCENT.md  # Rapport détaillé
├── 📄 QUICK_START_GUIDE.md              # Ce guide
├── 🚀 start_app.py                      # Script de démarrage
├── ⚙️ requirements.txt                  # Dépendances
├── 🔧 .env                              # Configuration
├── 📁 app/                              # Code source
│   ├── main.py                          # Point d'entrée
│   ├── models/                          # Modèles de données
│   ├── api/                             # Endpoints API
│   ├── services/                        # Services métier
│   └── core/                            # Infrastructure
└── 🗄️ uber_api.db                       # Base de données SQLite
```

---

## 🆘 SUPPORT ET DÉPANNAGE

### Problèmes Courants

**1. Erreur "Module not found"**
```bash
# Solution : Installer les dépendances
pip install -r requirements.txt
```

**2. Erreur "Port already in use"**
```bash
# Solution : Changer le port
uvicorn app.main:app --port 8001
```

**3. Base de données corrompue**
```bash
# Solution : Supprimer et recréer
rm uber_api.db
python start_app.py
```

### Logs de Débogage
```bash
# Voir les logs en temps réel
tail -f app.log

# Logs détaillés
python start_app.py --log-level debug
```

---

## 📈 MÉTRIQUES ET MONITORING

### Métriques Collectées Automatiquement
- **HTTP** : Requêtes, temps de réponse, codes de statut
- **Système** : CPU, mémoire, connexions
- **Erreurs** : Exceptions, timeouts, échecs

### Accès aux Données
```sql
-- Métriques HTTP récentes
SELECT * FROM metrics WHERE metric_type = 'http_request' 
ORDER BY timestamp DESC LIMIT 10;

-- Santé du système
SELECT * FROM system_health ORDER BY timestamp DESC LIMIT 5;

-- Alertes générées
SELECT * FROM metric_alerts WHERE status = 'active';
```

---

## 🎯 UTILISATION RECOMMANDÉE

### ✅ Bon pour :
- **Tests d'infrastructure** et de performance
- **Développement** de nouvelles fonctionnalités
- **Validation** de l'architecture
- **Tests** de monitoring et métriques

### ❌ Pas bon pour :
- **Production** (authentification cassée)
- **Tests utilisateur** (pas de création de compte)
- **Démonstrations** client (fonctionnalités limitées)

---

## 🔄 PROCHAINES ÉTAPES

Pour rendre l'application 100% fonctionnelle :

1. **Corriger les relations SQLAlchemy** dans les modèles
2. **Réparer l'authentification JWT**
3. **Tester la création d'utilisateurs**
4. **Valider tous les endpoints métier**

**Temps estimé :** 4-6 heures de développement

---

*Guide créé le 5 juillet 2025*
*Version de l'application : 2.0.0 (60% fonctionnelle)*

