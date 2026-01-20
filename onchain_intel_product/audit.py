"""Audit and replay mechanism for OnChain Intelligence Data Product."""

import json
import hashlib
from datetime import datetime
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
import structlog

from config import ProductConfig


logger = structlog.get_logger(__name__)


class AuditController:
    """
    Audit controller for ensuring reproducibility and compliance.
    
    Provides mechanisms to:
    - Record calculation inputs and outputs
    - Generate reproducible hashes
    - Enable replay of historical calculations
    - Verify calculation integrity
    """
    
    def __init__(self, config: ProductConfig):
        self.config = config
        self.logger = logger.bind(component="audit")
    
    def record_calculation(self, 
                          db_session: Session,
                          asset: str,
                          timeframe: str,
                          timestamp: datetime,
                          input_data: Dict[str, Any],
                          output_data: Dict[str, Any]) -> str:
        """
        Record calculation for audit trail.
        
        Returns calculation hash for future reference.
        """
        
        # Generate input data hash
        input_hash = self._generate_input_hash(input_data)
        
        # Generate calculation hash
        calculation_data = {
            "asset": asset,
            "timeframe": timeframe,
            "timestamp": timestamp.isoformat(),
            "input_hash": input_hash,
            "config": self._get_config_snapshot(),
            "output": output_data
        }
        calculation_hash = self._generate_calculation_hash(calculation_data)
        
        # Store audit record
        try:
            db_session.execute(text("""
                INSERT INTO audit_calculations 
                (calculation_hash, asset, timeframe, timestamp, 
                 input_data_hash, config_hash, output_data, created_at)
                VALUES (:calc_hash, :asset, :timeframe, :timestamp,
                        :input_hash, :config_hash, :output_data, :created_at)
                ON CONFLICT (calculation_hash) DO NOTHING
            """), {
                "calc_hash": calculation_hash,
                "asset": asset,
                "timeframe": timeframe,
                "timestamp": timestamp,
                "input_hash": input_hash,
                "config_hash": self._get_config_hash(),
                "output_data": json.dumps(output_data),
                "created_at": datetime.utcnow()
            })
            db_session.commit()
            
            self.logger.info("Calculation recorded for audit",
                           calculation_hash=calculation_hash,
                           asset=asset,
                           timeframe=timeframe)
            
        except Exception as e:
            self.logger.error("Failed to record calculation", error=str(e))
            db_session.rollback()
        
        return calculation_hash
    
    def get_audit_record(self, 
                        db_session: Session,
                        asset: str,
                        timeframe: str,
                        timestamp: datetime) -> Optional[Dict[str, Any]]:
        """
        Retrieve audit record for specific calculation.
        """
        
        try:
            result = db_session.execute(text("""
                SELECT calculation_hash, input_data_hash, config_hash, 
                       output_data, created_at
                FROM audit_calculations
                WHERE asset = :asset AND timeframe = :timeframe 
                AND timestamp = :timestamp
                ORDER BY created_at DESC
                LIMIT 1
            """), {
                "asset": asset,
                "timeframe": timeframe,
                "timestamp": timestamp
            }).fetchone()
            
            if result:
                return {
                    "calculation_hash": result.calculation_hash,
                    "input_data_hash": result.input_data_hash,
                    "config_hash": result.config_hash,
                    "output_data": json.loads(result.output_data),
                    "created_at": result.created_at
                }
            
            return None
            
        except Exception as e:
            self.logger.error("Failed to retrieve audit record", error=str(e))
            return None
    
    def verify_calculation_integrity(self,
                                   db_session: Session,
                                   calculation_hash: str) -> bool:
        """
        Verify calculation integrity by recomputing hashes.
        """
        
        try:
            result = db_session.execute(text("""
                SELECT asset, timeframe, timestamp, input_data_hash, 
                       config_hash, output_data
                FROM audit_calculations
                WHERE calculation_hash = :calc_hash
            """), {"calc_hash": calculation_hash}).fetchone()
            
            if not result:
                return False
            
            # Reconstruct calculation data
            calculation_data = {
                "asset": result.asset,
                "timeframe": result.timeframe,
                "timestamp": result.timestamp.isoformat(),
                "input_hash": result.input_data_hash,
                "config": json.loads(result.config_hash),  # Assuming config stored as JSON
                "output": json.loads(result.output_data)
            }
            
            # Verify hash
            computed_hash = self._generate_calculation_hash(calculation_data)
            integrity_verified = computed_hash == calculation_hash
            
            self.logger.info("Calculation integrity verification",
                           calculation_hash=calculation_hash,
                           verified=integrity_verified)
            
            return integrity_verified
            
        except Exception as e:
            self.logger.error("Failed to verify calculation integrity", error=str(e))
            return False
    
    def replay_calculation(self,
                          db_session: Session,
                          asset: str,
                          timeframe: str,
                          timestamp: datetime) -> Optional[Dict[str, Any]]:
        """
        Replay historical calculation using stored inputs and config.
        
        This would require re-running the calculation engine with historical data.
        Implementation depends on the specific calculation engine architecture.
        """
        
        audit_record = self.get_audit_record(db_session, asset, timeframe, timestamp)
        if not audit_record:
            return None
        
        # In a full implementation, this would:
        # 1. Retrieve historical input data using input_data_hash
        # 2. Restore configuration using config_hash
        # 3. Re-run calculation engine
        # 4. Compare output with stored output_data
        
        self.logger.info("Calculation replay requested",
                        asset=asset,
                        timeframe=timeframe,
                        timestamp=timestamp,
                        note="Replay implementation requires calculation engine integration")
        
        return audit_record
    
    def _generate_input_hash(self, input_data: Dict[str, Any]) -> str:
        """Generate deterministic hash of input data."""
        
        # Normalize input data for consistent hashing
        normalized_data = self._normalize_for_hash(input_data)
        data_string = json.dumps(normalized_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
    
    def _generate_calculation_hash(self, calculation_data: Dict[str, Any]) -> str:
        """Generate deterministic hash of complete calculation."""
        
        normalized_data = self._normalize_for_hash(calculation_data)
        data_string = json.dumps(normalized_data, sort_keys=True, separators=(',', ':'))
        return hashlib.sha256(data_string.encode('utf-8')).hexdigest()
    
    def _get_config_snapshot(self) -> Dict[str, Any]:
        """Get current configuration snapshot."""
        
        return {
            "min_confidence": self.config.min_confidence,
            "stability_threshold": self.config.stability_threshold,
            "completeness_threshold": self.config.completeness_threshold,
            "max_data_age_hours": self.config.max_data_age_hours,
            "max_conflicting_signals": self.config.max_conflicting_signals,
            "normal_weight": self.config.normal_weight,
            "degraded_weight": self.config.degraded_weight
        }
    
    def _get_config_hash(self) -> str:
        """Get hash of current configuration."""
        
        config_data = self._get_config_snapshot()
        return self._generate_input_hash(config_data)
    
    def _normalize_for_hash(self, data: Any) -> Any:
        """
        Normalize data structure for consistent hashing.
        
        Handles floating point precision, datetime formatting, etc.
        """
        
        if isinstance(data, dict):
            return {k: self._normalize_for_hash(v) for k, v in sorted(data.items())}
        elif isinstance(data, list):
            return [self._normalize_for_hash(item) for item in data]
        elif isinstance(data, float):
            # Round to 8 decimal places for consistency
            return round(data, 8)
        elif isinstance(data, datetime):
            return data.isoformat()
        else:
            return data