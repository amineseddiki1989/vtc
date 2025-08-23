"""
Service de paiement Stripe intégré pour l'application VTC.
"""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from datetime import datetime
import logging
import os

# Import Stripe (sera installé via requirements)
try:
    import stripe
except ImportError:
    stripe = None
    logging.warning("Stripe non installé. Utilisez: pip install stripe")

from ..models.trip import Trip, TripStatus
from ..models.payment import Payment, PaymentStatus, DriverPayout, PaymentRefund
from ..models.user import User

logger = logging.getLogger(__name__)


class StripePaymentService:
    """Service de paiement Stripe avec gestion des commissions"""
    
    def __init__(self, db: Session):
        self.db = db
        self.platform_commission_rate = 0.20  # 20% de commission
        
        # Configuration Stripe
        if stripe:
            stripe.api_key = os.getenv("STRIPE_SECRET_KEY")
            self.stripe_publishable_key = os.getenv("STRIPE_PUBLISHABLE_KEY")
            self.webhook_secret = os.getenv("STRIPE_WEBHOOK_SECRET")
            
            # Vérifier que les clés sont configurées
            if not stripe.api_key:
                logger.error("STRIPE_SECRET_KEY non configurée")
            if not self.webhook_secret:
                logger.error("STRIPE_WEBHOOK_SECRET non configurée")
        else:
            logger.error("Stripe non configuré")
    
    def create_payment_intent(self, trip_id: str) -> Dict[str, Any]:
        """
        Crée un PaymentIntent Stripe pour une course
        """
        if not stripe:
            raise RuntimeError("Stripe non configuré")
        
        logger.info(f"Création PaymentIntent pour course {trip_id}")
        
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.status != TripStatus.COMPLETED:
            raise ValueError("Course non terminée")
        
        # Vérifier si un paiement existe déjà
        existing_payment = self.db.query(Payment).filter(Payment.trip_id == trip_id).first()
        if existing_payment and existing_payment.status != PaymentStatus.FAILED:
            raise ValueError("Paiement déjà existant pour cette course")
        
        try:
            # Créer le PaymentIntent Stripe
            amount_cents = int(trip.final_price * 100)  # Convertir en centimes
            
            payment_intent = stripe.PaymentIntent.create(
                amount=amount_cents,
                currency="eur",
                metadata={
                    "trip_id": trip_id,
                    "passenger_id": trip.passenger_id,
                    "driver_id": trip.driver_id
                },
                description=f"Course VTC {trip_id}",
                automatic_payment_methods={"enabled": True}
            )
            
            # Créer l'enregistrement Payment
            payment = Payment(
                trip_id=trip_id,
                stripe_payment_intent_id=payment_intent.id,
                status=PaymentStatus.PENDING
            )
            payment.calculate_amounts(trip.final_price, self.platform_commission_rate)
            
            self.db.add(payment)
            self.db.commit()
            
            logger.info(
                f"PaymentIntent créé",
                trip_id=trip_id,
                payment_intent_id=payment_intent.id,
                amount=trip.final_price
            )
            
            return {
                "payment_id": payment.id,
                "client_secret": payment_intent.client_secret,
                "publishable_key": self.stripe_publishable_key,
                "amount": trip.final_price,
                "currency": "EUR"
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Erreur Stripe lors de la création PaymentIntent: {str(e)}")
            raise RuntimeError(f"Erreur de paiement: {str(e)}")
    
    def confirm_payment(self, payment_intent_id: str) -> Dict[str, Any]:
        """
        Confirme un paiement et traite les transferts
        """
        if not stripe:
            raise RuntimeError("Stripe non configuré")
        
        logger.info(f"Confirmation paiement {payment_intent_id}")
        
        payment = self.db.query(Payment).filter(
            Payment.stripe_payment_intent_id == payment_intent_id
        ).first()
        
        if not payment:
            raise ValueError("Paiement non trouvé")
        
        try:
            # Récupérer le PaymentIntent depuis Stripe
            payment_intent = stripe.PaymentIntent.retrieve(payment_intent_id)
            
            if payment_intent.status == "succeeded":
                # Marquer le paiement comme réussi
                payment.status = PaymentStatus.COMPLETED
                payment.completed_at = datetime.utcnow()
                payment.stripe_charge_id = payment_intent.latest_charge
                
                # Mettre à jour le statut de la course
                trip = payment.trip
                trip.payment_status = PaymentStatus.COMPLETED
                
                self.db.commit()
                
                # Traiter le paiement du conducteur
                payout_result = self._process_driver_payout(payment)
                
                logger.info(
                    f"Paiement confirmé avec succès",
                    payment_id=payment.id,
                    trip_id=payment.trip_id,
                    amount=payment.amount
                )
                
                return {
                    "status": "completed",
                    "payment_id": payment.id,
                    "amount": payment.amount,
                    "driver_payout": payout_result
                }
            
            elif payment_intent.status == "requires_action":
                return {
                    "status": "requires_action",
                    "client_secret": payment_intent.client_secret
                }
            
            else:
                # Paiement échoué
                payment.status = PaymentStatus.FAILED
                payment.failed_at = datetime.utcnow()
                payment.failure_reason = f"Stripe status: {payment_intent.status}"
                
                self.db.commit()
                
                logger.warning(
                    f"Paiement échoué",
                    payment_id=payment.id,
                    stripe_status=payment_intent.status
                )
                
                return {
                    "status": "failed",
                    "reason": payment.failure_reason
                }
                
        except stripe.error.StripeError as e:
            logger.error(f"Erreur Stripe lors de la confirmation: {str(e)}")
            
            payment.status = PaymentStatus.FAILED
            payment.failed_at = datetime.utcnow()
            payment.failure_reason = str(e)
            self.db.commit()
            
            raise RuntimeError(f"Erreur de confirmation: {str(e)}")
    
    def _process_driver_payout(self, payment: Payment) -> Dict[str, Any]:
        """
        Traite le paiement vers le conducteur
        """
        if not stripe:
            return {"status": "skipped", "reason": "Stripe non configuré"}
        
        logger.info(f"Traitement paiement conducteur pour payment {payment.id}")
        
        trip = payment.trip
        driver = trip.driver
        
        if not driver:
            logger.error("Aucun conducteur assigné à cette course")
            return {"status": "failed", "reason": "Aucun conducteur"}
        
        try:
            # Créer l'enregistrement DriverPayout
            payout = DriverPayout(
                payment_id=payment.id,
                driver_id=driver.id,
                amount=payment.driver_amount,
                status=PaymentStatus.PROCESSING
            )
            
            self.db.add(payout)
            self.db.commit()
            
            # Dans un vrai environnement, on ferait un transfer Stripe
            # Pour la démo, on simule un succès immédiat
            payout.status = PaymentStatus.COMPLETED
            payout.completed_at = datetime.utcnow()
            payout.stripe_transfer_id = f"tr_demo_{payout.id}"
            
            self.db.commit()
            
            logger.info(
                f"Paiement conducteur traité",
                payout_id=payout.id,
                driver_id=driver.id,
                amount=payment.driver_amount
            )
            
            return {
                "status": "completed",
                "payout_id": payout.id,
                "driver_amount": payment.driver_amount,
                "platform_fee": payment.platform_fee
            }
            
        except Exception as e:
            logger.error(f"Erreur lors du paiement conducteur: {str(e)}")
            return {"status": "failed", "reason": str(e)}
    
    def create_refund(self, payment_id: str, amount: Optional[float] = None, 
                     reason: str = "requested_by_customer") -> Dict[str, Any]:
        """
        Crée un remboursement pour un paiement
        """
        if not stripe:
            raise RuntimeError("Stripe non configuré")
        
        logger.info(f"Création remboursement pour payment {payment_id}")
        
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        if not payment:
            raise ValueError("Paiement non trouvé")
        
        if not payment.can_be_refunded:
            raise ValueError("Paiement non remboursable")
        
        refund_amount = amount or payment.amount
        
        try:
            # Créer le remboursement Stripe
            stripe_refund = stripe.Refund.create(
                payment_intent=payment.stripe_payment_intent_id,
                amount=int(refund_amount * 100),  # En centimes
                reason=reason,
                metadata={
                    "payment_id": payment_id,
                    "trip_id": payment.trip_id
                }
            )
            
            # Créer l'enregistrement PaymentRefund
            refund = PaymentRefund(
                payment_id=payment_id,
                amount=refund_amount,
                reason=reason,
                stripe_refund_id=stripe_refund.id,
                status=PaymentStatus.COMPLETED,
                completed_at=datetime.utcnow()
            )
            
            # Mettre à jour le paiement
            payment.refund_amount = refund_amount
            if refund_amount >= payment.amount:
                payment.status = PaymentStatus.REFUNDED
            else:
                payment.status = PaymentStatus.PARTIALLY_REFUNDED
            payment.refunded_at = datetime.utcnow()
            
            self.db.add(refund)
            self.db.commit()
            
            logger.info(
                f"Remboursement créé",
                refund_id=refund.id,
                amount=refund_amount,
                stripe_refund_id=stripe_refund.id
            )
            
            return {
                "status": "completed",
                "refund_id": refund.id,
                "amount": refund_amount,
                "stripe_refund_id": stripe_refund.id
            }
            
        except stripe.error.StripeError as e:
            logger.error(f"Erreur Stripe lors du remboursement: {str(e)}")
            raise RuntimeError(f"Erreur de remboursement: {str(e)}")
    
    def handle_webhook(self, payload: str, signature: str) -> Dict[str, Any]:
        """
        Traite les webhooks Stripe
        """
        if not stripe:
            raise RuntimeError("Stripe non configuré")
        
        try:
            event = stripe.Webhook.construct_event(
                payload, signature, self.webhook_secret
            )
            
            logger.info(f"Webhook Stripe reçu: {event['type']}")
            
            if event['type'] == 'payment_intent.succeeded':
                payment_intent = event['data']['object']
                self.confirm_payment(payment_intent['id'])
                
            elif event['type'] == 'payment_intent.payment_failed':
                payment_intent = event['data']['object']
                self._handle_payment_failure(payment_intent['id'])
                
            elif event['type'] == 'charge.dispute.created':
                charge = event['data']['object']
                self._handle_chargeback(charge['payment_intent'])
            
            return {"status": "handled", "event_type": event['type']}
            
        except ValueError as e:
            logger.error(f"Signature webhook invalide: {str(e)}")
            raise ValueError("Signature invalide")
        except Exception as e:
            logger.error(f"Erreur traitement webhook: {str(e)}")
            raise RuntimeError(f"Erreur webhook: {str(e)}")
    
    def _handle_payment_failure(self, payment_intent_id: str):
        """Traite l'échec d'un paiement"""
        payment = self.db.query(Payment).filter(
            Payment.stripe_payment_intent_id == payment_intent_id
        ).first()
        
        if payment:
            payment.status = PaymentStatus.FAILED
            payment.failed_at = datetime.utcnow()
            self.db.commit()
            
            logger.warning(f"Paiement échoué: {payment.id}")
    
    def _handle_chargeback(self, payment_intent_id: str):
        """Traite un chargeback"""
        payment = self.db.query(Payment).filter(
            Payment.stripe_payment_intent_id == payment_intent_id
        ).first()
        
        if payment:
            # Créer un remboursement automatique
            self.create_refund(
                payment.id,
                payment.amount,
                "chargeback_dispute"
            )
            
            logger.warning(f"Chargeback traité pour paiement: {payment.id}")
    
    def get_payment_status(self, payment_id: str) -> Dict[str, Any]:
        """Récupère le statut d'un paiement"""
        payment = self.db.query(Payment).filter(Payment.id == payment_id).first()
        
        if not payment:
            raise ValueError("Paiement non trouvé")
        
        return {
            "payment_id": payment.id,
            "trip_id": payment.trip_id,
            "status": payment.status.value,
            "amount": payment.amount,
            "platform_fee": payment.platform_fee,
            "driver_amount": payment.driver_amount,
            "created_at": payment.created_at.isoformat(),
            "completed_at": payment.completed_at.isoformat() if payment.completed_at else None,
            "stripe_payment_intent_id": payment.stripe_payment_intent_id,
            "refund_amount": payment.refund_amount
        }
    
    def get_driver_earnings(self, driver_id: str, start_date: datetime, 
                           end_date: datetime) -> Dict[str, Any]:
        """Calcule les gains d'un conducteur sur une période"""
        payouts = self.db.query(DriverPayout).filter(
            DriverPayout.driver_id == driver_id,
            DriverPayout.status == PaymentStatus.COMPLETED,
            DriverPayout.completed_at >= start_date,
            DriverPayout.completed_at <= end_date
        ).all()
        
        total_earnings = sum(payout.amount for payout in payouts)
        trip_count = len(payouts)
        
        return {
            "driver_id": driver_id,
            "period": {
                "start": start_date.isoformat(),
                "end": end_date.isoformat()
            },
            "total_earnings": total_earnings,
            "trip_count": trip_count,
            "average_per_trip": total_earnings / trip_count if trip_count > 0 else 0,
            "payouts": [
                {
                    "payout_id": payout.id,
                    "amount": payout.amount,
                    "completed_at": payout.completed_at.isoformat()
                }
                for payout in payouts
            ]
        }

