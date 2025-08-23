"""
Service Firebase pour notifications push avec templates personnalisés.
Support complet des notifications VTC avec templates dynamiques.
"""

import json
import asyncio
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, asdict
from enum import Enum
import logging

try:
    import firebase_admin
    from firebase_admin import credentials, messaging
    FIREBASE_AVAILABLE = True
except ImportError:
    FIREBASE_AVAILABLE = False

from sqlalchemy.orm import Session

from ..models.user import User, UserRole
from ..models.trip import Trip, TripStatus
from ..services.metrics_service import get_metrics_collector
from ..core.config.settings import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

class NotificationType(str, Enum):
    """Types de notifications VTC."""
    # Course - Passager
    TRIP_REQUEST_SENT = "trip_request_sent"
    DRIVER_FOUND = "driver_found"
    DRIVER_ARRIVING = "driver_arriving"
    DRIVER_ARRIVED = "driver_arrived"
    TRIP_STARTED = "trip_started"
    TRIP_COMPLETED = "trip_completed"
    TRIP_CANCELLED = "trip_cancelled"
    
    # Course - Conducteur
    NEW_TRIP_REQUEST = "new_trip_request"
    TRIP_ACCEPTED = "trip_accepted"
    PASSENGER_WAITING = "passenger_waiting"
    TRIP_PAYMENT_RECEIVED = "trip_payment_received"
    
    # Système
    ACCOUNT_VERIFIED = "account_verified"
    PAYMENT_FAILED = "payment_failed"
    MAINTENANCE_NOTICE = "maintenance_notice"
    PROMOTION_OFFER = "promotion_offer"
    
    # Urgence
    EMERGENCY_ALERT = "emergency_alert"
    SAFETY_CHECK = "safety_check"

class NotificationPriority(str, Enum):
    """Priorités des notifications."""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"

@dataclass
class NotificationTemplate:
    """Template de notification personnalisé."""
    title: str
    body: str
    icon: Optional[str] = None
    sound: Optional[str] = None
    click_action: Optional[str] = None
    color: Optional[str] = None
    tag: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

@dataclass
class NotificationResult:
    """Résultat d'envoi de notification."""
    success: bool
    message_id: Optional[str] = None
    error: Optional[str] = None
    tokens_sent: int = 0
    tokens_failed: int = 0

