"""
Service professionnel de tarification avec métriques intégrées.
"""

from datetime import datetime, time
from typing import Dict, Any
from enum import Enum

from ..models.trip import VehicleType
from ..services.metrics_service import get_metrics_collector
from ..models.metrics import MetricType, MetricCategory
from ..core.monitoring.decorators import monitor_business_operation, monitor_function


class PricingTier(str, Enum):
    """Niveaux de tarification."""
    NORMAL = "normal"
    PEAK = "peak"
    SURGE = "surge"


class PricingService:
    """Service de calcul des prix avec monitoring intégré."""
    
    # Tarifs de base par type de véhicule (DZD)
    BASE_PRICES = {
        VehicleType.STANDARD: {
            "base_fare": 150.0,      # Prix de base
            "per_km": 45.0,          # Prix par kilomètre
            "per_minute": 8.0,       # Prix par minute
            "minimum_fare": 200.0    # Prix minimum
        },
        VehicleType.COMFORT: {
            "base_fare": 200.0,
            "per_km": 55.0,
            "per_minute": 10.0,
            "minimum_fare": 250.0
        },
        VehicleType.PREMIUM: {
            "base_fare": 300.0,
            "per_km": 75.0,
            "per_minute": 15.0,
            "minimum_fare": 400.0
        },
        VehicleType.XL: {
            "base_fare": 250.0,
            "per_km": 65.0,
            "per_minute": 12.0,
            "minimum_fare": 350.0
        }
    }
    
    # Multiplicateurs selon l'heure
    TIME_MULTIPLIERS = {
        "night": 1.2,      # 22h-6h
        "peak": 1.3,       # 7h-9h et 17h-19h
        "weekend": 1.1,    # Samedi-Dimanche
        "normal": 1.0      # Heures normales
    }
    
    # Zones avec multiplicateurs
    ZONE_MULTIPLIERS = {
        "airport": 1.4,
        "city_center": 1.2,
        "business_district": 1.3,
        "residential": 1.0,
        "suburban": 0.9
    }
    
    def __init__(self):
        self.surge_multiplier = 1.0  # Multiplicateur de demande
        self.collector = get_metrics_collector()
    
    @monitor_business_operation("price_calculation", "pricing", track_value=True, value_field="final_price")
    def calculate_price(
        self, 
        distance_km: float, 
        duration_minutes: int,
        vehicle_type: VehicleType = VehicleType.STANDARD,
        pickup_zone: str = "residential",
        destination_zone: str = "residential",
        request_time: datetime = None
    ) -> float:
        """Calcule le prix d'une course avec métriques."""
        
        if request_time is None:
            request_time = datetime.now()
        
        # Tarifs de base
        pricing = self.BASE_PRICES[vehicle_type]
        
        # Calcul de base
        base_price = (
            pricing["base_fare"] +
            (distance_km * pricing["per_km"]) +
            (duration_minutes * pricing["per_minute"])
        )
        
        # Application du prix minimum
        base_price = max(base_price, pricing["minimum_fare"])
        
        # Multiplicateur temporel
        time_multiplier = self._get_time_multiplier(request_time)
        pricing_tier = self._get_pricing_tier(request_time)
        
        # Multiplicateur de zone (moyenne des zones de départ et arrivée)
        zone_multiplier = (
            self.ZONE_MULTIPLIERS.get(pickup_zone, 1.0) +
            self.ZONE_MULTIPLIERS.get(destination_zone, 1.0)
        ) / 2
        
        # Prix final avec tous les multiplicateurs
        final_price = base_price * time_multiplier * zone_multiplier * self.surge_multiplier
        
        # Métriques de tarification
        self.collector.record_metric(
            name="pricing_calculations_by_vehicle_type",
            value=1,
            metric_type=MetricType.COUNTER,
            category=MetricCategory.BUSINESS,
            labels={
                "vehicle_type": vehicle_type.value,
                "pricing_tier": pricing_tier.value,
                "pickup_zone": pickup_zone,
                "destination_zone": destination_zone
            },
            description="Calculs de prix par type de véhicule"
        )
        
        self.collector.record_metric(
            name="pricing_base_price",
            value=base_price,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={"vehicle_type": vehicle_type.value},
            description="Prix de base calculé"
        )
        
        self.collector.record_metric(
            name="pricing_final_price",
            value=final_price,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "vehicle_type": vehicle_type.value,
                "pricing_tier": pricing_tier.value,
                "price_range": self._get_price_range(final_price)
            },
            description="Prix final calculé"
        )
        
        # Métriques des multiplicateurs
        if time_multiplier > 1.0:
            self.collector.record_metric(
                name="pricing_time_multiplier_applied",
                value=time_multiplier,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={"pricing_tier": pricing_tier.value},
                description="Multiplicateur temporel appliqué"
            )
        
        if self.surge_multiplier > 1.0:
            self.collector.record_metric(
                name="pricing_surge_multiplier_applied",
                value=self.surge_multiplier,
                metric_type=MetricType.GAUGE,
                category=MetricCategory.BUSINESS,
                labels={"vehicle_type": vehicle_type.value},
                description="Multiplicateur de demande appliqué"
            )
        
        return round(final_price, 2)
    
    def _get_pricing_tier(self, request_time: datetime) -> PricingTier:
        """Détermine le niveau de tarification."""
        hour = request_time.hour
        weekday = request_time.weekday()
        
        if self.surge_multiplier > 1.5:
            return PricingTier.SURGE
        elif weekday >= 4 or (7 <= hour <= 9) or (17 <= hour <= 19) or hour >= 22 or hour < 6:
            return PricingTier.PEAK
        else:
            return PricingTier.NORMAL
    
    def _get_price_range(self, price: float) -> str:
        """Catégorise le prix pour les métriques."""
        if price < 250:
            return "low"
        elif price < 500:
            return "medium"
        elif price < 1000:
            return "high"
        else:
            return "premium"
    
    @monitor_business_operation("final_price_calculation", "pricing")
    def calculate_final_price(
        self,
        estimated_price: float,
        actual_duration_minutes: float,
        distance_km: float,
        vehicle_type: VehicleType = VehicleType.STANDARD
    ) -> float:
        """Calcule le prix final après la course."""
        
        pricing = self.BASE_PRICES[vehicle_type]
        
        # Recalcul basé sur la durée réelle
        actual_price = (
            pricing["base_fare"] +
            (distance_km * pricing["per_km"]) +
            (actual_duration_minutes * pricing["per_minute"])
        )
        
        # Le prix final ne peut pas dépasser 150% du prix estimé
        max_price = estimated_price * 1.5
        final_price = min(actual_price, max_price)
        
        # Application du prix minimum
        final_price = max(final_price, pricing["minimum_fare"])
        
        # Métriques de prix final
        price_difference = final_price - estimated_price
        price_variance_percent = (price_difference / estimated_price) * 100
        
        self.collector.record_metric(
            name="pricing_final_vs_estimated",
            value=price_difference,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "vehicle_type": vehicle_type.value,
                "variance_category": self._get_variance_category(price_variance_percent)
            },
            description="Différence entre prix final et estimé"
        )
        
        self.collector.record_metric(
            name="pricing_variance_percentage",
            value=abs(price_variance_percent),
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={"vehicle_type": vehicle_type.value},
            description="Pourcentage de variance du prix"
        )
        
        return round(final_price, 2)
    
    def _get_variance_category(self, variance_percent: float) -> str:
        """Catégorise la variance de prix."""
        abs_variance = abs(variance_percent)
        if abs_variance < 5:
            return "minimal"
        elif abs_variance < 15:
            return "moderate"
        elif abs_variance < 30:
            return "significant"
        else:
            return "major"
    
    def _get_time_multiplier(self, request_time: datetime) -> float:
        """Détermine le multiplicateur selon l'heure."""
        hour = request_time.hour
        weekday = request_time.weekday()  # 0=Lundi, 6=Dimanche
        
        # Weekend (Vendredi-Samedi en Algérie)
        if weekday >= 4:  # Vendredi et Samedi
            return self.TIME_MULTIPLIERS["weekend"]
        
        # Heures de nuit (22h-6h)
        if hour >= 22 or hour < 6:
            return self.TIME_MULTIPLIERS["night"]
        
        # Heures de pointe (7h-9h et 17h-19h)
        if (7 <= hour <= 9) or (17 <= hour <= 19):
            return self.TIME_MULTIPLIERS["peak"]
        
        # Heures normales
        return self.TIME_MULTIPLIERS["normal"]
    
    @monitor_function(category=MetricCategory.BUSINESS)
    def get_pricing_breakdown(
        self,
        distance_km: float,
        duration_minutes: int,
        vehicle_type: VehicleType = VehicleType.STANDARD,
        pickup_zone: str = "residential",
        destination_zone: str = "residential",
        request_time: datetime = None
    ) -> Dict[str, Any]:
        """Retourne le détail de la tarification."""
        
        if request_time is None:
            request_time = datetime.now()
        
        pricing = self.BASE_PRICES[vehicle_type]
        
        # Calculs détaillés
        base_fare = pricing["base_fare"]
        distance_cost = distance_km * pricing["per_km"]
        time_cost = duration_minutes * pricing["per_minute"]
        subtotal = base_fare + distance_cost + time_cost
        
        # Multiplicateurs
        time_multiplier = self._get_time_multiplier(request_time)
        zone_multiplier = (
            self.ZONE_MULTIPLIERS.get(pickup_zone, 1.0) +
            self.ZONE_MULTIPLIERS.get(destination_zone, 1.0)
        ) / 2
        
        # Prix avec multiplicateurs
        price_with_multipliers = subtotal * time_multiplier * zone_multiplier * self.surge_multiplier
        
        # Prix final (avec minimum)
        final_price = max(price_with_multipliers, pricing["minimum_fare"])
        
        return {
            "base_fare": round(base_fare, 2),
            "distance_cost": round(distance_cost, 2),
            "time_cost": round(time_cost, 2),
            "subtotal": round(subtotal, 2),
            "time_multiplier": time_multiplier,
            "zone_multiplier": round(zone_multiplier, 2),
            "surge_multiplier": self.surge_multiplier,
            "minimum_fare": pricing["minimum_fare"],
            "final_price": round(final_price, 2),
            "currency": "DZD"
        }
    
    @monitor_business_operation("surge_pricing_update", "pricing")
    def set_surge_pricing(self, multiplier: float) -> None:
        """Définit le multiplicateur de demande."""
        old_multiplier = self.surge_multiplier
        self.surge_multiplier = max(1.0, min(multiplier, 3.0))  # Entre 1.0 et 3.0
        
        # Métrique de changement de surge pricing
        self.collector.record_metric(
            name="pricing_surge_multiplier_change",
            value=self.surge_multiplier,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "previous_multiplier": str(old_multiplier),
                "new_multiplier": str(self.surge_multiplier),
                "surge_level": self._get_surge_level(self.surge_multiplier)
            },
            description="Changement du multiplicateur de demande"
        )
    
    def _get_surge_level(self, multiplier: float) -> str:
        """Catégorise le niveau de surge pricing."""
        if multiplier == 1.0:
            return "none"
        elif multiplier < 1.3:
            return "low"
        elif multiplier < 1.8:
            return "medium"
        elif multiplier < 2.5:
            return "high"
        else:
            return "extreme"
    
    def get_vehicle_type_prices(self) -> Dict[str, Dict[str, float]]:
        """Retourne tous les tarifs par type de véhicule."""
        return self.BASE_PRICES.copy()
    
    @monitor_business_operation("earnings_estimation", "pricing")
    def estimate_earnings(self, distance_km: float, vehicle_type: VehicleType = VehicleType.STANDARD) -> Dict[str, float]:
        """Estime les gains pour un conducteur."""
        # Estimation basique (20 minutes de trajet moyen)
        estimated_duration = max(int(distance_km * 2), 10)
        
        gross_price = self.calculate_price(distance_km, estimated_duration, vehicle_type)
        
        # Commission plateforme (20%)
        commission = gross_price * 0.20
        net_earnings = gross_price - commission
        
        # Métriques d'estimation de gains
        self.collector.record_metric(
            name="pricing_estimated_driver_earnings",
            value=net_earnings,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={
                "vehicle_type": vehicle_type.value,
                "earnings_range": self._get_earnings_range(net_earnings)
            },
            description="Gains estimés pour le conducteur"
        )
        
        self.collector.record_metric(
            name="pricing_platform_commission",
            value=commission,
            metric_type=MetricType.GAUGE,
            category=MetricCategory.BUSINESS,
            labels={"vehicle_type": vehicle_type.value},
            description="Commission de la plateforme"
        )
        
        return {
            "gross_price": round(gross_price, 2),
            "commission": round(commission, 2),
            "net_earnings": round(net_earnings, 2),
            "commission_rate": 0.20
        }
    
    def _get_earnings_range(self, earnings: float) -> str:
        """Catégorise les gains pour les métriques."""
        if earnings < 200:
            return "low"
        elif earnings < 500:
            return "medium"
        elif earnings < 1000:
            return "high"
        else:
            return "premium"

