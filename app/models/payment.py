"""
Modèles de paiement pour l'application VTC.
"""

from sqlalchemy import Column, String, Float, DateTime, Text, ForeignKey, Enum, Boolean
from sqlalchemy.orm import relationship
import enum
from datetime import datetime
import uuid

from ..core.database.base import Base


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REFUNDED = "refunded"
    PARTIALLY_REFUNDED = "partially_refunded"


class PaymentMethod(str, enum.Enum):
    CARD = "card"
    WALLET = "wallet"
    BANK_TRANSFER = "bank_transfer"
    CASH = "cash"


class Payment(Base):
    """Paiement d'une course"""
    __tablename__ = "payments"
    
    id = Column(String, primary_key=True, default=lambda: f"pay_{uuid.uuid4().hex[:12]}")
    trip_id = Column(String, ForeignKey("trips.id"), nullable=False, unique=True)
    
    # Montants
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR", nullable=False)
    platform_fee = Column(Float, nullable=False, default=0.0)
    driver_amount = Column(Float, nullable=False, default=0.0)
    
    # Statut et méthode
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    payment_method = Column(Enum(PaymentMethod), default=PaymentMethod.CARD, nullable=False)
    
    # Intégration Stripe
    stripe_payment_intent_id = Column(String(255), nullable=True, unique=True)
    stripe_charge_id = Column(String(255), nullable=True)
    stripe_transfer_id = Column(String(255), nullable=True)
    
    # Métadonnées
    failure_reason = Column(Text, nullable=True)
    refund_reason = Column(Text, nullable=True)
    refund_amount = Column(Float, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    refunded_at = Column(DateTime, nullable=True)
    
    # Relations
    trip = relationship("Trip", back_populates="payment")
    
    @property
    def is_successful(self) -> bool:
        """Vérifie si le paiement est réussi"""
        return self.status == PaymentStatus.COMPLETED
    
    @property
    def is_pending(self) -> bool:
        """Vérifie si le paiement est en attente"""
        return self.status in [PaymentStatus.PENDING, PaymentStatus.PROCESSING]
    
    @property
    def can_be_refunded(self) -> bool:
        """Vérifie si le paiement peut être remboursé"""
        return self.status == PaymentStatus.COMPLETED and not self.refund_amount
    
    def calculate_amounts(self, total_amount: float, platform_commission_rate: float = 0.20):
        """Calcule les montants de commission"""
        self.amount = total_amount
        self.platform_fee = total_amount * platform_commission_rate
        self.driver_amount = total_amount - self.platform_fee


class DriverPayout(Base):
    """Paiement vers un conducteur"""
    __tablename__ = "driver_payouts"
    
    id = Column(String, primary_key=True, default=lambda: f"payout_{uuid.uuid4().hex[:12]}")
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False)
    driver_id = Column(String, ForeignKey("users.id"), nullable=False)
    
    # Montants
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR", nullable=False)
    
    # Statut
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    
    # Intégration Stripe
    stripe_transfer_id = Column(String(255), nullable=True, unique=True)
    stripe_account_id = Column(String(255), nullable=True)
    
    # Métadonnées
    failure_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Relations
    payment = relationship("Payment")
    driver = relationship("User")
    
    @property
    def is_successful(self) -> bool:
        """Vérifie si le paiement conducteur est réussi"""
        return self.status == PaymentStatus.COMPLETED


class PaymentRefund(Base):
    """Remboursement d'un paiement"""
    __tablename__ = "payment_refunds"
    
    id = Column(String, primary_key=True, default=lambda: f"refund_{uuid.uuid4().hex[:12]}")
    payment_id = Column(String, ForeignKey("payments.id"), nullable=False)
    
    # Montants
    amount = Column(Float, nullable=False)
    currency = Column(String(3), default="EUR", nullable=False)
    
    # Statut et raison
    status = Column(Enum(PaymentStatus), default=PaymentStatus.PENDING, nullable=False)
    reason = Column(Text, nullable=False)
    
    # Intégration Stripe
    stripe_refund_id = Column(String(255), nullable=True, unique=True)
    
    # Métadonnées
    failure_reason = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)
    failed_at = Column(DateTime, nullable=True)
    
    # Relations
    payment = relationship("Payment")
    
    @property
    def is_successful(self) -> bool:
        """Vérifie si le remboursement est réussi"""
        return self.status == PaymentStatus.COMPLETED