class FirebaseNotificationService:
    """Service Firebase pour notifications push avec templates personnalisés."""
    
    def __init__(self, db: Session):
        self.db = db
        self.metrics_collector = get_metrics_collector()
        self.firebase_app = None
        self.is_initialized = False
        
        # Templates de notifications personnalisés
        self.templates = self._initialize_templates()
        
        # Configuration Firebase
        self.firebase_config = {
            "project_id": getattr(settings, 'firebase_project_id', 'uber-vtc-demo'),
            "service_account_path": getattr(settings, 'firebase_service_account_path', None),
            "use_mock": getattr(settings, 'firebase_use_mock', True)  # Mode mock pour tests
        }
    
    def _initialize_templates(self) -> Dict[NotificationType, NotificationTemplate]:
        """Initialiser les templates de notifications personnalisés."""
        
        return {
            # === NOTIFICATIONS PASSAGER ===
            NotificationType.TRIP_REQUEST_SENT: NotificationTemplate(
                title="🚗 Demande de course envoyée",
                body="Nous recherchons un conducteur près de vous...",
                icon="trip_request",
                sound="notification_sound",
                color="#4CAF50",
                click_action="OPEN_TRIP_TRACKING",
                data={"action": "track_trip", "screen": "trip_tracking"}
            ),
            
            NotificationType.DRIVER_FOUND: NotificationTemplate(
                title="✅ Conducteur trouvé !",
                body="{driver_name} arrive dans {eta_minutes} minutes • {vehicle_info}",
                icon="driver_found",
                sound="success_sound",
                color="#2196F3",
                click_action="OPEN_TRIP_TRACKING",
                data={"action": "track_driver", "screen": "trip_tracking"}
            ),
            
            NotificationType.DRIVER_ARRIVING: NotificationTemplate(
                title="🚗 Votre conducteur arrive",
                body="{driver_name} sera là dans {eta_minutes} minutes",
                icon="driver_arriving",
                sound="arrival_sound",
                color="#FF9800",
                click_action="OPEN_TRIP_TRACKING",
                data={"action": "prepare_pickup", "screen": "trip_tracking"}
            ),
            
            NotificationType.DRIVER_ARRIVED: NotificationTemplate(
                title="📍 Votre conducteur est arrivé",
                body="{driver_name} vous attend • {vehicle_info}",
                icon="driver_arrived",
                sound="arrival_sound",
                color="#4CAF50",
                click_action="OPEN_TRIP_TRACKING",
                data={"action": "meet_driver", "screen": "trip_tracking"}
            ),
            
            NotificationType.TRIP_STARTED: NotificationTemplate(
                title="🛣️ Course en cours",
                body="Direction {destination} • Durée estimée: {duration_minutes} min",
                icon="trip_started",
                sound="trip_start_sound",
                color="#9C27B0",
                click_action="OPEN_TRIP_TRACKING",
                data={"action": "track_trip", "screen": "trip_tracking"}
            ),
            
            NotificationType.TRIP_COMPLETED: NotificationTemplate(
                title="🎉 Course terminée",
                body="Merci d'avoir voyagé avec nous ! Montant: {trip_amount}€",
                icon="trip_completed",
                sound="success_sound",
                color="#4CAF50",
                click_action="OPEN_TRIP_SUMMARY",
                data={"action": "rate_trip", "screen": "trip_summary"}
            ),
            
            NotificationType.TRIP_CANCELLED: NotificationTemplate(
                title="❌ Course annulée",
                body="Votre course a été annulée. {cancellation_reason}",
                icon="trip_cancelled",
                sound="notification_sound",
                color="#F44336",
                click_action="OPEN_HOME",
                data={"action": "book_new_trip", "screen": "home"}
            ),
            
            # === NOTIFICATIONS CONDUCTEUR ===
            NotificationType.NEW_TRIP_REQUEST: NotificationTemplate(
                title="🔔 Nouvelle demande de course",
                body="Course vers {destination} • Distance: {distance_km}km • Gain: {estimated_earnings}€",
                icon="new_trip_request",
                sound="new_request_sound",
                color="#2196F3",
                click_action="OPEN_TRIP_REQUEST",
                data={"action": "accept_trip", "screen": "trip_request"}
            ),
            
            NotificationType.TRIP_ACCEPTED: NotificationTemplate(
                title="✅ Course acceptée",
                body="Rendez-vous chez {passenger_name} • {pickup_address}",
                icon="trip_accepted",
                sound="success_sound",
                color="#4CAF50",
                click_action="OPEN_NAVIGATION",
                data={"action": "navigate_to_pickup", "screen": "navigation"}
            ),
            
            NotificationType.PASSENGER_WAITING: NotificationTemplate(
                title="⏰ Passager en attente",
                body="{passenger_name} vous attend depuis {waiting_minutes} minutes",
                icon="passenger_waiting",
                sound="reminder_sound",
                color="#FF9800",
                click_action="OPEN_TRIP_TRACKING",
                data={"action": "contact_passenger", "screen": "trip_tracking"}
            ),
            
            NotificationType.TRIP_PAYMENT_RECEIVED: NotificationTemplate(
                title="💰 Paiement reçu",
                body="Vous avez reçu {payment_amount}€ pour votre course",
                icon="payment_received",
                sound="payment_sound",
                color="#4CAF50",
                click_action="OPEN_EARNINGS",
                data={"action": "view_earnings", "screen": "earnings"}
            ),
            
            # === NOTIFICATIONS SYSTÈME ===
            NotificationType.ACCOUNT_VERIFIED: NotificationTemplate(
                title="✅ Compte vérifié",
                body="Votre compte a été vérifié avec succès. Bienvenue !",
                icon="account_verified",
                sound="success_sound",
                color="#4CAF50",
                click_action="OPEN_HOME",
                data={"action": "explore_app", "screen": "home"}
            ),
            
            NotificationType.PAYMENT_FAILED: NotificationTemplate(
                title="⚠️ Problème de paiement",
                body="Le paiement de votre course a échoué. Veuillez mettre à jour votre moyen de paiement.",
                icon="payment_failed",
                sound="error_sound",
                color="#F44336",
                click_action="OPEN_PAYMENT_SETTINGS",
                data={"action": "update_payment", "screen": "payment_settings"}
            ),
            
            NotificationType.MAINTENANCE_NOTICE: NotificationTemplate(
                title="🔧 Maintenance programmée",
                body="L'application sera indisponible de {start_time} à {end_time} pour maintenance.",
                icon="maintenance",
                sound="notification_sound",
                color="#607D8B",
                click_action="OPEN_HOME",
                data={"action": "acknowledge", "screen": "home"}
            ),
            
            NotificationType.PROMOTION_OFFER: NotificationTemplate(
                title="🎁 Offre spéciale",
                body="{promotion_title} • {discount_text}",
                icon="promotion",
                sound="promotion_sound",
                color="#E91E63",
                click_action="OPEN_PROMOTIONS",
                data={"action": "view_promotion", "screen": "promotions"}
            ),
            
            # === NOTIFICATIONS URGENCE ===
            NotificationType.EMERGENCY_ALERT: NotificationTemplate(
                title="🚨 ALERTE URGENCE",
                body="Une alerte d'urgence a été déclenchée. Contactez immédiatement le support.",
                icon="emergency",
                sound="emergency_sound",
                color="#F44336",
                click_action="OPEN_EMERGENCY",
                data={"action": "emergency_contact", "screen": "emergency"}
            ),
            
            NotificationType.SAFETY_CHECK: NotificationTemplate(
                title="🛡️ Vérification de sécurité",
                body="Votre course dure plus longtemps que prévu. Tout va bien ?",
                icon="safety_check",
                sound="safety_sound",
                color="#FF9800",
                click_action="OPEN_SAFETY_CHECK",
                data={"action": "safety_response", "screen": "safety_check"}
            )
        }
    
    async def initialize_firebase(self) -> bool:
        """Initialiser Firebase Admin SDK."""
        
        if self.is_initialized:
            return True
        
        try:
            if not FIREBASE_AVAILABLE:
                logger.warning("Firebase SDK non disponible, utilisation du mode mock")
                self.is_initialized = True
                return True
            
            # Mode mock pour les tests
            if self.firebase_config["use_mock"]:
                logger.info("Firebase initialisé en mode mock pour les tests")
                self.is_initialized = True
                return True
            
            # Configuration réelle Firebase
            service_account_path = self.firebase_config["service_account_path"]
            
            if not service_account_path:
                logger.warning("Chemin du service account Firebase non configuré, utilisation du mode mock")
                self.firebase_config["use_mock"] = True
                self.is_initialized = True
                return True
            
            # Initialiser Firebase avec le service account
            cred = credentials.Certificate(service_account_path)
            self.firebase_app = firebase_admin.initialize_app(cred, {
                'projectId': self.firebase_config["project_id"]
            })
            
            logger.info(f"Firebase initialisé avec succès pour le projet {self.firebase_config['project_id']}")
            self.is_initialized = True
            return True
            
        except Exception as e:
            logger.error(f"Erreur initialisation Firebase: {e}")
            logger.info("Basculement en mode mock")
            self.firebase_config["use_mock"] = True
            self.is_initialized = True
            return True
    
    def _format_template(self, template: NotificationTemplate, **kwargs) -> NotificationTemplate:
        """Formater un template avec les variables dynamiques."""
        
        formatted_template = NotificationTemplate(
            title=template.title.format(**kwargs) if template.title else "",
            body=template.body.format(**kwargs) if template.body else "",
            icon=template.icon,
            sound=template.sound,
            click_action=template.click_action,
            color=template.color,
            tag=template.tag,
            data=template.data.copy() if template.data else None
        )
        
        # Ajouter les données dynamiques
        if formatted_template.data:
            formatted_template.data.update(kwargs)
        else:
            formatted_template.data = kwargs
        
        return formatted_template
    
    async def send_notification(
        self,
        user_id: str,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **template_vars
    ) -> NotificationResult:
        """Envoyer une notification à un utilisateur."""
        
        await self.initialize_firebase()
        
        try:
            # Récupérer l'utilisateur
            user = self.db.query(User).filter(User.id == user_id).first()
            if not user:
                return NotificationResult(
                    success=False,
                    error=f"Utilisateur {user_id} non trouvé"
                )
            
            # Récupérer le template
            template = self.templates.get(notification_type)
            if not template:
                return NotificationResult(
                    success=False,
                    error=f"Template {notification_type} non trouvé"
                )
            
            # Formater le template
            formatted_template = self._format_template(template, **template_vars)
            
            # Simuler l'envoi en mode mock
            if self.firebase_config["use_mock"]:
                return await self._send_mock_notification(
                    user, formatted_template, notification_type, priority
                )
            
            # Envoi réel Firebase
            return await self._send_firebase_notification(
                user, formatted_template, notification_type, priority
            )
            
        except Exception as e:
            logger.error(f"Erreur envoi notification {notification_type} à {user_id}: {e}")
            return NotificationResult(
                success=False,
                error=str(e)
            )
    
    async def _send_mock_notification(
        self,
        user: User,
        template: NotificationTemplate,
        notification_type: NotificationType,
        priority: NotificationPriority
    ) -> NotificationResult:
        """Simuler l'envoi d'une notification (mode mock)."""
        
        # Simuler un délai d'envoi
        await asyncio.sleep(0.1)
        
        # Log de la notification simulée
        notification_type_value = notification_type.value if hasattr(notification_type, 'value') else str(notification_type)
        priority_value = priority.value if hasattr(priority, 'value') else str(priority)
        
        logger.info(f"📱 NOTIFICATION MOCK envoyée à {user.email}")
        logger.info(f"   Type: {notification_type_value}")
        logger.info(f"   Titre: {template.title}")
        logger.info(f"   Corps: {template.body}")
        logger.info(f"   Priorité: {priority_value}")
        logger.info(f"   Données: {template.data}")
        
        # Enregistrer les métriques
        try:
            logger.debug(f"🔍 DEBUG METRICS - user.role: {user.role} (type: {type(user.role)})")
            user_role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
            logger.debug(f"🔍 DEBUG METRICS - user_role_value: {user_role_value}")
            
            logger.debug(f"🔍 DEBUG METRICS - notification_type: {notification_type} (type: {type(notification_type)})")
            notification_type_value = notification_type.value if hasattr(notification_type, 'value') else str(notification_type)
            logger.debug(f"🔍 DEBUG METRICS - notification_type_value: {notification_type_value}")
            
            logger.debug(f"🔍 DEBUG METRICS - priority: {priority} (type: {type(priority)})")
            priority_value = priority.value if hasattr(priority, 'value') else str(priority)
            logger.debug(f"🔍 DEBUG METRICS - priority_value: {priority_value}")
            
            logger.debug(f"🔍 DEBUG METRICS - Avant record_metric")
            self.metrics_collector.record_metric(
                name="notification_sent_mock",
                value=1,
                metric_type="counter",
                category="notifications",
                labels={
                    "type": notification_type_value,
                    "priority": priority_value,
                    "user_role": user_role_value
                },
                user_id=user.id,
                description=f"Notification mock {notification_type_value} envoyée"
            )
            logger.debug(f"🔍 DEBUG METRICS - Après record_metric")
        except Exception as metrics_error:
            logger.error(f"🚨 ERREUR DANS METRICS: {metrics_error}")
            logger.error(f"🚨 TYPE ERREUR METRICS: {type(metrics_error)}")
            import traceback
            logger.error(f"🚨 STACK TRACE METRICS: {traceback.format_exc()}")
            raise
        
        # Simuler un succès avec un ID de message fictif
        mock_message_id = f"mock_{notification_type_value}_{int(datetime.now().timestamp())}"
        
        return NotificationResult(
            success=True,
            message_id=mock_message_id,
            tokens_sent=1,
            tokens_failed=0
        )
    
    async def _send_firebase_notification(
        self,
        user: User,
        template: NotificationTemplate,
        notification_type: NotificationType,
        priority: NotificationPriority
    ) -> NotificationResult:
        """Envoyer une notification via Firebase (mode réel)."""
        
        try:
            # Récupérer les tokens FCM de l'utilisateur
            # Note: Dans une vraie implémentation, les tokens seraient stockés en base
            fcm_tokens = getattr(user, 'fcm_tokens', [])
            
            if not fcm_tokens:
                logger.warning(f"Aucun token FCM pour l'utilisateur {user.id}")
                return NotificationResult(
                    success=False,
                    error="Aucun token FCM disponible"
                )
            
            # Construire le message Firebase
            android_config = messaging.AndroidConfig(
                priority=self._get_android_priority(priority),
                notification=messaging.AndroidNotification(
                    title=template.title,
                    body=template.body,
                    icon=template.icon,
                    color=template.color,
                    sound=template.sound,
                    tag=template.tag,
                    click_action=template.click_action
                )
            )
            
            apns_config = messaging.APNSConfig(
                payload=messaging.APNSPayload(
                    aps=messaging.Aps(
                        alert=messaging.ApsAlert(
                            title=template.title,
                            body=template.body
                        ),
                        sound=template.sound or "default",
                        badge=1
                    )
                )
            )
            
            message = messaging.MulticastMessage(
                tokens=fcm_tokens,
                notification=messaging.Notification(
                    title=template.title,
                    body=template.body
                ),
                data=template.data or {},
                android=android_config,
                apns=apns_config
            )
            
            # Envoyer la notification
            response = messaging.send_multicast(message)
            
            # Analyser la réponse
            success_count = response.success_count
            failure_count = response.failure_count
            
            # Log des erreurs
            for idx, resp in enumerate(response.responses):
                if not resp.success:
                    logger.error(f"Erreur envoi à token {idx}: {resp.exception}")
            
            # Enregistrer les métriques de succès
            user_role_value = user.role.value if hasattr(user.role, 'value') else str(user.role)
            notification_type_value = notification_type.value if hasattr(notification_type, 'value') else str(notification_type)
            priority_value = priority.value if hasattr(priority, 'value') else str(priority)
            
            self.metrics_collector.record_metric(
                name="notification_sent_firebase",
                value=success_count,
                metric_type="counter",
                category="notifications",
                labels={
                    "type": notification_type_value,
                    "priority": priority_value,
                    "user_role": user_role_value
                },
                user_id=user.id,
                description=f"Notification Firebase {notification_type_value} envoyée"
            )   
            if failure_count > 0:
                self.metrics_collector.record_metric(
                    name="notification_failed_firebase",
                    value=failure_count,
                    metric_type="counter",
                    category="notifications",
                    labels={
                        "type": notification_type_value,
                        "priority": priority_value
                    },
                    user_id=user.id,
                    description=f"Notification Firebase {notification_type_value} échouée"
                )
            
            return NotificationResult(
                success=success_count > 0,
                message_id=response.responses[0].message_id if response.responses else None,
                tokens_sent=success_count,
                tokens_failed=failure_count
            )
            
        except Exception as e:
            logger.error(f"Erreur Firebase: {e}")
            return NotificationResult(
                success=False,
                error=str(e)
            )
    
    def _get_android_priority(self, priority: NotificationPriority) -> str:
        """Convertir la priorité en priorité Android."""
        priority_map = {
            NotificationPriority.LOW: "normal",
            NotificationPriority.NORMAL: "normal",
            NotificationPriority.HIGH: "high",
            NotificationPriority.CRITICAL: "high"
        }
        return priority_map.get(priority, "normal")
    
    async def send_trip_notification(
        self,
        trip_id: str,
        notification_type: NotificationType,
        target_role: Optional[UserRole] = None
    ) -> List[NotificationResult]:
        """Envoyer une notification liée à une course."""
        
        try:
            # Récupérer la course
            trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
            if not trip:
                logger.error(f"Course {trip_id} non trouvée")
                return []
            
            # Déterminer les destinataires
            recipients = []
            if target_role == UserRole.PASSENGER or target_role is None:
                if trip.passenger_id:
                    recipients.append((trip.passenger_id, UserRole.PASSENGER))
            
            if target_role == UserRole.DRIVER or target_role is None:
                if trip.driver_id:
                    recipients.append((trip.driver_id, UserRole.DRIVER))
            
            # Variables du template basées sur la course
            template_vars = {
                "trip_id": trip.id,
                "pickup_address": getattr(trip, 'pickup_address', 'Adresse de départ'),
                "destination": getattr(trip, 'destination_address', 'Destination'),
                "trip_amount": f"{getattr(trip, 'total_amount', 0):.2f}",
                "distance_km": f"{getattr(trip, 'distance_km', 0):.1f}",
                "duration_minutes": getattr(trip, 'duration_minutes', 0),
                "estimated_earnings": f"{getattr(trip, 'driver_earnings', 0):.2f}"
            }
            
            # Ajouter des variables spécifiques selon le type
            if hasattr(trip, 'driver') and trip.driver:
                template_vars.update({
                    "driver_name": f"{trip.driver.first_name} {trip.driver.last_name}",
                    "vehicle_info": f"{getattr(trip.driver, 'vehicle_model', 'Véhicule')} • {getattr(trip.driver, 'license_plate', 'ABC-123')}"
                })
            
            if hasattr(trip, 'passenger') and trip.passenger:
                template_vars.update({
                    "passenger_name": f"{trip.passenger.first_name} {trip.passenger.last_name}"
                })
            
            # Envoyer les notifications
            results = []
            for user_id, role in recipients:
                result = await self.send_notification(
                    user_id=user_id,
                    notification_type=notification_type,
                    priority=NotificationPriority.HIGH,
                    **template_vars
                )
                results.append(result)
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur envoi notification course {trip_id}: {e}")
            return []
    
    async def send_bulk_notification(
        self,
        user_ids: List[str],
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **template_vars
    ) -> List[NotificationResult]:
        """Envoyer une notification à plusieurs utilisateurs."""
        
        results = []
        
        # Envoyer en parallèle pour améliorer les performances
        tasks = [
            self.send_notification(
                user_id=user_id,
                notification_type=notification_type,
                priority=priority,
                **template_vars
            )
            for user_id in user_ids
        ]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les exceptions
        processed_results = []
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erreur notification utilisateur {user_ids[i]}: {result}")
                processed_results.append(NotificationResult(
                    success=False,
                    error=str(result)
                ))
            else:
                processed_results.append(result)
        
        return processed_results
    
    def get_available_templates(self) -> Dict[str, Dict[str, Any]]:
        """Obtenir la liste des templates disponibles."""
        
        templates_info = {}
        
        for notification_type, template in self.templates.items():
            templates_info[notification_type.value] = {
                "title": template.title,
                "body": template.body,
                "icon": template.icon,
                "color": template.color,
                "click_action": template.click_action,
                "data": template.data
            }
        
        return templates_info
    
    async def test_notification_service(self) -> Dict[str, Any]:
        """Tester le service de notifications."""
        
        await self.initialize_firebase()
        
        test_results = {
            "firebase_initialized": self.is_initialized,
            "mock_mode": self.firebase_config["use_mock"],
            "templates_count": len(self.templates),
            "available_types": [t.value for t in NotificationType],
            "test_timestamp": datetime.now(timezone.utc).isoformat()
        }
        
        return test_results


    # ==========================================
    # MÉTHODES D'ENVOIS MULTIPLES
    # ==========================================
    
    async def send_notifications_to_multiple_users(
        self,
        user_ids: List[str],
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **template_vars
    ) -> List[NotificationResult]:
        """Envoyer une notification à plusieurs utilisateurs."""
        
        if not user_ids:
            return []
        
        logger.info(f"Envoi notification {notification_type} à {len(user_ids)} utilisateurs")
        
        # Créer les tâches d'envoi en parallèle
        tasks = []
        for user_id in user_ids:
            task = self.send_notification(
                user_id=user_id,
                notification_type=notification_type,
                priority=priority,
                **template_vars
            )
            tasks.append(task)
        
        # Exécuter en parallèle avec gestion des exceptions
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les résultats et exceptions
        processed_results = []
        success_count = 0
        error_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erreur notification utilisateur {user_ids[i]}: {result}")
                processed_results.append(NotificationResult(
                    success=False,
                    error=str(result)
                ))
                error_count += 1
            else:
                processed_results.append(result)
                if result.success:
                    success_count += 1
                else:
                    error_count += 1
        
        # Enregistrer les métriques globales
        try:
            self.metrics_collector.record_metric(
                name="notification_batch_sent",
                value=1,
                metric_type="counter",
                category="notifications",
                labels={
                    "notification_type": str(notification_type),
                    "priority": str(priority),
                    "total_users": len(user_ids),
                    "success_count": success_count,
                    "error_count": error_count
                }
            )
        except Exception as e:
            logger.warning(f"Erreur enregistrement métriques batch: {e}")
        
        logger.info(f"Batch notification terminé: {success_count} succès, {error_count} erreurs")
        return processed_results
    
    async def send_bulk_notifications(
        self,
        notifications: List[Dict[str, Any]]
    ) -> List[NotificationResult]:
        """Envoyer plusieurs notifications différentes en lot."""
        
        if not notifications:
            return []
        
        logger.info(f"Envoi en lot de {len(notifications)} notifications")
        
        # Valider et créer les tâches
        tasks = []
        valid_notifications = []
        
        for i, notif in enumerate(notifications):
            try:
                # Validation des champs requis
                required_fields = ['user_id', 'notification_type']
                for field in required_fields:
                    if field not in notif:
                        raise ValueError(f"Champ requis manquant: {field}")
                
                # Convertir notification_type en enum si c'est une string
                notification_type = notif['notification_type']
                if isinstance(notification_type, str):
                    notification_type = NotificationType(notification_type)
                
                # Convertir priority en enum si c'est une string
                priority = notif.get('priority', NotificationPriority.NORMAL)
                if isinstance(priority, str):
                    priority = NotificationPriority(priority)
                
                # Extraire les variables de template
                template_vars = notif.get('template_vars', {})
                
                # Créer la tâche
                task = self.send_notification(
                    user_id=notif['user_id'],
                    notification_type=notification_type,
                    priority=priority,
                    **template_vars
                )
                tasks.append(task)
                valid_notifications.append(notif)
                
            except Exception as e:
                logger.error(f"Erreur validation notification {i}: {e}")
                # Créer une coroutine qui retourne un résultat d'erreur
                async def create_error_result():
                    return NotificationResult(
                        success=False,
                        error=f"Validation error: {str(e)}"
                    )
                tasks.append(create_error_result())
                valid_notifications.append(notif)
        
        # Exécuter toutes les tâches en parallèle
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Traiter les résultats
        processed_results = []
        success_count = 0
        error_count = 0
        
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Erreur notification bulk {i}: {result}")
                processed_results.append(NotificationResult(
                    success=False,
                    error=str(result)
                ))
                error_count += 1
            else:
                processed_results.append(result)
                if result.success:
                    success_count += 1
                else:
                    error_count += 1
        
        # Enregistrer les métriques
        try:
            self.metrics_collector.record_metric(
                name="notification_bulk_sent",
                value=1,
                metric_type="counter",
                category="notifications",
                labels={
                    "total_notifications": len(notifications),
                    "success_count": success_count,
                    "error_count": error_count
                }
            )
        except Exception as e:
            logger.warning(f"Erreur enregistrement métriques bulk: {e}")
        
        logger.info(f"Bulk notifications terminé: {success_count} succès, {error_count} erreurs")
        return processed_results
    
    async def send_notifications_by_role(
        self,
        role: UserRole,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        limit: Optional[int] = None,
        **template_vars
    ) -> List[NotificationResult]:
        """Envoyer une notification à tous les utilisateurs d'un rôle spécifique."""
        
        try:
            # Récupérer les utilisateurs par rôle
            query = self.db.query(User).filter(User.role == role, User.is_active == True)
            
            if limit:
                query = query.limit(limit)
            
            users = query.all()
            user_ids = [user.id for user in users]
            
            if not user_ids:
                logger.warning(f"Aucun utilisateur trouvé pour le rôle {role}")
                return []
            
            logger.info(f"Envoi notification {notification_type} à {len(user_ids)} utilisateurs {role}")
            
            # Utiliser la méthode d'envoi multiple
            results = await self.send_notifications_to_multiple_users(
                user_ids=user_ids,
                notification_type=notification_type,
                priority=priority,
                **template_vars
            )
            
            # Enregistrer les métriques spécifiques au rôle
            success_count = sum(1 for r in results if r.success)
            try:
                self.metrics_collector.record_metric(
                    name="notification_role_broadcast",
                    value=1,
                    metric_type="counter",
                    category="notifications",
                    labels={
                        "role": str(role),
                        "notification_type": str(notification_type),
                        "users_targeted": len(user_ids),
                        "success_count": success_count
                    }
                )
            except Exception as e:
                logger.warning(f"Erreur enregistrement métriques role: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur envoi notifications par rôle {role}: {e}")
            return [NotificationResult(
                success=False,
                error=f"Erreur envoi par rôle: {str(e)}"
            )]
    
    async def send_notifications_by_trip(
        self,
        trip_id: str,
        notification_type: NotificationType,
        priority: NotificationPriority = NotificationPriority.NORMAL,
        **template_vars
    ) -> List[NotificationResult]:
        """Envoyer une notification à tous les participants d'une course."""
        
        try:
            # Récupérer la course
            trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
            if not trip:
                return [NotificationResult(
                    success=False,
                    error=f"Course {trip_id} non trouvée"
                )]
            
            # Récupérer les participants (passager et conducteur)
            user_ids = []
            if trip.passenger_id:
                user_ids.append(trip.passenger_id)
            if trip.driver_id:
                user_ids.append(trip.driver_id)
            
            if not user_ids:
                return [NotificationResult(
                    success=False,
                    error=f"Aucun participant trouvé pour la course {trip_id}"
                )]
            
            # Ajouter les informations de la course aux variables de template
            trip_vars = {
                'trip_id': trip_id,
                'pickup_address': trip.pickup_address,
                'destination_address': trip.destination_address,
                'status': str(trip.status),
                **template_vars
            }
            
            logger.info(f"Envoi notification {notification_type} aux participants de la course {trip_id}")
            
            # Envoyer aux participants
            results = await self.send_notifications_to_multiple_users(
                user_ids=user_ids,
                notification_type=notification_type,
                priority=priority,
                **trip_vars
            )
            
            # Enregistrer les métriques spécifiques aux courses
            success_count = sum(1 for r in results if r.success)
            try:
                self.metrics_collector.record_metric(
                    name="notification_trip_broadcast",
                    value=1,
                    metric_type="counter",
                    category="notifications",
                    labels={
                        "trip_id": trip_id,
                        "notification_type": str(notification_type),
                        "participants": len(user_ids),
                        "success_count": success_count
                    }
                )
            except Exception as e:
                logger.warning(f"Erreur enregistrement métriques trip: {e}")
            
            return results
            
        except Exception as e:
            logger.error(f"Erreur envoi notifications course {trip_id}: {e}")
            return [NotificationResult(
                success=False,
                error=f"Erreur envoi course: {str(e)}"
            )]
    
    def get_bulk_notification_stats(self, results: List[NotificationResult]) -> Dict[str, Any]:
        """Obtenir les statistiques d'un envoi en lot."""
        
        total = len(results)
        success_count = sum(1 for r in results if r.success)
        error_count = total - success_count
        
        # Analyser les types d'erreurs
        error_types = {}
        for result in results:
            if not result.success and result.error:
                error_type = result.error.split(':')[0] if ':' in result.error else result.error
                error_types[error_type] = error_types.get(error_type, 0) + 1
        
        # Calculer les tokens
        total_tokens_sent = sum(r.tokens_sent for r in results if r.tokens_sent)
        total_tokens_failed = sum(r.tokens_failed for r in results if r.tokens_failed)
        
        return {
            "total_notifications": total,
            "success_count": success_count,
            "error_count": error_count,
            "success_rate": (success_count / total * 100) if total > 0 else 0,
            "total_tokens_sent": total_tokens_sent,
            "total_tokens_failed": total_tokens_failed,
            "error_types": error_types,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

