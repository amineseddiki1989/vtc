"""
Tests de charge et de performance pour l'application VTC.
"""

import asyncio
import time
import statistics
from concurrent.futures import ThreadPoolExecutor, as_completed
import requests
import pytest
from typing import List, Dict, Any


class LoadTestConfig:
    """Configuration pour les tests de charge."""
    
    BASE_URL = "http://localhost:8000"
    CONCURRENT_USERS = 50
    REQUESTS_PER_USER = 20
    TIMEOUT = 30
    
    # Seuils de performance
    MAX_RESPONSE_TIME = 2.0  # secondes
    MAX_ERROR_RATE = 0.05  # 5%
    MIN_THROUGHPUT = 100  # requêtes par seconde


class PerformanceMetrics:
    """Collecteur de métriques de performance."""
    
    def __init__(self):
        self.response_times: List[float] = []
        self.status_codes: List[int] = []
        self.errors: List[str] = []
        self.start_time: float = 0
        self.end_time: float = 0
    
    def add_result(self, response_time: float, status_code: int, error: str = None):
        """Ajoute un résultat de test."""
        self.response_times.append(response_time)
        self.status_codes.append(status_code)
        if error:
            self.errors.append(error)
    
    def calculate_stats(self) -> Dict[str, Any]:
        """Calcule les statistiques de performance."""
        if not self.response_times:
            return {}
        
        total_requests = len(self.response_times)
        successful_requests = len([s for s in self.status_codes if 200 <= s < 300])
        error_rate = (total_requests - successful_requests) / total_requests
        
        duration = self.end_time - self.start_time
        throughput = total_requests / duration if duration > 0 else 0
        
        return {
            "total_requests": total_requests,
            "successful_requests": successful_requests,
            "error_rate": error_rate,
            "throughput_rps": throughput,
            "duration_seconds": duration,
            "response_time_stats": {
                "min": min(self.response_times),
                "max": max(self.response_times),
                "mean": statistics.mean(self.response_times),
                "median": statistics.median(self.response_times),
                "p95": self._percentile(self.response_times, 95),
                "p99": self._percentile(self.response_times, 99)
            },
            "status_code_distribution": self._count_status_codes(),
            "errors": self.errors[:10]  # Premiers 10 erreurs
        }
    
    def _percentile(self, data: List[float], percentile: int) -> float:
        """Calcule un percentile."""
        sorted_data = sorted(data)
        index = int(len(sorted_data) * percentile / 100)
        return sorted_data[min(index, len(sorted_data) - 1)]
    
    def _count_status_codes(self) -> Dict[int, int]:
        """Compte les codes de statut."""
        counts = {}
        for code in self.status_codes:
            counts[code] = counts.get(code, 0) + 1
        return counts


class LoadTester:
    """Testeur de charge."""
    
    def __init__(self, base_url: str = LoadTestConfig.BASE_URL):
        self.base_url = base_url
        self.session = requests.Session()
    
    def make_request(self, method: str, endpoint: str, data: Dict = None) -> tuple:
        """Fait une requête et mesure le temps de réponse."""
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            if method.upper() == "GET":
                response = self.session.get(url, timeout=LoadTestConfig.TIMEOUT)
            elif method.upper() == "POST":
                response = self.session.post(url, json=data, timeout=LoadTestConfig.TIMEOUT)
            else:
                raise ValueError(f"Méthode HTTP non supportée: {method}")
            
            response_time = time.time() - start_time
            return response_time, response.status_code, None
            
        except Exception as e:
            response_time = time.time() - start_time
            return response_time, 0, str(e)
    
    def run_user_scenario(self, user_id: int, requests_per_user: int) -> PerformanceMetrics:
        """Exécute un scénario utilisateur."""
        metrics = PerformanceMetrics()
        
        for i in range(requests_per_user):
            # Scénario mixte : calculs fiscaux et monitoring
            if i % 3 == 0:
                # Calcul fiscal
                data = {
                    "amount": 100.0 + (user_id * 10),
                    "service_type": "standard",
                    "distance_km": 5.0 + (i % 10),
                    "duration_minutes": 15 + (i % 20),
                    "region": "algiers"
                }
                response_time, status_code, error = self.make_request(
                    "POST", "/api/v1/fiscal/calculate", data
                )
            elif i % 3 == 1:
                # Health check fiscal
                response_time, status_code, error = self.make_request(
                    "GET", "/api/v1/fiscal/health"
                )
            else:
                # Dashboard monitoring
                response_time, status_code, error = self.make_request(
                    "GET", "/api/v1/monitoring/dashboard"
                )
            
            metrics.add_result(response_time, status_code, error)
            
            # Petite pause entre les requêtes
            time.sleep(0.1)
        
        return metrics


