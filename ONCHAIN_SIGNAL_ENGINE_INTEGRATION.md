# OnChain Signal Engine - Integration Contract & Limitations

## Integration Contract

### API Contract

The OnChain Signal Engine provides a **strict output contract** that BotTrading systems can rely on for consistent signal consumption.

#### Core Output Format (MANDATORY)

```json
{
  "asset": "BTC",
  "timeframe": "1d", 
  "timestamp": "2024-01-15T12:00:00+00:00",
  "onchain_score": 72.45,          // [0, 100] - GUARANTEED
  "confidence": 0.8234,            // [0, 1] - GUARANTEED
  "bias": "positive",              // "positive" | "neutral" | "negative" - GUARANTEED
  "signals": { ... },              // Individual signal details
  "components": { ... },           // Component score breakdown
  "verification": { ... }          // Reproducibility and quality metrics
}
```

#### Field Guarantees

**GUARANTEED FIELDS** (Always Present):
- `asset`: String, asset identifier
- `timeframe`: String, one of ["1h", "4h", "1d"]
- `timestamp`: ISO 8601 UTC timestamp
- `onchain_score`: Number [0, 100], overall score
- `confidence`: Number [0, 1], overall confidence
- `bias`: String, one of ["positive", "neutral", "negative"]

**CONDITIONAL FIELDS** (May be absent on errors):
- `signals`: Object with individual signal results
- `components`: Object with component score breakdown
- `verification`: Object with quality and reproducibility data

#### Error Handling Contract

```json
{
  "asset": "BTC",
  "timeframe": "1d",
  "timestamp": "2024-01-15T12:00:00+00:00",
  "onchain_score": 50.0,           // Default neutral score on error
  "confidence": 0.0,               // Zero confidence on error
  "bias": "neutral",               // Neutral bias on error
  "error": {
    "code": "INSUFFICIENT_DATA",
    "message": "Insufficient historical data for baseline calculation",
    "severity": "high",
    "retry_after_minutes": 60
  }
}
```

### Integration Patterns

#### 1. Real-Time Signal Consumption

```python
from onchain_signal_engine import OnChainSignalEngine, SignalEngineConfig

# Initialize engine
config = SignalEngineConfig()
engine = OnChainSignalEngine(config)

# Generate signals
result = engine.generate_signals(asset="BTC", timeframe="1d")

# Consume signals in BotTrading system
if result.confidence >= 0.6:  # High confidence threshold
    trading_signal = {
        'source': 'onchain_signals',
        'score': float(result.onchain_score),
        'confidence': float(result.confidence),
        'bias': result.bias.value,
        'weight': 0.25  # 25% weight in overall trading decision
    }
    
    # Pass to trading decision engine
    bot_trading_system.add_signal_input(trading_signal)
else:
    # Low confidence - ignore or use with reduced weight
    pass
```

#### 2. Batch Processing Integration

```python
from datetime import datetime, timedelta

def process_historical_signals(start_date: datetime, end_date: datetime):
    """Process signals for historical analysis."""
    
    current_date = start_date
    signals_batch = []
    
    while current_date <= end_date:
        try:
            result = engine.generate_signals(
                asset="BTC", 
                timeframe="1d", 
                timestamp=current_date
            )
            
            signals_batch.append({
                'timestamp': current_date,
                'score': float(result.onchain_score),
                'confidence': float(result.confidence),
                'bias': result.bias.value,
                'active_signals': result.active_signals,
                'data_quality': float(result.data_completeness)
            })
            
        except Exception as e:
            # Handle errors gracefully
            signals_batch.append({
                'timestamp': current_date,
                'score': 50.0,  # Neutral
                'confidence': 0.0,
                'bias': 'neutral',
                'error': str(e)
            })
        
        current_date += timedelta(days=1)
    
    return signals_batch
```

#### 3. Signal Quality Filtering

```python
def filter_high_quality_signals(signal_result):
    """Filter signals based on quality criteria."""
    
    quality_criteria = {
        'min_confidence': 0.7,
        'min_data_completeness': 0.8,
        'max_conflicting_signals': 2,
        'min_active_signals': 2
    }
    
    passes_quality = (
        signal_result.confidence >= quality_criteria['min_confidence'] and
        signal_result.data_completeness >= quality_criteria['min_data_completeness'] and
        signal_result.conflicting_signals <= quality_criteria['max_conflicting_signals'] and
        signal_result.active_signals >= quality_criteria['min_active_signals']
    )
    
    return passes_quality
```

### Database Integration

