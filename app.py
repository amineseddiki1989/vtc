"""
Wrapper Flask pour l'application FastAPI - Déploiement
"""

from flask import Flask, jsonify, send_file, request
import requests
import subprocess
import threading
import time
import os

# Créer l'application Flask
flask_app = Flask(__name__)

# Configuration
FASTAPI_URL = "http://localhost:8000"
FASTAPI_PROCESS = None

def start_fastapi():
    """Démarre le serveur FastAPI en arrière-plan"""
    global FASTAPI_PROCESS
    try:
        FASTAPI_PROCESS = subprocess.Popen([
            "python3.11", "-m", "app.main"
        ], cwd="/home/ubuntu/uber_api_fixed")
        time.sleep(3)  # Attendre le démarrage
    except Exception as e:
        print(f"Erreur démarrage FastAPI: {e}")

# Démarrer FastAPI au lancement
threading.Thread(target=start_fastapi, daemon=True).start()

@flask_app.route('/')
def home():
    """Page d'accueil avec informations sur l'API"""
    return jsonify({
        "message": "Application Mobile Uber API - Déployée avec succès!",
        "version": "1.0.0",
        "status": "running",
        "interfaces_disponibles": 11,
        "endpoints": {
            "api_base": f"{request.host_url}api/",
            "interfaces": f"{request.host_url}api/v1/interfaces",
            "auth": f"{request.host_url}api/v1/auth/",
            "documentation": f"{request.host_url}docs"
        },
        "description": "API complète avec interfaces ultra-sophistiquées intégrées"
    })

@flask_app.route('/api/<path:path>', methods=['GET', 'POST', 'PUT', 'DELETE', 'PATCH'])
def proxy_to_fastapi(path):
    """Proxy vers l'API FastAPI"""
    try:
        url = f"{FASTAPI_URL}/{path}"
        
        # Transférer la requête vers FastAPI
        if request.method == 'GET':
            resp = requests.get(url, params=request.args)
        elif request.method == 'POST':
            resp = requests.post(url, json=request.get_json(), params=request.args)
        elif request.method == 'PUT':
            resp = requests.put(url, json=request.get_json(), params=request.args)
        elif request.method == 'DELETE':
            resp = requests.delete(url, params=request.args)
        elif request.method == 'PATCH':
            resp = requests.patch(url, json=request.get_json(), params=request.args)
        
        # Retourner la réponse
        if resp.headers.get('content-type', '').startswith('image/'):
            return send_file(resp.content, mimetype=resp.headers['content-type'])
        else:
            return resp.json(), resp.status_code
            
    except Exception as e:
        return jsonify({"error": f"Erreur proxy: {str(e)}"}), 500

@flask_app.route('/docs')
def docs():
    """Redirection vers la documentation FastAPI"""
    try:
        resp = requests.get(f"{FASTAPI_URL}/docs")
        return resp.text, resp.status_code, {'Content-Type': 'text/html'}
    except:
        return jsonify({"error": "Documentation non disponible"}), 503

@flask_app.route('/health')
def health():
    """Vérification de santé de l'application"""
    try:
        # Tester FastAPI
        resp = requests.get(f"{FASTAPI_URL}/health", timeout=5)
        fastapi_status = "healthy" if resp.status_code == 200 else "unhealthy"
    except:
        fastapi_status = "unreachable"
    
    return jsonify({
        "flask_app": "healthy",
        "fastapi_backend": fastapi_status,
        "interfaces_integrated": True,
        "total_interfaces": 11
    })

if __name__ == '__main__':
    flask_app.run(host='0.0.0.0', port=5000, debug=False)