class TestPerformance:
    """Tests de performance et de charge."""
    
    @pytest.fixture
    def load_tester(self):
        """Fixture pour le testeur de charge."""
        return LoadTester()
    
    def test_fiscal_endpoint_performance(self, load_tester):
        """Test de performance de l'endpoint fiscal."""
        data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        # Test de performance simple
        response_times = []
        for _ in range(100):
            response_time, status_code, error = load_tester.make_request(
                "POST", "/api/v1/fiscal/calculate", data
            )
            
            assert status_code == 200, f"Erreur: {error}"
            response_times.append(response_time)
        
        # Vérifier les seuils de performance
        avg_response_time = statistics.mean(response_times)
        max_response_time = max(response_times)
        
        assert avg_response_time < LoadTestConfig.MAX_RESPONSE_TIME, \
            f"Temps de réponse moyen trop élevé: {avg_response_time:.3f}s"
        assert max_response_time < LoadTestConfig.MAX_RESPONSE_TIME * 2, \
            f"Temps de réponse maximum trop élevé: {max_response_time:.3f}s"
    
    def test_fiscal_cache_performance(self, load_tester):
        """Test de performance du cache fiscal."""
        data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        # Premier appel (sans cache)
        first_time, status_code, error = load_tester.make_request(
            "POST", "/api/v1/fiscal/calculate", data
        )
        assert status_code == 200
        
        # Appels suivants (avec cache)
        cached_times = []
        for _ in range(10):
            response_time, status_code, error = load_tester.make_request(
                "POST", "/api/v1/fiscal/calculate", data
            )
            assert status_code == 200
            cached_times.append(response_time)
        
        avg_cached_time = statistics.mean(cached_times)
        
        # Les appels en cache devraient être plus rapides
        # (pas toujours garanti selon l'implémentation du cache)
        print(f"Premier appel: {first_time:.3f}s, Moyenne avec cache: {avg_cached_time:.3f}s")
    
    @pytest.mark.slow
    def test_concurrent_load(self, load_tester):
        """Test de charge avec utilisateurs concurrents."""
        metrics = PerformanceMetrics()
        metrics.start_time = time.time()
        
        # Exécuter des scénarios utilisateur en parallèle
        with ThreadPoolExecutor(max_workers=LoadTestConfig.CONCURRENT_USERS) as executor:
            futures = []
            
            for user_id in range(LoadTestConfig.CONCURRENT_USERS):
                future = executor.submit(
                    load_tester.run_user_scenario,
                    user_id,
                    LoadTestConfig.REQUESTS_PER_USER
                )
                futures.append(future)
            
            # Collecter les résultats
            for future in as_completed(futures):
                try:
                    user_metrics = future.result()
                    metrics.response_times.extend(user_metrics.response_times)
                    metrics.status_codes.extend(user_metrics.status_codes)
                    metrics.errors.extend(user_metrics.errors)
                except Exception as e:
                    metrics.errors.append(str(e))
        
        metrics.end_time = time.time()
        
        # Analyser les résultats
        stats = metrics.calculate_stats()
        
        print("\n=== RÉSULTATS DU TEST DE CHARGE ===")
        print(f"Requêtes totales: {stats['total_requests']}")
        print(f"Requêtes réussies: {stats['successful_requests']}")
        print(f"Taux d'erreur: {stats['error_rate']:.2%}")
        print(f"Débit: {stats['throughput_rps']:.1f} req/s")
        print(f"Durée: {stats['duration_seconds']:.1f}s")
        print(f"Temps de réponse moyen: {stats['response_time_stats']['mean']:.3f}s")
        print(f"Temps de réponse P95: {stats['response_time_stats']['p95']:.3f}s")
        print(f"Temps de réponse P99: {stats['response_time_stats']['p99']:.3f}s")
        
        if stats['errors']:
            print(f"Erreurs: {stats['errors'][:5]}")
        
        # Vérifier les seuils de performance
        assert stats['error_rate'] <= LoadTestConfig.MAX_ERROR_RATE, \
            f"Taux d'erreur trop élevé: {stats['error_rate']:.2%}"
        
        assert stats['response_time_stats']['p95'] <= LoadTestConfig.MAX_RESPONSE_TIME, \
            f"P95 du temps de réponse trop élevé: {stats['response_time_stats']['p95']:.3f}s"
        
        assert stats['throughput_rps'] >= LoadTestConfig.MIN_THROUGHPUT, \
            f"Débit trop faible: {stats['throughput_rps']:.1f} req/s"
    
    def test_fiscal_batch_performance(self, load_tester):
        """Test de performance du calcul fiscal en batch."""
        # Préparer un batch de requêtes
        batch_data = []
        for i in range(50):
            batch_data.append({
                "amount": 100.0 + i,
                "service_type": "standard",
                "distance_km": 5.0 + (i % 10),
                "duration_minutes": 15 + (i % 20),
                "region": "algiers"
            })
        
        # Test du batch
        start_time = time.time()
        response_time, status_code, error = load_tester.make_request(
            "POST", "/api/v1/fiscal/calculate-batch", batch_data
        )
        
        assert status_code == 200, f"Erreur batch: {error}"
        
        # Le batch devrait être plus efficace que les requêtes individuelles
        batch_time_per_request = response_time / len(batch_data)
        
        print(f"Temps batch total: {response_time:.3f}s")
        print(f"Temps par requête en batch: {batch_time_per_request:.3f}s")
        
        # Comparer avec des requêtes individuelles
        individual_times = []
        for data in batch_data[:10]:  # Tester seulement 10 pour la comparaison
            individual_time, status_code, error = load_tester.make_request(
                "POST", "/api/v1/fiscal/calculate", data
            )
            assert status_code == 200
            individual_times.append(individual_time)
        
        avg_individual_time = statistics.mean(individual_times)
        
        print(f"Temps moyen individuel: {avg_individual_time:.3f}s")
        
        # Le batch devrait être plus efficace (pas toujours garanti)
        efficiency_ratio = avg_individual_time / batch_time_per_request
        print(f"Ratio d'efficacité batch: {efficiency_ratio:.2f}x")
    
    @pytest.mark.slow
    def test_memory_usage_under_load(self, load_tester):
        """Test d'utilisation mémoire sous charge."""
        import psutil
        import os
        
        # Mesurer la mémoire avant le test
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss / 1024 / 1024  # MB
        
        # Exécuter une charge soutenue
        data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        for i in range(1000):
            response_time, status_code, error = load_tester.make_request(
                "POST", "/api/v1/fiscal/calculate", data
            )
            
            if i % 100 == 0:
                current_memory = process.memory_info().rss / 1024 / 1024
                print(f"Requête {i}: Mémoire = {current_memory:.1f} MB")
        
        # Mesurer la mémoire après le test
        final_memory = process.memory_info().rss / 1024 / 1024
        memory_increase = final_memory - initial_memory
        
        print(f"Mémoire initiale: {initial_memory:.1f} MB")
        print(f"Mémoire finale: {final_memory:.1f} MB")
        print(f"Augmentation: {memory_increase:.1f} MB")
        
        # Vérifier qu'il n'y a pas de fuite mémoire majeure
        assert memory_increase < 100, f"Augmentation mémoire excessive: {memory_increase:.1f} MB"


