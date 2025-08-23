# 🚀 GUIDE DE DÉPLOIEMENT - UBER API PHASE 3

## 📋 PRÉREQUIS SYSTÈME

### **SERVEUR DE PRODUCTION**
- **OS :** Ubuntu 22.04 LTS ou CentOS 8+
- **CPU :** 4 cores minimum (8 cores recommandé)
- **RAM :** 8GB minimum (16GB recommandé)
- **Stockage :** 100GB SSD minimum
- **Réseau :** 1Gbps minimum

### **LOGICIELS REQUIS**
- Python 3.11+
- PostgreSQL 15+
- Redis 7+
- Nginx 1.20+
- Docker 24+ (optionnel)
- Git 2.30+

---

## 🔧 INSTALLATION ÉTAPE PAR ÉTAPE

### **1. PRÉPARATION DU SERVEUR**

```bash
# Mise à jour du système
sudo apt update && sudo apt upgrade -y

# Installation des dépendances système
sudo apt install -y python3.11 python3.11-venv python3.11-dev \
    postgresql postgresql-contrib redis-server nginx git \
    build-essential libpq-dev curl

# Configuration du firewall
sudo ufw allow 22    # SSH
sudo ufw allow 80    # HTTP
sudo ufw allow 443   # HTTPS
sudo ufw enable
```

### **2. CONFIGURATION POSTGRESQL**

```bash
# Démarrer PostgreSQL
sudo systemctl start postgresql
sudo systemctl enable postgresql

# Créer la base de données
sudo -u postgres psql << EOF
CREATE DATABASE uber_api_prod;
CREATE USER uber_api WITH PASSWORD 'votre_mot_de_passe_securise';
GRANT ALL PRIVILEGES ON DATABASE uber_api_prod TO uber_api;
ALTER USER uber_api CREATEDB;
\q
EOF

# Configuration PostgreSQL pour production
sudo nano /etc/postgresql/15/main/postgresql.conf
# Modifier :
# max_connections = 200
# shared_buffers = 256MB
# effective_cache_size = 1GB
# work_mem = 4MB

sudo systemctl restart postgresql
```

### **3. CONFIGURATION REDIS**

```bash
# Configuration Redis
sudo nano /etc/redis/redis.conf
# Modifier :
# maxmemory 512mb
# maxmemory-policy allkeys-lru
# save 900 1
# save 300 10

sudo systemctl restart redis-server
sudo systemctl enable redis-server
```

### **4. DÉPLOIEMENT DE L'APPLICATION**

```bash
# Créer l'utilisateur de déploiement
sudo adduser --system --group --home /opt/uber_api uber_api

# Cloner l'application
sudo -u uber_api git clone <repository> /opt/uber_api/app
cd /opt/uber_api/app

# Créer l'environnement virtuel
sudo -u uber_api python3.11 -m venv /opt/uber_api/venv

# Activer l'environnement
sudo -u uber_api /opt/uber_api/venv/bin/pip install --upgrade pip

# Installer les dépendances
sudo -u uber_api /opt/uber_api/venv/bin/pip install -r requirements-production.txt
```

### **5. CONFIGURATION ENVIRONNEMENT**

```bash
# Créer le fichier de configuration
sudo -u uber_api nano /opt/uber_api/app/.env
```

```env
# Configuration Production
ENVIRONMENT=production
DEBUG=false

# Base de données
DATABASE_URL=postgresql://uber_api:votre_mot_de_passe@localhost/uber_api_prod
DATABASE_POOL_SIZE=20
DATABASE_MAX_OVERFLOW=30

# Redis
REDIS_URL=redis://localhost:6379/0
REDIS_CACHE_TTL=3600

# Sécurité
SECRET_KEY=votre_cle_secrete_ultra_securisee_64_caracteres_minimum
JWT_SECRET_KEY=votre_cle_jwt_secrete_64_caracteres_minimum
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_MINUTES=30
JWT_REFRESH_TOKEN_EXPIRE_DAYS=7

# API Keys externes
GOOGLE_MAPS_API_KEY=votre_cle_google_maps
STRIPE_SECRET_KEY=votre_cle_stripe_secrete
STRIPE_PUBLISHABLE_KEY=votre_cle_stripe_publique

# Notifications
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=votre_email@gmail.com
SMTP_PASSWORD=votre_mot_de_passe_app
SMS_API_KEY=votre_cle_sms

# Monitoring
SENTRY_DSN=votre_dsn_sentry
LOG_LEVEL=INFO

# Serveur
HOST=0.0.0.0
PORT=8000
WORKERS=4
```

