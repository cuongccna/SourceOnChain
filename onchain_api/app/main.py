"""Main FastAPI application for OnChain Intelligence API."""

import logging
import time
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Dict, Any

from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import structlog

from onchain_api.config.settings import APISettings
from onchain_api.services.kill_switch import KillSwitchController, KillSwitchConfig, FallbackController
from onchain_api.utils.logging import setup_logging
from onchain_api.utils.metrics import setup_metrics, metrics
from onchain_api.utils.rate_limiter import RateLimiter
from onchain_api.app.routers import signal, health, audit, history, validation


# Global application state
app_state = {
    "settings": None,
    "db_engine": None,
    "db_session": None,
    "kill_switch": None,
    "fallback_controller": None,
    "rate_limiter": None,
    "startup_time": None
}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan management."""
    
    # Startup
    logger = structlog.get_logger(__name__)
    logger.info("Starting OnChain Intelligence API")
    
    try:
        # Initialize settings
        settings = APISettings()
        app_state["settings"] = settings
        
        # Setup logging
        setup_logging(settings)
        
        # Setup metrics
        if settings.enable_metrics:
            setup_metrics(app)
        
        # Initialize database
        engine = create_engine(
            settings.database_url,
            pool_size=settings.db_pool_size,
            max_overflow=settings.db_max_overflow,
            pool_timeout=settings.db_pool_timeout,
            echo=settings.debug
        )
        app_state["db_engine"] = engine
        app_state["db_session"] = sessionmaker(bind=engine)
        
        # Initialize kill switch
        kill_switch_config = KillSwitchConfig(**settings.get_kill_switch_config())
        app_state["kill_switch"] = KillSwitchController(kill_switch_config)
        
        # Initialize fallback controller
        app_state["fallback_controller"] = FallbackController()
        
        # Initialize rate limiter
        app_state["rate_limiter"] = RateLimiter(
            max_requests=settings.rate_limit_requests,
            window_seconds=settings.rate_limit_window
        )
        
        app_state["startup_time"] = datetime.now()
        
        logger.info("OnChain Intelligence API started successfully")
        
        yield
        
    except Exception as e:
        logger.error(f"Failed to start API: {e}")
        raise
    
    # Shutdown
    logger.info("Shutting down OnChain Intelligence API")
    
    if app_state["db_engine"]:
        app_state["db_engine"].dispose()
    
    logger.info("OnChain Intelligence API shutdown complete")


# Create FastAPI application
def create_app() -> FastAPI:
    """Create and configure FastAPI application."""
    
    settings = APISettings()
    
    app = FastAPI(
        title=settings.api_title,
        description=settings.api_description,
        version=settings.api_version,
        debug=settings.debug,
        lifespan=lifespan,
        docs_url="/docs" if settings.debug else None,
        redoc_url="/redoc" if settings.debug else None
    )
    
    # Add middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=settings.cors_methods,
        allow_headers=["*"],
    )
    
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=["*"]  # Configure appropriately for production
    )
    
    # Add custom middleware
    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        """Add processing time header."""
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response
    
    @app.middleware("http")
    async def logging_middleware(request: Request, call_next):
        """Request logging middleware."""
        logger = structlog.get_logger(__name__)
        
        start_time = time.time()
        
        # Log request
        logger.info("Request started",
                   method=request.method,
                   url=str(request.url),
                   client_ip=request.client.host if request.client else None)
        
        try:
            response = await call_next(request)
            
            # Log response
            process_time = time.time() - start_time
            logger.info("Request completed",
                       method=request.method,
                       url=str(request.url),
                       status_code=response.status_code,
                       process_time=process_time)
            
            # Update metrics
            if app_state.get("settings") and app_state["settings"].enable_metrics:
                metrics.request_count.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status=response.status_code
                ).inc()
                
                metrics.request_duration.labels(
                    method=request.method,
                    endpoint=request.url.path
                ).observe(process_time)
            
            return response
            
        except Exception as e:
            process_time = time.time() - start_time
            logger.error("Request failed",
                        method=request.method,
                        url=str(request.url),
                        error=str(e),
                        process_time=process_time)
            
            # Update error metrics
            if app_state.get("settings") and app_state["settings"].enable_metrics:
                metrics.request_count.labels(
                    method=request.method,
                    endpoint=request.url.path,
                    status=500
                ).inc()
            
            raise
    
    # Include routers
    app.include_router(signal.router, prefix="/api/v1/onchain", tags=["signals"])
    app.include_router(health.router, prefix="/api/v1/onchain", tags=["health"])
    app.include_router(audit.router, prefix="/api/v1/onchain", tags=["audit"])
    app.include_router(history.router, prefix="/api/v1/onchain", tags=["history"])
    app.include_router(validation.router, prefix="/api/v1/onchain", tags=["validation"])
    
    # Global exception handlers
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        """Handle HTTP exceptions."""
        logger = structlog.get_logger(__name__)
        logger.warning("HTTP exception",
                      status_code=exc.status_code,
                      detail=exc.detail,
                      url=str(request.url))
        
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": {
                    "code": f"HTTP_{exc.status_code}",
                    "message": exc.detail,
                    "timestamp": datetime.now().isoformat(),
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            }
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        """Handle general exceptions."""
        logger = structlog.get_logger(__name__)
        logger.error("Unhandled exception",
                    error=str(exc),
                    url=str(request.url),
                    exc_info=True)
        
        return JSONResponse(
            status_code=500,
            content={
                "error": {
                    "code": "INTERNAL_SERVER_ERROR",
                    "message": "An internal server error occurred",
                    "timestamp": datetime.now().isoformat(),
                    "request_id": getattr(request.state, "request_id", "unknown")
                }
            }
        )
    
    return app


# Security dependencies
security = HTTPBearer()


async def verify_api_key(credentials: HTTPAuthorizationCredentials = Depends(security)) -> str:
    """Verify API key authentication."""
    
    settings = app_state.get("settings")
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service not ready"
        )
    
    api_key = credentials.credentials
    
    if api_key not in settings.allowed_api_keys:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid API key"
        )
    
    return api_key


async def check_rate_limit(request: Request, api_key: str = Depends(verify_api_key)):
    """Check rate limiting."""
    
    rate_limiter = app_state.get("rate_limiter")
    if not rate_limiter:
        return  # Skip rate limiting if not initialized
    
    client_id = f"api_key:{api_key}"
    
    if not rate_limiter.is_allowed(client_id):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Rate limit exceeded",
            headers={"Retry-After": "3600"}
        )


# Dependency to get application components
def get_kill_switch() -> KillSwitchController:
    """Get kill switch controller."""
    kill_switch = app_state.get("kill_switch")
    if not kill_switch:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Kill switch not initialized"
        )
    return kill_switch


def get_fallback_controller() -> FallbackController:
    """Get fallback controller."""
    fallback = app_state.get("fallback_controller")
    if not fallback:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Fallback controller not initialized"
        )
    return fallback


def get_db_session():
    """Get database session."""
    session_factory = app_state.get("db_session")
    if not session_factory:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database not initialized"
        )
    return session_factory()


def get_settings() -> APISettings:
    """Get application settings."""
    settings = app_state.get("settings")
    if not settings:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Settings not initialized"
        )
    return settings


# Create the application instance
app = create_app()


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information."""
    settings = get_settings()
    startup_time = app_state.get("startup_time")
    
    return {
        "service": "OnChain Intelligence API",
        "version": settings.api_version,
        "status": "operational",
        "startup_time": startup_time.isoformat() if startup_time else None,
        "documentation": "/docs" if settings.debug else "Contact administrator",
        "endpoints": {
            "signal": "/api/v1/onchain/signal",
            "health": "/api/v1/onchain/health",
            "audit": "/api/v1/onchain/audit/{timestamp}",
            "history": "/api/v1/onchain/history",
            "validation": "/api/v1/onchain/validate"
        }
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = APISettings()
    
    uvicorn.run(
        "onchain_api.app.main:app",
        host=settings.host,
        port=settings.port,
        workers=settings.workers if not settings.debug else 1,
        reload=settings.debug,
        access_log=settings.access_log,
        log_level=settings.log_level.lower()
    )