#### Direct Database Access Pattern

```python
from sqlalchemy import create_engine, text

def get_latest_signals(asset: str, timeframe: str, limit: int = 10):
    """Get latest signals directly from database."""
    
    engine = create_engine(DATABASE_URL)
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT timestamp, onchain_score, confidence, bias,
                   network_health_score, capital_flow_score, smart_money_score,
                   active_signals, conflicting_signals, data_completeness
            FROM onchain_scores
            WHERE asset = :asset AND timeframe = :timeframe
            ORDER BY timestamp DESC
            LIMIT :limit
        """), {
            'asset': asset,
            'timeframe': timeframe,
            'limit': limit
        })
        
        return [dict(row._mapping) for row in result]
```

#### Signal Aggregation Pattern

```python
def get_signal_trend_analysis(asset: str, timeframe: str, days: int = 30):
    """Analyze signal trends over time."""
    
    with engine.connect() as conn:
        result = conn.execute(text("""
            SELECT 
                DATE_TRUNC('day', timestamp) as date,
                AVG(onchain_score) as avg_score,
                AVG(confidence) as avg_confidence,
                COUNT(CASE WHEN bias = 'positive' THEN 1 END) as positive_count,
                COUNT(CASE WHEN bias = 'negative' THEN 1 END) as negative_count,
                COUNT(*) as total_count
            FROM onchain_scores
            WHERE asset = :asset 
                AND timeframe = :timeframe
                AND timestamp >= NOW() - INTERVAL ':days days'
            GROUP BY DATE_TRUNC('day', timestamp)
            ORDER BY date DESC
        """), {
            'asset': asset,
            'timeframe': timeframe,
            'days': days
        })
        
        return [dict(row._mapping) for row in result]
```

## System Limitations

### 1. Data Dependencies

#### Input Data Requirements

**CRITICAL DEPENDENCIES**:
- Network Activity Time Series (`network_activity_ts`)
- UTXO Flow Time Series (`utxo_flow_ts`)
- Whale Detection Results (`whale_behavior_flags_ts`)
- Smart Wallet Classifications (`wallet_classification`)

**MINIMUM DATA REQUIREMENTS**:
- 30 days of historical data for baseline calculations
- Data completeness > 80% for reliable signals
- Maximum data age < 2 hours for real-time signals

#### Data Quality Impact

```python
def assess_data_quality_impact(data_completeness: float) -> str:
    """Assess impact of data quality on signal reliability."""
    
    if data_completeness >= 0.95:
        return "HIGH_RELIABILITY"
    elif data_completeness >= 0.80:
        return "MEDIUM_RELIABILITY"
    elif data_completeness >= 0.60:
        return "LOW_RELIABILITY"
    else:
        return "UNRELIABLE"
```

### 2. Computational Limitations

#### Performance Constraints

**Processing Capacity**:
- ~1000 signal calculations per hour per instance
- ~2 seconds average calculation time per timeframe
- Memory usage: ~512MB per 10K addresses analyzed
- Database storage: ~100GB/year for full signal history

**Scalability Bottlenecks**:
1. **Baseline Calculations**: O(n*log(n)) complexity
2. **Network Percentile Calculations**: Requires full dataset scan
3. **Multi-timeframe Consistency Checks**: Linear with timeframe count
4. **Database I/O**: Dominant factor for large historical analyses

#### Resource Requirements

```yaml
minimum_system_requirements:
  cpu_cores: 4
  memory_gb: 8
  storage_gb: 100
  database_connections: 10

recommended_system_requirements:
  cpu_cores: 8
  memory_gb: 16
  storage_gb: 500
  database_connections: 20
  
production_system_requirements:
  cpu_cores: 16
  memory_gb: 32
  storage_gb: 1000
  database_connections: 50
```

### 3. Signal Accuracy Limitations

#### Confidence Boundaries

**High Confidence (0.8-1.0)**:
- Reliable for automated trading decisions
- Strong signal agreement and historical stability
- Data completeness > 90%
- Minimum 20+ days of stable baseline data

**Medium Confidence (0.5-0.8)**:
- Suitable for human-reviewed decisions
- Some signal disagreement or data gaps
- Data completeness 70-90%
- Adequate baseline data available

**Low Confidence (0.0-0.5)**:
- Informational only, not for trading decisions
- Significant signal conflicts or data issues
- Data completeness < 70%
- Insufficient or unstable baseline data

#### Known Accuracy Limitations