### **6. MIGRATIONS DE BASE DE DONNÉES**

```bash
# Exécuter les migrations
cd /opt/uber_api/app
sudo -u uber_api /opt/uber_api/venv/bin/alembic upgrade head

# Créer un utilisateur admin
sudo -u uber_api /opt/uber_api/venv/bin/python << EOF
import asyncio
from app.services.user_service_advanced import UserServiceAdvanced, UserRegistrationRequest
from app.models.user_advanced import UserRole
from app.core.database.postgresql import get_async_session

async def create_admin():
    async with get_async_session() as db:
        service = UserServiceAdvanced()
        admin_request = UserRegistrationRequest(
            email="admin@votre-domaine.com",
            phone="+213555000000",
            password="AdminPassword123!",
            first_name="Admin",
            last_name="System",
            role=UserRole.ADMIN
        )
        user, token = await service.register_user(admin_request, db)
        print(f"Admin créé: {user.email}")

asyncio.run(create_admin())
EOF
```

---

## 🔧 CONFIGURATION NGINX

### **1. CONFIGURATION NGINX**

```bash
# Créer la configuration Nginx
sudo nano /etc/nginx/sites-available/uber_api
```

```nginx
server {
    listen 80;
    server_name votre-domaine.com www.votre-domaine.com;
    
    # Redirection HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name votre-domaine.com www.votre-domaine.com;
    
    # Certificats SSL
    ssl_certificate /etc/letsencrypt/live/votre-domaine.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/votre-domaine.com/privkey.pem;
    
    # Configuration SSL
    ssl_protocols TLSv1.2 TLSv1.3;
    ssl_ciphers ECDHE-RSA-AES256-GCM-SHA512:DHE-RSA-AES256-GCM-SHA512;
    ssl_prefer_server_ciphers off;
    ssl_session_cache shared:SSL:10m;
    
    # Headers de sécurité
    add_header Strict-Transport-Security "max-age=63072000" always;
    add_header X-Frame-Options DENY always;
    add_header X-Content-Type-Options nosniff always;
    
    # Taille max upload
    client_max_body_size 10M;
    
    # Proxy vers l'application
    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
        
        # Timeouts
        proxy_connect_timeout 60s;
        proxy_send_timeout 60s;
        proxy_read_timeout 60s;
    }
    
    # Fichiers statiques
    location /static/ {
        alias /opt/uber_api/app/static/;
        expires 1y;
        add_header Cache-Control "public, immutable";
    }
    
    # Health check
    location /health {
        access_log off;
        proxy_pass http://127.0.0.1:8000/health;
    }
}
```

```bash
# Activer la configuration
sudo ln -s /etc/nginx/sites-available/uber_api /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### **2. CERTIFICAT SSL (Let's Encrypt)**

```bash
# Installer Certbot
sudo apt install certbot python3-certbot-nginx

# Obtenir le certificat
sudo certbot --nginx -d votre-domaine.com -d www.votre-domaine.com

# Renouvellement automatique
sudo crontab -e
# Ajouter :
0 12 * * * /usr/bin/certbot renew --quiet
```

---

## 🔄 SERVICE SYSTEMD

### **1. CRÉER LE SERVICE**

```bash
sudo nano /etc/systemd/system/uber_api.service
```

```ini
[Unit]
Description=Uber API Production Server
After=network.target postgresql.service redis.service
Requires=postgresql.service redis.service

[Service]
Type=exec
User=uber_api
Group=uber_api
WorkingDirectory=/opt/uber_api/app
Environment=PATH=/opt/uber_api/venv/bin
ExecStart=/opt/uber_api/venv/bin/gunicorn app.main_production:app \
    --workers 4 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 127.0.0.1:8000 \
    --access-logfile /var/log/uber_api/access.log \
    --error-logfile /var/log/uber_api/error.log \
    --log-level info \
    --timeout 60 \
    --keep-alive 5 \
    --max-requests 1000 \
    --max-requests-jitter 100