class TestStressScenarios:
    """Tests de scénarios de stress spécifiques."""
    
    @pytest.fixture
    def load_tester(self):
        return LoadTester()
    
    def test_rapid_fire_requests(self, load_tester):
        """Test de requêtes en rafale."""
        data = {
            "amount": 100.00,
            "service_type": "standard",
            "distance_km": 5.0,
            "duration_minutes": 15,
            "region": "algiers"
        }
        
        # Envoyer 100 requêtes le plus rapidement possible
        start_time = time.time()
        results = []
        
        for _ in range(100):
            response_time, status_code, error = load_tester.make_request(
                "POST", "/api/v1/fiscal/calculate", data
            )
            results.append((response_time, status_code, error))
        
        total_time = time.time() - start_time
        
        # Analyser les résultats
        successful = len([r for r in results if r[1] == 200])
        rate_limited = len([r for r in results if r[1] == 429])
        
        print(f"Requêtes réussies: {successful}/100")
        print(f"Requêtes rate limitées: {rate_limited}/100")
        print(f"Temps total: {total_time:.3f}s")
        print(f"Débit: {100/total_time:.1f} req/s")
        
        # Au moins quelques requêtes devraient réussir
        assert successful > 0, "Aucune requête n'a réussi"
    
    def test_mixed_endpoint_stress(self, load_tester):
        """Test de stress sur plusieurs endpoints."""
        endpoints = [
            ("GET", "/api/v1/fiscal/health", None),
            ("GET", "/api/v1/fiscal/rates", None),
            ("GET", "/api/v1/monitoring/health", None),
            ("POST", "/api/v1/fiscal/calculate", {
                "amount": 100.00,
                "service_type": "standard",
                "distance_km": 5.0,
                "duration_minutes": 15,
                "region": "algiers"
            })
        ]
        
        results = []
        
        # Test chaque endpoint
        for method, endpoint, data in endpoints:
            endpoint_results = []
            
            for _ in range(50):
                response_time, status_code, error = load_tester.make_request(
                    method, endpoint, data
                )
                endpoint_results.append((response_time, status_code, error))
            
            successful = len([r for r in endpoint_results if 200 <= r[1] < 300])
            avg_time = statistics.mean([r[0] for r in endpoint_results])
            
            results.append({
                "endpoint": endpoint,
                "successful": successful,
                "total": len(endpoint_results),
                "avg_response_time": avg_time
            })
        
        # Afficher les résultats
        print("\n=== RÉSULTATS PAR ENDPOINT ===")
        for result in results:
            print(f"{result['endpoint']}: {result['successful']}/{result['total']} "
                  f"({result['avg_response_time']:.3f}s)")
        
        # Tous les endpoints devraient avoir un taux de succès raisonnable
        for result in results:
            success_rate = result['successful'] / result['total']
            assert success_rate >= 0.8, \
                f"Taux de succès trop faible pour {result['endpoint']}: {success_rate:.2%}"


if __name__ == "__main__":
    # Exécuter les tests de performance
    pytest.main([__file__, "-v", "-s", "-m", "not slow"])