```python
ACCURACY_LIMITATIONS = {
    'market_regime_changes': {
        'description': 'Signals may lag during rapid market regime transitions',
        'impact': 'Reduced accuracy for 1-3 days after major market shifts',
        'mitigation': 'Use shorter timeframes during volatile periods'
    },
    
    'low_activity_periods': {
        'description': 'Reduced signal reliability during low network activity',
        'impact': 'Higher confidence thresholds needed',
        'mitigation': 'Extend baseline periods during quiet markets'
    },
    
    'extreme_events': {
        'description': 'Black swan events may trigger false signals',
        'impact': 'Risk signals may have false positives',
        'mitigation': 'Manual review during extreme market conditions'
    },
    
    'data_source_failures': {
        'description': 'Upstream data issues affect signal quality',
        'impact': 'Degraded confidence and potential signal gaps',
        'mitigation': 'Automated fallback to cached baselines'
    }
}
```

### 4. Temporal Limitations

#### Signal Freshness

**Real-Time Constraints**:
- Signals reflect data up to last completed block
- ~10-60 minute lag from on-chain events to signal updates
- Baseline calculations updated every 6 hours
- Network statistics refreshed daily

**Historical Analysis Constraints**:
- Signals cannot be generated for dates without baseline data
- Minimum 30-day lookback required for first signal
- Historical recalculation may differ from original due to baseline updates

#### Time Zone and Timestamp Handling

```python
TEMPORAL_CONSTRAINTS = {
    'timezone': 'UTC_ONLY',
    'timestamp_precision': 'MINUTE',
    'minimum_interval': '1_HOUR',
    'maximum_lookback': '2_YEARS',
    'baseline_update_frequency': '6_HOURS',
    'signal_cache_ttl': '15_MINUTES'
}
```

### 5. Integration Limitations

#### API Rate Limits

```python
RATE_LIMITS = {
    'signal_generation': {
        'requests_per_minute': 60,
        'requests_per_hour': 1000,
        'concurrent_requests': 10
    },
    
    'database_queries': {
        'connections_per_instance': 20,
        'query_timeout_seconds': 30,
        'max_result_rows': 10000
    },
    
    'verification_tests': {
        'tests_per_hour': 100,
        'full_suite_per_day': 4
    }
}
```

#### Compatibility Requirements

**Database Compatibility**:
- PostgreSQL 12+ with TimescaleDB extension
- Minimum 100GB storage for production
- Connection pooling required for concurrent access

**Python Environment**:
- Python 3.10+
- Required packages: SQLAlchemy, Pandas, NumPy, Pydantic
- Memory: Minimum 4GB available for signal engine

**Network Requirements**:
- Stable database connectivity
- Low-latency access to data sources
- Backup connectivity for failover scenarios

### 6. Monitoring and Alerting Requirements

#### Critical Monitoring Points

```python
MONITORING_REQUIREMENTS = {
    'signal_quality': {
        'avg_confidence_threshold': 0.6,
        'data_completeness_threshold': 0.8,
        'calculation_success_rate': 0.95
    },
    
    'performance': {
        'max_calculation_time_ms': 5000,
        'max_memory_usage_mb': 1024,
        'max_database_response_ms': 1000
    },
    
    'system_health': {
        'database_connection_health': True,
        'cache_hit_rate_minimum': 0.7,
        'error_rate_maximum': 0.05
    }
}
```

#### Alert Conditions

```python
ALERT_CONDITIONS = {
    'CRITICAL': [
        'signal_engine_down',
        'database_connection_failed',
        'data_completeness < 0.5',
        'calculation_success_rate < 0.8'
    ],
    
    'WARNING': [
        'avg_confidence < 0.6',
        'calculation_time > 3000ms',
        'cache_hit_rate < 0.7',
        'conflicting_signals > 3'
    ],
    
    'INFO': [
        'new_signal_threshold_calculated',
        'baseline_cache_refreshed',
        'verification_test_completed'
    ]
}
```

## Best Practices for Integration

### 1. Signal Consumption Patterns

#### Recommended Usage

```python
def consume_onchain_signals():
    """Best practice signal consumption pattern."""
    
    # 1. Generate signals with error handling
    try:
        result = engine.generate_signals(asset="BTC", timeframe="1d")
    except Exception as e:
        logger.error(f"Signal generation failed: {e}")
        return None
    
    # 2. Validate signal quality
    if not filter_high_quality_signals(result):
        logger.warning("Low quality signals detected")
        return None
    
    # 3. Apply confidence-based weighting
    confidence_weight = min(1.0, float(result.confidence) / 0.8)  # Scale to 0.8 max
    
    # 4. Extract actionable information
    signal_data = {
        'source': 'onchain',
        'score': float(result.onchain_score),
        'bias': result.bias.value,
        'weight': confidence_weight * 0.25,  # 25% max weight in trading decision
        'active_signals': result.active_signals,
        'risk_penalty': float(result.risk_penalty)
    }
    
    return signal_data
```

