# 🚗 VTC Application - Configuration de Production

Application VTC complète avec backend Flask, frontend Next.js, et infrastructure Docker.

## 📋 Architecture

```
vtc-app/
├── docker-compose.yml      # Orchestration des services
├── nginx/                  # Configuration proxy reverse
│   ├── nginx.conf         # Configuration principale
│   └── sites-enabled/     # Sites virtuels
├── backend/               # API Flask
│   ├── Dockerfile
│   └── requirements.txt
├── frontend/              # Application Next.js
│   └── Dockerfile
├── database/              # Schema PostgreSQL
│   └── init.sql
├── scripts/               # Scripts de déploiement
│   └── deploy.sh
└── ssl/                   # Certificats SSL
```

## 🚀 Déploiement Rapide

### Prérequis
- Docker & Docker Compose installés
- Ports 80, 443, 3000, 5000 disponibles
- Certificats SSL (optionnel pour dev)

### 1. Configuration
```bash
# Cloner le projet
git clone https://github.com/amineseddiki1989/vtc.git
cd vtc-app

# Configuration environnement
cp .env.example .env
nano .env  # Modifier les variables si nécessaire
```

### 2. Déploiement automatique
```bash
chmod +x scripts/deploy.sh
./scripts/deploy.sh
```

### 3. Déploiement manuel
```bash
# Construction et démarrage
docker-compose up -d --build

# Vérification des services
docker-compose ps
docker-compose logs
```

## 🔧 Services

| Service | Port | Description |
|---------|------|-------------|
| **Frontend** | 3000 | Interface utilisateur Next.js |
| **Backend** | 5000 | API REST Flask |
| **Nginx** | 80/443 | Proxy reverse et SSL |
| **PostgreSQL** | 5432 | Base de données |
| **Redis** | 6379 | Cache et sessions |

## 📊 Accès

- **Application:** https://vtc-app.com (production) ou http://localhost:3000 (dev)
- **API:** https://api.vtc-app.com/api (production) ou http://localhost:5000/api (dev)
- **Admin:** admin@vtc-app.com / AdminVTC2024!

## 🛡️ Sécurité

### SSL/TLS
- Certificats dans `ssl/`
- Redirection automatique HTTP → HTTPS
- Headers de sécurité configurés

### Authentification
- JWT avec expiration
- Hashage bcrypt des mots de passe
- Protection CSRF

### Rate Limiting
- API: 10 req/s par IP
- Auth: 5 req/m par IP

## 📋 Commandes Utiles

### Gestion des conteneurs
```bash
# Démarrer tous les services
docker-compose up -d

# Arrêter tous les services
docker-compose down

# Reconstruire et redémarrer
docker-compose up -d --build

# Voir les logs
docker-compose logs -f [service]

# Accéder à un conteneur
docker-compose exec [service] bash
```

### Base de données
```bash
# Accéder à PostgreSQL
docker-compose exec postgres psql -U vtc_user -d vtc_database

# Sauvegarde
docker-compose exec postgres pg_dump -U vtc_user vtc_database > backup.sql

# Restauration
docker-compose exec -T postgres psql -U vtc_user -d vtc_database < backup.sql
```

### Monitoring
```bash
# Statut des services
docker-compose ps

# Utilisation ressources
docker stats

# Health checks
curl http://localhost:3000/health
curl http://localhost:5000/health
```

## 🔄 Mise à jour

```bash
# Arrêter les services
docker-compose down

# Mettre à jour le code
git pull origin main

# Reconstruire et redémarrer
docker-compose up -d --build
```

## 🐛 Dépannage

### Problèmes courants

1. **Port déjà utilisé**
   ```bash
   sudo netstat -tlnp | grep :3000
   sudo kill -9 [PID]
   ```

2. **Problème de permissions**
   ```bash
   sudo chown -R $USER:$USER .
   chmod +x scripts/deploy.sh
   ```

3. **Base de données non accessible**
   ```bash
   docker-compose logs postgres
   docker-compose restart postgres
   ```

4. **SSL/HTTPS**
   - Vérifier les certificats dans `ssl/`
   - Pour le dev: utiliser HTTP sur localhost

### Logs détaillés
```bash
# Tous les services
docker-compose logs -f

# Service spécifique
docker-compose logs -f backend
docker-compose logs -f frontend
docker-compose logs -f nginx
```

## 📞 Support

- **Email:** admin@vtc-app.com
- **GitHub:** https://github.com/amineseddiki1989/vtc
- **Documentation API:** http://localhost:5000/docs (après démarrage)

## 📄 License

MIT License - Voir LICENSE pour plus de détails.