ExecReload=/bin/kill -s HUP $MAINPID
KillMode=mixed
TimeoutStopSec=5
PrivateTmp=true
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

### **2. ACTIVER LE SERVICE**

```bash
# Créer les dossiers de logs
sudo mkdir -p /var/log/uber_api
sudo chown uber_api:uber_api /var/log/uber_api

# Activer et démarrer le service
sudo systemctl daemon-reload
sudo systemctl enable uber_api
sudo systemctl start uber_api

# Vérifier le statut
sudo systemctl status uber_api
```

---

## 📊 MONITORING ET LOGS

### **1. CONFIGURATION LOGROTATE**

```bash
sudo nano /etc/logrotate.d/uber_api
```

```
/var/log/uber_api/*.log {
    daily
    missingok
    rotate 52
    compress
    delaycompress
    notifempty
    create 644 uber_api uber_api
    postrotate
        systemctl reload uber_api
    endscript
}
```

### **2. MONITORING AVEC PROMETHEUS**

```bash
# Installer Prometheus
wget https://github.com/prometheus/prometheus/releases/download/v2.40.0/prometheus-2.40.0.linux-amd64.tar.gz
tar xvfz prometheus-*.tar.gz
sudo mv prometheus-*/prometheus /usr/local/bin/
sudo mv prometheus-*/promtool /usr/local/bin/

# Configuration Prometheus
sudo mkdir /etc/prometheus
sudo nano /etc/prometheus/prometheus.yml
```

```yaml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'uber_api'
    static_configs:
      - targets: ['localhost:8000']
    metrics_path: '/metrics'
    scrape_interval: 5s
```

---

## 🔒 SÉCURITÉ PRODUCTION

### **1. CONFIGURATION FAIL2BAN**

```bash
# Installer Fail2ban
sudo apt install fail2ban

# Configuration
sudo nano /etc/fail2ban/jail.local
```

```ini
[DEFAULT]
bantime = 3600
findtime = 600
maxretry = 5

[sshd]
enabled = true

[nginx-http-auth]
enabled = true

[nginx-limit-req]
enabled = true
filter = nginx-limit-req
action = iptables-multiport[name=ReqLimit, port="http,https", protocol=tcp]
logpath = /var/log/nginx/error.log
findtime = 600
bantime = 7200
maxretry = 10
```

### **2. CONFIGURATION IPTABLES**

```bash
# Règles de base
sudo iptables -A INPUT -i lo -j ACCEPT
sudo iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 22 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 80 -j ACCEPT
sudo iptables -A INPUT -p tcp --dport 443 -j ACCEPT
sudo iptables -A INPUT -j DROP

# Sauvegarder les règles
sudo iptables-save > /etc/iptables/rules.v4
```

---

## 🔄 SAUVEGARDE ET RESTAURATION

### **1. SCRIPT DE SAUVEGARDE**

```bash
sudo nano /opt/uber_api/backup.sh
```

```bash
#!/bin/bash
BACKUP_DIR="/opt/backups/uber_api"
DATE=$(date +%Y%m%d_%H%M%S)

# Créer le dossier de sauvegarde
mkdir -p $BACKUP_DIR

# Sauvegarde PostgreSQL
pg_dump -h localhost -U uber_api uber_api_prod | gzip > $BACKUP_DIR/db_$DATE.sql.gz

# Sauvegarde Redis
redis-cli --rdb $BACKUP_DIR/redis_$DATE.rdb

# Sauvegarde des fichiers uploadés
tar -czf $BACKUP_DIR/uploads_$DATE.tar.gz /opt/uber_api/app/uploads/

# Nettoyage (garder 30 jours)
find $BACKUP_DIR -name "*.gz" -mtime +30 -delete
find $BACKUP_DIR -name "*.rdb" -mtime +30 -delete
```

