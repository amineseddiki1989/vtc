from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse
import os

router = APIRouter()

INTERFACES_DIR = "static/images/interfaces"

# Liste des interfaces disponibles
AVAILABLE_INTERFACES = {
    "connexion": "01_ecran_connexion.png",
    "dashboard": "02_dashboard_elabore.png", 
    "profil": "03_profil_ultra_sophistique.png",
    "historique": "04_historique_ultra_sophistique.png",
    "securite": "05_securite_corrigee_ultra_sophistique.png",
    "inscription": "06_inscription_ultra_sophistique.png",
    "admin_dashboard": "07_admin_dashboard_ultra_sophistique.png",
    "gestion_utilisateurs": "08_gestion_utilisateurs_ultra_sophistique.png",
    "parametres": "09_parametres_ULTRA_sophistique_retrouve.png",
    "notifications": "10_notifications_SOPHISTICATION_ABSOLUE.png",
    "portefeuille": "11_portefeuille_FOND_CORRECT.png"
}

@router.get("/interfaces")
async def get_available_interfaces():
    """Retourne la liste des interfaces disponibles"""
    return {
        "interfaces": list(AVAILABLE_INTERFACES.keys()),
        "total": len(AVAILABLE_INTERFACES),
        "description": "Interfaces ultra-sophistiquées pour l'application mobile"
    }

@router.get("/interfaces/{interface_name}")
async def get_interface(interface_name: str):
    """Retourne une interface spécifique"""
    if interface_name not in AVAILABLE_INTERFACES:
        raise HTTPException(
            status_code=404, 
            detail=f"Interface '{interface_name}' non trouvée. Interfaces disponibles: {list(AVAILABLE_INTERFACES.keys())}"
        )
    
    file_path = os.path.join(INTERFACES_DIR, AVAILABLE_INTERFACES[interface_name])
    
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail="Fichier d'interface non trouvé")
    
    return FileResponse(
        file_path,
        media_type="image/png",
        filename=AVAILABLE_INTERFACES[interface_name]
    )

@router.get("/interfaces/preview/all")
async def get_all_interfaces_info():
    """Retourne les informations de toutes les interfaces"""
    interfaces_info = []
    
    for name, filename in AVAILABLE_INTERFACES.items():
        file_path = os.path.join(INTERFACES_DIR, filename)
        if os.path.exists(file_path):
            file_size = os.path.getsize(file_path)
            interfaces_info.append({
                "name": name,
                "filename": filename,
                "url": f"/api/v1/interfaces/{name}",
                "size_bytes": file_size,
                "size_mb": round(file_size / (1024 * 1024), 2)
            })
    
    return {
        "interfaces": interfaces_info,
        "total_count": len(interfaces_info),
        "total_size_mb": round(sum(info["size_mb"] for info in interfaces_info), 2)
    }

