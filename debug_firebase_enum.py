#!/usr/bin/env python3
"""
Script de debug spécialisé pour tracer l'erreur enum Firebase.
"""

import sys
import traceback
import logging
sys.path.append('.')

# Configuration du logging pour debug
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

def debug_enum_error():
    """Debug approfondi de l'erreur enum."""
    
    print("🔍 DEBUG APPROFONDI - ERREUR ENUM FIREBASE")
    print("=" * 60)
    
    try:
        from app.services.firebase_notification_service import FirebaseNotificationService, NotificationType, NotificationPriority
        from app.core.database.session import get_db
        from app.models.user import User
        
        # Utiliser un utilisateur existant
        db = next(get_db())
        user = db.query(User).first()
        
        print(f"👤 Utilisateur trouvé:")
        print(f"   ID: {user.id}")
        print(f"   Email: {user.email}")
        print(f"   Role: {user.role} (type: {type(user.role)})")
        print(f"   Role.value: {user.role.value if hasattr(user.role, 'value') else 'NO VALUE ATTR'}")
        
        # Tester les enums
        notification_type = NotificationType.DRIVER_FOUND
        priority = NotificationPriority.NORMAL
        
        print(f"\n🔔 Types de notification:")
        print(f"   notification_type: {notification_type} (type: {type(notification_type)})")
        print(f"   notification_type.value: {notification_type.value if hasattr(notification_type, 'value') else 'NO VALUE ATTR'}")
        print(f"   priority: {priority} (type: {type(priority)})")
        print(f"   priority.value: {priority.value if hasattr(priority, 'value') else 'NO VALUE ATTR'}")
        
        # Créer le service avec debug
        print(f"\n🔥 Création du service Firebase...")
        service = FirebaseNotificationService(db)
        
        # Tester l'envoi avec variables de template
        print(f"\n📱 Test d'envoi avec variables complètes...")
        test_vars = {
            "driver_name": "Jean Dupont",
            "passenger_name": "Marie Martin",
            "destination": "Gare de Lyon",
            "pickup_address": "Place de la République",
            "eta_minutes": "5",
            "trip_amount": "15.50",
            "distance_km": "3.2",
            "duration_minutes": "12",
            "vehicle_info": "Peugeot 308 • AB-123-CD",
            "estimated_earnings": "12.40"
        }
        
        import asyncio
        result = asyncio.run(service.send_notification(
            user_id=user.id,
            notification_type=notification_type,
            priority=priority,
            **test_vars
        ))
        
        print(f"\n✅ Résultat: {result}")
        
    except Exception as e:
        print(f"\n❌ ERREUR CAPTURÉE: {e}")
        print(f"Type d'erreur: {type(e)}")
        print("\n📋 STACK TRACE COMPLÈTE:")
        traceback.print_exc()
        
        # Analyser la stack trace
        print(f"\n🔍 ANALYSE DE L'ERREUR:")
        if "'str' object has no attribute 'value'" in str(e):
            print("   ⚠️  Erreur enum confirmée!")
            print("   🎯 Recherche de la variable string qui cause le problème...")
        else:
            print(f"   ℹ️  Erreur différente: {e}")

if __name__ == "__main__":
    debug_enum_error()