```bash
# Rendre exécutable
sudo chmod +x /opt/uber_api/backup.sh

# Programmer la sauvegarde
sudo crontab -e
# Ajouter :
0 2 * * * /opt/uber_api/backup.sh
```

---

## 🚀 DÉPLOIEMENT AVEC DOCKER

### **1. DOCKERFILE**

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Dépendances système
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Dépendances Python
COPY requirements-production.txt .
RUN pip install --no-cache-dir -r requirements-production.txt

# Code application
COPY . .

# Utilisateur non-root
RUN useradd --create-home --shell /bin/bash app
RUN chown -R app:app /app
USER app

EXPOSE 8000

CMD ["gunicorn", "app.main_production:app", "--workers", "4", "--worker-class", "uvicorn.workers.UvicornWorker", "--bind", "0.0.0.0:8000"]
```

### **2. DOCKER-COMPOSE**

```yaml
version: '3.8'

services:
  app:
    build: .
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://uber_api:password@db:5432/uber_api_prod
      - REDIS_URL=redis://redis:6379/0
    depends_on:
      - db
      - redis
    volumes:
      - ./uploads:/app/uploads
    restart: unless-stopped

  db:
    image: postgres:15
    environment:
      - POSTGRES_DB=uber_api_prod
      - POSTGRES_USER=uber_api
      - POSTGRES_PASSWORD=password
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: unless-stopped

  nginx:
    image: nginx:alpine
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./nginx.conf:/etc/nginx/nginx.conf
      - ./ssl:/etc/ssl
    depends_on:
      - app
    restart: unless-stopped

volumes:
  postgres_data:
  redis_data:
```

---

## ✅ VÉRIFICATION POST-DÉPLOIEMENT

### **1. TESTS DE SANTÉ**

```bash
# Test de l'API
curl -f http://localhost:8000/health

# Test de la base de données
curl -f http://localhost:8000/api/v1/health/db

# Test Redis
curl -f http://localhost:8000/api/v1/health/redis

# Test complet
curl -f http://localhost:8000/api/v1/health/full
```

### **2. TESTS DE CHARGE**

```bash
# Installer Apache Bench
sudo apt install apache2-utils

# Test de charge basique
ab -n 1000 -c 10 http://localhost:8000/health

# Test avec authentification
ab -n 100 -c 5 -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8000/api/v1/trips/my-trips
```

---

## 🎯 OPTIMISATIONS PRODUCTION

### **1. OPTIMISATIONS POSTGRESQL**

```sql
-- Index pour les requêtes fréquentes
CREATE INDEX CONCURRENTLY idx_trips_status ON trips(status);
CREATE INDEX CONCURRENTLY idx_trips_passenger_id ON trips(passenger_id);
CREATE INDEX CONCURRENTLY idx_trips_driver_id ON trips(driver_id);
CREATE INDEX CONCURRENTLY idx_trips_created_at ON trips(created_at);
CREATE INDEX CONCURRENTLY idx_users_email ON users(email);
CREATE INDEX CONCURRENTLY idx_users_phone ON users(phone);

-- Statistiques
ANALYZE;
```

### **2. OPTIMISATIONS REDIS**

```bash
# Configuration Redis optimisée
echo "maxmemory 1gb" >> /etc/redis/redis.conf
echo "maxmemory-policy allkeys-lru" >> /etc/redis/redis.conf
echo "tcp-keepalive 60" >> /etc/redis/redis.conf
```

---

## 📞 MAINTENANCE ET SUPPORT

### **1. COMMANDES UTILES**

```bash
# Redémarrer l'application
sudo systemctl restart uber_api

# Voir les logs en temps réel
sudo journalctl -u uber_api -f

# Vérifier l'utilisation des ressources
htop
sudo iotop
sudo nethogs

# Vérifier les connexions
sudo netstat -tulpn | grep :8000
```

### **2. DÉPANNAGE COURANT**

```bash
# Problème de base de données
sudo systemctl status postgresql
sudo -u postgres psql -c "SELECT version();"

# Problème Redis
sudo systemctl status redis-server
redis-cli ping

# Problème Nginx
sudo nginx -t
sudo systemctl status nginx
```

---

**🚀 Déploiement terminé !**  
*Votre application Uber API est maintenant en production*

