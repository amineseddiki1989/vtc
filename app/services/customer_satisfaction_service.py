"""
Service de métriques de satisfaction client pour surveiller les ratings et feedback.
"""

from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import func, and_, or_
from datetime import datetime, timedelta
import statistics

from ..models.rating import Rating
from ..models.trip import Trip, TripStatus
from ..models.user import User, UserRole
from ..services.metrics_service import get_metrics_collector
from ..models.metrics import MetricType, MetricCategory
from ..core.monitoring.decorators import monitor_business_operation, monitor_function


class CustomerSatisfactionService:
    """Service de surveillance de la satisfaction client."""
    
    def __init__(self, db: Session):
        self.db = db
        self.collector = get_metrics_collector()
    
    @monitor_business_operation("rating_creation", "satisfaction", track_value=True, value_field="rating")
    def create_rating(
        self,
        trip_id: str,
        rater_id: str,
        rated_id: str,
        rating: int,
        comment: Optional[str] = None,
        punctuality: Optional[int] = None,
        cleanliness: Optional[int] = None,
        communication: Optional[int] = None,
        safety: Optional[int] = None,
        is_anonymous: bool = False
    ) -> Rating:
        """Crée une nouvelle évaluation avec métriques."""
        
        # Vérifier que la course existe et est terminée
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            raise ValueError("Course non trouvée")
        
        if trip.status != TripStatus.COMPLETED:
            raise ValueError("Impossible d'évaluer une course non terminée")
        
        # Vérifier que l'évaluateur est autorisé
        if trip.passenger_id != rater_id and trip.driver_id != rater_id:
            raise ValueError("Seuls le passager et le conducteur peuvent évaluer")
        
        # Déterminer qui évalue qui
        rater_role = "passenger" if trip.passenger_id == rater_id else "driver"
        rated_role = "driver" if rater_role == "passenger" else "passenger"
        
        # Créer l'évaluation
        rating_obj = Rating(
            id=f"rating_{trip_id}_{rater_role}",
            trip_id=trip_id,
            rater_id=rater_id,
            rated_id=rated_id,
            rating=rating,
            comment=comment,
            punctuality=punctuality,
            cleanliness=cleanliness,
            communication=communication,
            safety=safety,
            is_anonymous=is_anonymous
        )
        
        self.db.add(rating_obj)
        self.db.commit()
        self.db.refresh(rating_obj)
        
        # Métriques de satisfaction
        self._record_rating_metrics(rating_obj, rater_role, rated_role, trip)
        
        return rating_obj
    
    def _record_rating_metrics(self, rating: Rating, rater_role: str, rated_role: str, trip: Trip):
        """Enregistre les métriques liées à une évaluation."""
        
        # Métrique principale de rating
        self.collector.record_metric(
            name="satisfaction_ratings_created",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={
                "rater_role": rater_role,
                "rated_role": rated_role,
                "rating_value": str(rating.rating),
                "rating_category": self._get_rating_category(rating.rating),
                "vehicle_type": trip.vehicle_type.value,
                "has_comment": str(bool(rating.comment))
            },
            user_id=rating.rater_id,
            description="Évaluation créée"
        )
        
        # Métrique de valeur de rating
        self.collector.record_metric(
            name="satisfaction_rating_value",
            value=rating.rating,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "rater_role": rater_role,
                "rated_role": rated_role,
                "vehicle_type": trip.vehicle_type.value
            },
            user_id=rating.rated_id,
            description="Valeur de l'évaluation"
        )
        
        # Métriques des critères détaillés
        criteria = {
            "punctuality": rating.punctuality,
            "cleanliness": rating.cleanliness,
            "communication": rating.communication,
            "safety": rating.safety
        }
        
        for criterion, value in criteria.items():
            if value is not None:
                self.collector.record_metric(
                    name=f"satisfaction_{criterion}_rating",
                    value=value,
                    metric_type=MetricType.GAUGE,
                    category=MetricCategory.BUSINESS,
                    labels={
                        "rater_role": rater_role,
                        "rated_role": rated_role,
                        "rating_category": self._get_rating_category(value)
                    },
                    user_id=rating.rated_id,
                    description=f"Évaluation du critère {criterion}"
                )
        
        # Métriques de satisfaction par niveau
        satisfaction_level = self._get_satisfaction_level(rating.rating)
        self.collector.record_metric(
            name=f"satisfaction_level_{satisfaction_level}",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={
                "rater_role": rater_role,
                "rated_role": rated_role,
                "vehicle_type": trip.vehicle_type.value
            },
            user_id=rating.rated_id,
            description=f"Évaluation de niveau {satisfaction_level}"
        )
        
        # Métriques de commentaires
        if rating.comment:
            comment_sentiment = self._analyze_comment_sentiment(rating.comment)
            comment_length = len(rating.comment)
            
            self.collector.record_metric(
                name="satisfaction_comments_created",
                value=1,
                metric_type=MetricType.COUNTER,
                category=MetricCategory.BUSINESS,
                labels={
                    "sentiment": comment_sentiment,
                    "length_category": self._get_comment_length_category(comment_length),
                    "rater_role": rater_role,
                    "rated_role": rated_role
                },
                user_id=rating.rater_id,
                description="Commentaire d'évaluation créé"
            )
    
    def _get_rating_category(self, rating: int) -> str:
        """Catégorise une note."""
        if rating <= 2:
            return "poor"
        elif rating == 3:
            return "average"
        elif rating == 4:
            return "good"
        else:
            return "excellent"
    
    def _get_satisfaction_level(self, rating: int) -> str:
        """Détermine le niveau de satisfaction."""
        if rating <= 2:
            return "dissatisfied"
        elif rating == 3:
            return "neutral"
        else:
            return "satisfied"
    
    def _analyze_comment_sentiment(self, comment: str) -> str:
        """Analyse basique du sentiment d'un commentaire."""
        comment_lower = comment.lower()
        
        # Mots positifs
        positive_words = [
            "excellent", "parfait", "super", "génial", "formidable", "merci",
            "recommande", "professionnel", "ponctuel", "propre", "sympa",
            "agréable", "rapide", "efficace", "courtois", "aimable"
        ]
        
        # Mots négatifs
        negative_words = [
            "mauvais", "horrible", "nul", "décevant", "retard", "sale",
            "impoli", "dangereux", "lent", "problème", "plainte", "insatisfait",
            "mécontent", "inacceptable", "inadmissible"
        ]
        
        positive_count = sum(1 for word in positive_words if word in comment_lower)
        negative_count = sum(1 for word in negative_words if word in comment_lower)
        
        if positive_count > negative_count:
            return "positive"
        elif negative_count > positive_count:
            return "negative"
        else:
            return "neutral"
    
    def _get_comment_length_category(self, length: int) -> str:
        """Catégorise la longueur d'un commentaire."""
        if length < 20:
            return "short"
        elif length < 100:
            return "medium"
        else:
            return "long"
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def calculate_user_rating_stats(self, user_id: str, role: UserRole) -> Dict[str, Any]:
        """Calcule les statistiques d'évaluation d'un utilisateur."""
        
        # Récupérer toutes les évaluations reçues
        ratings = self.db.query(Rating).filter(Rating.rated_id == user_id).all()
        
        if not ratings:
            return {
                "average_rating": None,
                "total_ratings": 0,
                "rating_distribution": {},
                "criteria_averages": {}
            }
        
        # Calculs statistiques
        rating_values = [r.rating for r in ratings]
        average_rating = statistics.mean(rating_values)
        
        # Distribution des notes
        rating_distribution = {}
        for i in range(1, 6):
            count = sum(1 for r in rating_values if r == i)
            rating_distribution[str(i)] = count
        
        # Moyennes des critères
        criteria_averages = {}
        for criterion in ['punctuality', 'cleanliness', 'communication', 'safety']:
            values = [getattr(r, criterion) for r in ratings if getattr(r, criterion) is not None]
            if values:
                criteria_averages[criterion] = statistics.mean(values)
        
        # Métriques de statistiques utilisateur
        self.collector.record_metric(
            name="satisfaction_user_average_rating",
            value=average_rating,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "user_role": role.value,
                "rating_category": self._get_rating_category(round(average_rating)),
                "total_ratings_range": self._get_ratings_count_range(len(ratings))
            },
            user_id=user_id,
            description="Note moyenne d'un utilisateur"
        )
        
        self.collector.record_metric(
            name="satisfaction_user_total_ratings",
            value=len(ratings),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "user_role": role.value,
                "ratings_range": self._get_ratings_count_range(len(ratings))
            },
            user_id=user_id,
            description="Nombre total d'évaluations reçues"
        )
        
        return {
            "average_rating": round(average_rating, 2),
            "total_ratings": len(ratings),
            "rating_distribution": rating_distribution,
            "criteria_averages": {k: round(v, 2) for k, v in criteria_averages.items()}
        }
    
    def _get_ratings_count_range(self, count: int) -> str:
        """Catégorise le nombre d'évaluations."""
        if count < 5:
            return "very_few"
        elif count < 20:
            return "few"
        elif count < 50:
            return "moderate"
        elif count < 100:
            return "many"
        else:
            return "very_many"
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def get_satisfaction_trends(self, days: int = 30) -> Dict[str, Any]:
        """Analyse les tendances de satisfaction sur une période."""
        
        start_date = datetime.utcnow() - timedelta(days=days)
        
        # Récupérer les évaluations de la période
        ratings = self.db.query(Rating).filter(
            Rating.created_at >= start_date
        ).all()
        
        if not ratings:
            return {"message": "Aucune évaluation sur la période"}
        
        # Calculs de tendances
        total_ratings = len(ratings)
        average_rating = statistics.mean([r.rating for r in ratings])
        
        # Distribution par note
        distribution = {}
        for i in range(1, 6):
            count = sum(1 for r in ratings if r.rating == i)
            percentage = (count / total_ratings) * 100
            distribution[str(i)] = {
                "count": count,
                "percentage": round(percentage, 1)
            }
        
        # Taux de satisfaction (4-5 étoiles)
        satisfied_count = sum(1 for r in ratings if r.rating >= 4)
        satisfaction_rate = (satisfied_count / total_ratings) * 100
        
        # Métriques de tendances
        self.collector.record_metric(
            name="satisfaction_period_average_rating",
            value=average_rating,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "period_days": str(days),
                "rating_category": self._get_rating_category(round(average_rating))
            },
            description=f"Note moyenne sur {days} jours"
        )
        
        self.collector.record_metric(
            name="satisfaction_period_rate_percent",
            value=satisfaction_rate,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "period_days": str(days),
                "satisfaction_level": self._get_satisfaction_rate_level(satisfaction_rate)
            },
            description=f"Taux de satisfaction sur {days} jours"
        )
        
        return {
            "period_days": days,
            "total_ratings": total_ratings,
            "average_rating": round(average_rating, 2),
            "satisfaction_rate": round(satisfaction_rate, 1),
            "distribution": distribution
        }
    
    def _get_satisfaction_rate_level(self, rate: float) -> str:
        """Catégorise le taux de satisfaction."""
        if rate < 60:
            return "poor"
        elif rate < 75:
            return "fair"
        elif rate < 85:
            return "good"
        else:
            return "excellent"
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def identify_satisfaction_issues(self) -> Dict[str, Any]:
        """Identifie les problèmes de satisfaction récurrents."""
        
        # Évaluations récentes négatives (1-2 étoiles)
        recent_date = datetime.utcnow() - timedelta(days=7)
        poor_ratings = self.db.query(Rating).filter(
            and_(
                Rating.rating <= 2,
                Rating.created_at >= recent_date
            )
        ).all()
        
        # Analyse des commentaires négatifs
        negative_comments = [r.comment for r in poor_ratings if r.comment]
        
        # Problèmes par critère
        criteria_issues = {}
        for criterion in ['punctuality', 'cleanliness', 'communication', 'safety']:
            poor_criterion_ratings = [
                getattr(r, criterion) for r in poor_ratings 
                if getattr(r, criterion) is not None and getattr(r, criterion) <= 2
            ]
            if poor_criterion_ratings:
                criteria_issues[criterion] = len(poor_criterion_ratings)
        
        # Métriques d'identification des problèmes
        self.collector.record_metric(
            name="satisfaction_poor_ratings_recent",
            value=len(poor_ratings),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={"period": "7_days"},
            description="Nombre d'évaluations négatives récentes"
        )
        
        for criterion, count in criteria_issues.items():
            self.collector.record_metric(
                name=f"satisfaction_issues_{criterion}",
                value=count,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={"period": "7_days"},
                description=f"Problèmes identifiés pour {criterion}"
            )
        
        return {
            "poor_ratings_count": len(poor_ratings),
            "criteria_issues": criteria_issues,
            "negative_comments_count": len(negative_comments)
        }
    
    @monitor_business_operation("satisfaction_alert_check", "satisfaction")
    def check_satisfaction_alerts(self) -> List[Dict[str, Any]]:
        """Vérifie les alertes de satisfaction."""
        alerts = []
        
        # Alerte : Baisse de la note moyenne
        recent_ratings = self.db.query(Rating).filter(
            Rating.created_at >= datetime.utcnow() - timedelta(days=7)
        ).all()
        
        if recent_ratings:
            recent_average = statistics.mean([r.rating for r in recent_ratings])
            
            if recent_average < 3.5:
                alerts.append({
                    "type": "low_average_rating",
                    "severity": "high" if recent_average < 3.0 else "medium",
                    "value": recent_average,
                    "message": f"Note moyenne récente faible: {recent_average:.2f}"
                })
                
                # Métrique d'alerte
                self.collector.record_metric(
                    name="satisfaction_alerts_triggered",
                    value=1,
                    metric_type=MetricType.COUNTER,
                    category=MetricCategory.BUSINESS,
                    labels={
                        "alert_type": "low_average_rating",
                        "severity": "high" if recent_average < 3.0 else "medium"
                    },
                    description="Alerte de satisfaction déclenchée"
                )
        
        # Alerte : Trop d'évaluations négatives
        poor_ratings_count = len([r for r in recent_ratings if r.rating <= 2])
        if poor_ratings_count > 5:
            alerts.append({
                "type": "high_poor_ratings",
                "severity": "high",
                "value": poor_ratings_count,
                "message": f"Trop d'évaluations négatives: {poor_ratings_count}"
            })
        
        return alerts

