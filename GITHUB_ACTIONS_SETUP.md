# 🚀 Configuration GitHub Actions - Application VTC

## 📋 Étapes de Configuration

### 1️⃣ Workflow GitHub Actions ✅ CRÉÉ

Le fichier `.github/workflows/ci.yml` a été créé avec :

- **Tests automatiques** sur chaque push/PR vers `main`
- **Services** : PostgreSQL + Redis
- **Couverture de code** avec pytest-cov
- **Tests de sécurité** avec Bandit
- **Tests de charge nocturnes** avec Locust (2h du matin)

### 2️⃣ Configuration Codecov (Recommandé)

**Étapes à suivre :**

1. **Créer un compte Codecov :**
   - Aller sur https://codecov.io
   - Se connecter avec votre compte GitHub
   - Autoriser l'accès à vos repositories

2. **Ajouter votre repository :**
   - Sélectionner votre repo VTC
   - Copier le token Codecov généré

3. **Configurer le secret GitHub :**
   ```
   Repository → Settings → Secrets and variables → Actions
   → New repository secret
   
   Name: CODECOV_TOKEN
   Value: [votre token Codecov]
   ```

### 3️⃣ Tests de Sécurité ✅ CONFIGURÉ

**Bandit** est configuré pour scanner automatiquement :
- Vulnérabilités de sécurité
- Pratiques dangereuses
- Failles potentielles

### 4️⃣ Tests de Charge ✅ CONFIGURÉ

**Locust** configuré pour :
- **Exécution nocturne** (2h du matin)
- **20 utilisateurs simultanés**
- **5 utilisateurs/seconde**
- **Durée : 1 minute**

## 📁 Fichiers Créés

```
.github/
└── workflows/
    └── ci.yml                    # Workflow principal

tests/
└── load/
    └── locustfile.py            # Tests de charge Locust

requirements-test.txt            # Dépendances de test
GITHUB_ACTIONS_SETUP.md         # Ce guide
```

## 🧪 Tests Inclus

### Tests Automatiques (chaque push/PR)
- ✅ Tests unitaires avec pytest
- ✅ Couverture de code (XML + terminal)
- ✅ Analyse de sécurité avec Bandit
- ✅ Upload vers Codecov

### Tests de Charge (nocturnes)
- 🌙 Exécution à 2h du matin
- 📊 Simulation de 20 utilisateurs
- 🎯 Tests des endpoints critiques :
  - `/health`
  - `/api/v1/monitoring/dashboard`
  - `/api/v1/fiscal/calculate`
  - `/api/v1/auth/register`

## ⚙️ Configuration des Services

### PostgreSQL
```yaml
POSTGRES_USER: trafic
POSTGRES_PASSWORD: trafic
POSTGRES_DB: trafic
Port: 5432
```

### Redis
```yaml
Port: 6379
Health check: redis-cli ping
```

## 🔧 Commandes Locales

### Exécuter les tests localement
```bash
# Tests unitaires
pytest --cov=app --cov-report=xml --cov-report=term-missing

# Tests de sécurité
bandit -r app

# Tests de charge (avec serveur local)
locust -f tests/load/locustfile.py --headless -u 20 -r 5 -t 1m --host http://localhost:8000
```

## 📊 Résultats Attendus

### ✅ Succès
- **Badge vert** sur GitHub
- **Rapport de couverture** sur Codecov
- **Aucune vulnérabilité** détectée par Bandit
- **Tests de charge** réussis (nocturnes)

### ❌ Échec
- **Badge rouge** sur GitHub
- **Détails des erreurs** dans les logs
- **Blocage des PR** si tests échouent

## 🚀 Activation

1. **Pusher le code** vers votre repository GitHub
2. **Vérifier** que le workflow se lance automatiquement
3. **Configurer Codecov** (optionnel mais recommandé)
4. **Surveiller** les résultats dans l'onglet "Actions"

## 📈 Métriques Surveillées

- **Couverture de code** : minimum recommandé 80%
- **Performance** : temps de réponse des endpoints
- **Sécurité** : 0 vulnérabilité critique
- **Charge** : capacité à gérer 20 utilisateurs simultanés

---

**🎉 Votre pipeline CI/CD est maintenant configuré et prêt à assurer la qualité de votre application VTC !**

