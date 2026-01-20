"""Prometheus metrics for OnChain API."""

from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import FastAPI, Response


class Metrics:
    """Prometheus metrics collection."""
    
    def __init__(self):
        # Request metrics
        self.request_count = Counter(
            'onchain_api_requests_total',
            'Total number of API requests',
            ['method', 'endpoint', 'status']
        )
        
        self.request_duration = Histogram(
            'onchain_api_request_duration_seconds',
            'Request duration in seconds',
            ['method', 'endpoint']
        )
        
        # Signal metrics
        self.signal_requests = Counter(
            'onchain_api_signal_requests_total',
            'Total number of signal requests',
            ['asset', 'timeframe', 'status']
        )
        
        self.signal_confidence = Histogram(
            'onchain_api_signal_confidence',
            'Signal confidence scores',
            ['asset', 'timeframe']
        )
        
        # Kill switch metrics
        self.kill_switch_activations = Counter(
            'onchain_api_kill_switch_activations_total',
            'Kill switch activation count',
            ['reason']
        )
        
        self.blocked_signals = Counter(
            'onchain_api_blocked_signals_total',
            'Blocked signal count',
            ['asset', 'timeframe', 'reason']
        )
        
        # System metrics
        self.active_connections = Gauge(
            'onchain_api_active_connections',
            'Number of active database connections'
        )
        
        self.cache_hits = Counter(
            'onchain_api_cache_hits_total',
            'Cache hit count',
            ['cache_type']
        )
        
        self.cache_misses = Counter(
            'onchain_api_cache_misses_total',
            'Cache miss count',
            ['cache_type']
        )


# Global metrics instance
metrics = Metrics()


def setup_metrics(app: FastAPI):
    """Setup metrics endpoint."""
    
    @app.get("/metrics")
    async def get_metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(),
            media_type="text/plain"
        )