#### Anti-Patterns to Avoid

```python
# ❌ DON'T: Use signals as sole trading decision
if onchain_score > 70:
    execute_buy_order()  # DANGEROUS

# ✅ DO: Use signals as one input among many
trading_inputs = {
    'onchain_signals': onchain_signal_data,
    'technical_analysis': ta_signal_data,
    'market_sentiment': sentiment_data,
    'risk_management': risk_data
}
final_decision = trading_decision_engine.process(trading_inputs)

# ❌ DON'T: Ignore confidence scores
use_signal = onchain_score > 60  # Ignores confidence

# ✅ DO: Weight by confidence
use_signal = onchain_score > 60 and confidence > 0.7

# ❌ DON'T: Use signals during system errors
if result.error:
    # Still use the signal anyway - WRONG
    pass

# ✅ DO: Handle errors gracefully
if result.error:
    logger.error(f"Signal error: {result.error}")
    fallback_to_cached_signals()
```

### 2. Performance Optimization

#### Caching Strategy

```python
def implement_signal_caching():
    """Implement efficient signal caching."""
    
    # 1. Cache frequently accessed signals
    cache_config = {
        'signal_results': {'ttl_minutes': 15, 'max_entries': 1000},
        'baselines': {'ttl_hours': 6, 'max_entries': 100},
        'network_stats': {'ttl_hours': 24, 'max_entries': 50}
    }
    
    # 2. Use database connection pooling
    engine = create_engine(
        DATABASE_URL,
        pool_size=20,
        max_overflow=30,
        pool_pre_ping=True
    )
    
    # 3. Batch signal requests when possible
    def get_signals_batch(timestamps: List[datetime]):
        results = []
        for timestamp in timestamps:
            result = engine.generate_signals(timestamp=timestamp)
            results.append(result)
        return results
```

### 3. Error Handling and Resilience

#### Robust Error Handling

```python
def robust_signal_processing():
    """Implement robust signal processing with fallbacks."""
    
    try:
        # Primary signal generation
        result = engine.generate_signals(asset="BTC", timeframe="1d")
        
        # Validate result quality
        if result.confidence < 0.3:
            raise ValueError("Signal confidence too low")
        
        return result
        
    except DatabaseConnectionError:
        # Fallback to cached signals
        logger.warning("Database connection failed, using cached signals")
        return get_cached_signals()
        
    except InsufficientDataError:
        # Fallback to longer timeframe
        logger.warning("Insufficient data for 1d, trying 4h")
        return engine.generate_signals(asset="BTC", timeframe="4h")
        
    except Exception as e:
        # Final fallback to neutral signal
        logger.error(f"Signal generation failed: {e}")
        return create_neutral_signal()

def create_neutral_signal():
    """Create neutral signal for error conditions."""
    return {
        'onchain_score': 50.0,
        'confidence': 0.0,
        'bias': 'neutral',
        'error': True,
        'timestamp': datetime.now()
    }
```

## Conclusion

The OnChain Signal Engine provides a robust, deterministic framework for generating structured Bitcoin on-chain signals. Key integration considerations:

### ✅ **Strengths**
- **Deterministic & Reproducible**: Same inputs always produce identical outputs
- **Comprehensive Verification**: Built-in testing and validation framework
- **Confidence-Weighted**: All signals include reliability metrics
- **Production-Ready**: Designed for 24/7 operation with proper error handling

### ⚠️ **Critical Requirements**
- **Data Quality**: Minimum 80% completeness for reliable signals
- **Confidence Thresholds**: Use >0.7 confidence for automated decisions
- **Error Handling**: Implement robust fallback mechanisms
- **Monitoring**: Continuous monitoring of signal quality and system health

### 🎯 **Recommended Usage**
- **Weight Signals Appropriately**: Maximum 25% weight in trading decisions
- **Combine with Other Inputs**: Never use as sole decision factor
- **Respect Confidence Scores**: Lower confidence = lower weight or human review
- **Monitor System Health**: Implement comprehensive alerting and monitoring

The system is designed to **inform, not decide** - providing high-quality on-chain intelligence as one input into sophisticated trading systems while maintaining complete transparency and auditability.