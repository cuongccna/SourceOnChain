"""Configuration for OnChain Intelligence Data Product."""

import os
from typing import Optional
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings


class ProductConfig(BaseSettings):
    """Production configuration for OnChain Intelligence Data Product."""
    
    # Database configuration
    database_url: str = Field(
        default="postgresql://onchain_user:onchain_pass@localhost:5432/bitcoin_onchain_signals",
        description="Database connection URL"
    )
    
    # Kill switch thresholds
    min_confidence: float = Field(default=0.60, ge=0.0, le=1.0, description="Minimum confidence threshold")
    stability_threshold: float = Field(default=0.70, ge=0.0, le=1.0, description="Minimum stability score")
    completeness_threshold: float = Field(default=0.80, ge=0.0, le=1.0, description="Minimum data completeness")
    
    # Data quality thresholds
    max_data_age_hours: float = Field(default=2.0, gt=0, description="Maximum data age in hours")
    max_conflicting_signals: int = Field(default=2, ge=0, description="Maximum conflicting signals allowed")
    
    # Usage policy weights
    normal_weight: float = Field(default=1.0, ge=0.0, le=1.0, description="Normal recommended weight")
    degraded_weight: float = Field(default=0.3, ge=0.0, le=1.0, description="Degraded recommended weight")
    
    # Logging configuration
    log_level: str = Field(default="INFO", description="Logging level")
    
    class Config:
        env_file = ".env"
        env_prefix = "ONCHAIN_"