"""Main OnChain Signal Engine implementation."""

import hashlib
import json
import time
from datetime import datetime, timedelta
from decimal import Decimal
from typing import Dict, List, Optional, Any, Tuple
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker
from concurrent.futures import ThreadPoolExecutor, as_completed

from onchain_signal_engine.models.config import SignalEngineConfig
from onchain_signal_engine.models.signal_data import (
    SignalResult, OnChainScore, ComponentScore, ConfidenceBreakdown,
    SignalCategory, SignalType, BiasType, SignalBaseline
)
from onchain_signal_engine.signals.network_health import NetworkHealthSignals
from onchain_signal_engine.signals.capital_flow import CapitalFlowSignals
from onchain_signal_engine.signals.smart_money import SmartMoneySignals
from onchain_signal_engine.signals.risk_signals import RiskSignals
from onchain_signal_engine.core.score_calculator import ScoreCalculator
from onchain_signal_engine.utils.data_fetcher import DataFetcher
from onchain_signal_engine.utils.baseline_calculator import BaselineCalculator

logger = structlog.get_logger(__name__)


class OnChainSignalEngine:
    """Main OnChain Signal Engine for generating structured signals and scores."""
    
    def __init__(self, config: SignalEngineConfig):
        self.config = config
        self.logger = logger.bind(component="signal_engine")
        
        # Validate configuration
        self.config.validate_configuration()
        
        # Database connection
        self.engine = create_engine(
            config.database_url,
            pool_size=config.db_pool_size,
            max_overflow=config.db_max_overflow
        )
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Initialize components
        self.data_fetcher = DataFetcher(config, self.SessionLocal)
        self.baseline_calculator = BaselineCalculator(config, self.SessionLocal)
        self.score_calculator = ScoreCalculator(config)
        
        # Initialize signal calculators
        self.network_health_signals = NetworkHealthSignals(config)
        self.capital_flow_signals = CapitalFlowSignals(config)
        self.smart_money_signals = SmartMoneySignals(config)
        self.risk_signals = RiskSignals(config)
        
        # Cache for baselines and results
        self.baseline_cache = {}
        self.signal_cache = {}
        
        self.logger.info("OnChain Signal Engine initialized",
                        timeframes=config.timeframes,
                        signals_configured=len(config.get_enabled_signals()))
    
    def generate_signals(self, asset: str = "BTC", timeframe: str = "1d",
                        timestamp: Optional[datetime] = None) -> OnChainScore:
        """
        Generate complete OnChain signals and score.
        
        Args:
            asset: Asset symbol (default: BTC)
            timeframe: Timeframe for analysis (1h, 4h, 1d)
            timestamp: Timestamp for analysis (default: now)
            
        Returns:
            OnChainScore with all signals and components
        """
        if timestamp is None:
            timestamp = datetime.now()
        
        start_time = time.time()
        
        self.logger.info("Starting signal generation",
                        asset=asset,
                        timeframe=timeframe,
                        timestamp=timestamp)
        
        try:
            # Step 1: Fetch input data
            input_data = self._fetch_input_data(asset, timeframe, timestamp)
            input_data_hash = self._calculate_input_hash(input_data)
            
            # Step 2: Calculate baselines
            baselines = self._get_or_calculate_baselines(asset, timeframe, timestamp)
            
            # Step 3: Calculate individual signals
            signal_results = self._calculate_all_signals(input_data, baselines, asset, timeframe, timestamp)
            
            # Step 4: Calculate component scores
            component_scores = self._calculate_component_scores(signal_results)
            
            # Step 5: Calculate overall score and confidence
            onchain_score, confidence_breakdown = self._calculate_overall_score_and_confidence(
                component_scores, signal_results
            )
            
            # Step 6: Determine bias
            bias = self._determine_bias(onchain_score, confidence_breakdown.overall_confidence)
            
            # Step 7: Create final result
            calculation_time_ms = int((time.time() - start_time) * 1000)
            
            result = OnChainScore(
                asset=asset,
                timeframe=timeframe,
                timestamp=timestamp,
                onchain_score=onchain_score,
                confidence=confidence_breakdown.overall_confidence,
                bias=bias,
                network_health_score=component_scores['network_health'],
                capital_flow_score=component_scores['capital_flow'],
                smart_money_score=component_scores['smart_money'],
                risk_penalty=component_scores.get('risk_penalty', Decimal('0.0')),
                signals=signal_results,
                confidence_breakdown=confidence_breakdown,
                input_data_hash=input_data_hash,
                calculation_hash=self._calculate_result_hash(onchain_score, signal_results),
                signal_count=len(signal_results),
                active_signals=sum(1 for s in signal_results.values() if s.value),
                conflicting_signals=self._count_conflicting_signals(signal_results),
                calculation_time_ms=calculation_time_ms,
                data_completeness=self._calculate_data_completeness(input_data)
            )
            
            # Step 8: Store results
            self._store_results(result)
            
            # Step 9: Cache results if enabled
            if self.config.enable_signal_caching:
                self._cache_results(result)
            
            self.logger.info("Signal generation completed",
                           asset=asset,
                           timeframe=timeframe,
                           onchain_score=float(onchain_score),
                           confidence=float(confidence_breakdown.overall_confidence),
                           bias=bias.value,
                           calculation_time_ms=calculation_time_ms)
            
            return result
            
        except Exception as e:
            self.logger.error("Signal generation failed",
                            asset=asset,
                            timeframe=timeframe,
                            error=str(e))
            raise
    
    def _fetch_input_data(self, asset: str, timeframe: str, timestamp: datetime) -> Dict[str, Any]:
        """Fetch all required input data for signal calculation."""
        
        self.logger.debug("Fetching input data",
                         asset=asset,
                         timeframe=timeframe,
                         timestamp=timestamp)
        
        # Calculate time window for data fetching
        lookback_days = self.config.baseline_lookback_periods
        start_time = timestamp - timedelta(days=lookback_days)
        
        input_data = {}
        
        # Fetch network activity features
        input_data['network_features'] = self.data_fetcher.get_network_activity_features(
            asset, timeframe, start_time, timestamp
        )
        
        # Fetch UTXO flow features
        input_data['utxo_features'] = self.data_fetcher.get_utxo_flow_features(
            asset, timeframe, start_time, timestamp
        )
        
        # Fetch whale detection results
        input_data['whale_features'] = self.data_fetcher.get_whale_detection_results(
            asset, timeframe, start_time, timestamp
        )
        
        # Fetch smart wallet classification results
        input_data['smart_wallet_features'] = self.data_fetcher.get_smart_wallet_features(
            asset, timeframe, start_time, timestamp
        )
        
        return input_data
    
    def _get_or_calculate_baselines(self, asset: str, timeframe: str, 
                                  timestamp: datetime) -> Dict[str, SignalBaseline]:
        """Get or calculate baseline statistics for all signals."""
        
        cache_key = f"{asset}_{timeframe}_{timestamp.date()}"
        
        # Check cache first
        if self.config.enable_baseline_caching and cache_key in self.baseline_cache:
            cached_baselines, cache_time = self.baseline_cache[cache_key]
            if datetime.now() - cache_time < timedelta(hours=self.config.baseline_cache_ttl_hours):
                return cached_baselines
        
        # Calculate baselines for all signals
        baselines = {}
        enabled_signals = self.config.get_enabled_signals()
        
        for signal_id in enabled_signals:
            baseline = self.baseline_calculator.calculate_baseline(
                signal_id, asset, timeframe, timestamp
            )
            baselines[signal_id] = baseline
        
        # Cache baselines
        if self.config.enable_baseline_caching:
            self.baseline_cache[cache_key] = (baselines, datetime.now())
        
        return baselines
    
    def _calculate_all_signals(self, input_data: Dict[str, Any], 
                             baselines: Dict[str, SignalBaseline],
                             asset: str, timeframe: str, timestamp: datetime) -> Dict[str, SignalResult]:
        """Calculate all individual signals."""
        
        signal_results = {}
        
        if self.config.enable_parallel_processing:
            # Parallel signal calculation
            with ThreadPoolExecutor(max_workers=self.config.max_workers) as executor:
                future_to_signal = {}
                
                # Submit all signal calculations
                signal_calculators = [
                    (self.network_health_signals, 'network_health'),
                    (self.capital_flow_signals, 'capital_flow'),
                    (self.smart_money_signals, 'smart_money'),
                    (self.risk_signals, 'risk')
                ]
                
                for calculator, category in signal_calculators:
                    future = executor.submit(
                        self._calculate_category_signals,
                        calculator, category, input_data, baselines, asset, timeframe, timestamp
                    )
                    future_to_signal[future] = category
                
                # Collect results
                for future in as_completed(future_to_signal):
                    category = future_to_signal[future]
                    try:
                        category_results = future.result()
                        signal_results.update(category_results)
                    except Exception as e:
                        self.logger.error("Signal calculation failed",
                                        category=category,
                                        error=str(e))
        else:
            # Sequential signal calculation
            signal_results.update(self._calculate_category_signals(
                self.network_health_signals, 'network_health', 
                input_data, baselines, asset, timeframe, timestamp
            ))
            signal_results.update(self._calculate_category_signals(
                self.capital_flow_signals, 'capital_flow',
                input_data, baselines, asset, timeframe, timestamp
            ))
            signal_results.update(self._calculate_category_signals(
                self.smart_money_signals, 'smart_money',
                input_data, baselines, asset, timeframe, timestamp
            ))
            signal_results.update(self._calculate_category_signals(
                self.risk_signals, 'risk',
                input_data, baselines, asset, timeframe, timestamp
            ))
        
        return signal_results
    
    def _calculate_category_signals(self, calculator, category: str, 
                                  input_data: Dict[str, Any],
                                  baselines: Dict[str, SignalBaseline],
                                  asset: str, timeframe: str, timestamp: datetime) -> Dict[str, SignalResult]:
        """Calculate signals for a specific category."""
        
        category_results = {}
        
        try:
            if category == 'network_health':
                # Network growth signal
                if 'network_growth_signal' in baselines:
                    result = calculator.calculate_network_growth_signal(
                        input_data['network_features'], baselines['network_growth_signal']
                    )
                    category_results['network_growth_signal'] = self._create_signal_result(
                        'network_growth_signal', 'Network Growth Signal', 
                        SignalCategory.NETWORK_HEALTH, result, asset, timeframe, timestamp
                    )
                
                # Network congestion signal
                if 'network_congestion_signal' in baselines:
                    result = calculator.calculate_network_congestion_signal(
                        input_data['network_features'], baselines['network_congestion_signal']
                    )
                    category_results['network_congestion_signal'] = self._create_signal_result(
                        'network_congestion_signal', 'Network Congestion Signal',
                        SignalCategory.NETWORK_HEALTH, result, asset, timeframe, timestamp
                    )
            
            elif category == 'capital_flow':
                # Net UTXO inflow signal
                if 'net_utxo_inflow_signal' in baselines:
                    result = calculator.calculate_net_utxo_inflow_signal(
                        input_data['utxo_features'], baselines['net_utxo_inflow_signal']
                    )
                    category_results['net_utxo_inflow_signal'] = self._create_signal_result(
                        'net_utxo_inflow_signal', 'Net UTXO Inflow Signal',
                        SignalCategory.CAPITAL_FLOW, result, asset, timeframe, timestamp
                    )
                
                # Whale flow dominance signal
                if 'whale_flow_dominance_signal' in baselines:
                    result = calculator.calculate_whale_flow_dominance_signal(
                        input_data['whale_features'], input_data['network_features'],
                        baselines['whale_flow_dominance_signal']
                    )
                    category_results['whale_flow_dominance_signal'] = self._create_signal_result(
                        'whale_flow_dominance_signal', 'Whale Flow Dominance Signal',
                        SignalCategory.CAPITAL_FLOW, result, asset, timeframe, timestamp
                    )
            
            elif category == 'smart_money':
                # Smart money accumulation signal
                if 'smart_money_accumulation_signal' in baselines:
                    result = calculator.calculate_smart_money_accumulation_signal(
                        input_data['smart_wallet_features'], baselines['smart_money_accumulation_signal']
                    )
                    category_results['smart_money_accumulation_signal'] = self._create_signal_result(
                        'smart_money_accumulation_signal', 'Smart Money Accumulation Signal',
                        SignalCategory.SMART_MONEY, result, asset, timeframe, timestamp
                    )
                
                # Smart money distribution signal
                if 'smart_money_distribution_signal' in baselines:
                    result = calculator.calculate_smart_money_distribution_signal(
                        input_data['smart_wallet_features'], baselines['smart_money_distribution_signal']
                    )
                    category_results['smart_money_distribution_signal'] = self._create_signal_result(
                        'smart_money_distribution_signal', 'Smart Money Distribution Signal',
                        SignalCategory.SMART_MONEY, result, asset, timeframe, timestamp
                    )
            
            elif category == 'risk':
                # Abnormal activity signal
                if 'abnormal_activity_signal' in baselines:
                    result = calculator.calculate_abnormal_activity_signal(
                        input_data['network_features'], baselines['abnormal_activity_signal']
                    )
                    category_results['abnormal_activity_signal'] = self._create_signal_result(
                        'abnormal_activity_signal', 'Abnormal Activity Signal',
                        SignalCategory.RISK, result, asset, timeframe, timestamp
                    )
                
                # Capital concentration signal
                if 'capital_concentration_signal' in baselines:
                    result = calculator.calculate_capital_concentration_signal(
                        input_data['whale_features'], input_data['network_features'],
                        baselines['capital_concentration_signal']
                    )
                    category_results['capital_concentration_signal'] = self._create_signal_result(
                        'capital_concentration_signal', 'Capital Concentration Signal',
                        SignalCategory.RISK, result, asset, timeframe, timestamp
                    )
        
        except Exception as e:
            self.logger.error("Category signal calculation failed",
                            category=category,
                            error=str(e))
        
        return category_results
    
    def _create_signal_result(self, signal_id: str, signal_name: str,
                            category: SignalCategory, calculation_result: Tuple[bool, float],
                            asset: str, timeframe: str, timestamp: datetime) -> SignalResult:
        """Create SignalResult from calculation output."""
        
        signal_value, confidence = calculation_result
        
        return SignalResult(
            signal_id=signal_id,
            signal_name=signal_name,
            signal_category=category,
            signal_type=SignalType.BINARY,
            value=signal_value,
            confidence=Decimal(str(confidence)),
            timestamp=timestamp,
            asset=asset,
            timeframe=timeframe,
            threshold_values=self.config.get_signal_threshold_config(signal_id),
            reproducible=True
        )
    
    def _calculate_component_scores(self, signal_results: Dict[str, SignalResult]) -> Dict[str, ComponentScore]:
        """Calculate component scores from individual signals."""
        
        return self.score_calculator.calculate_component_scores(signal_results)
    
    def _calculate_overall_score_and_confidence(self, component_scores: Dict[str, ComponentScore],
                                              signal_results: Dict[str, SignalResult]) -> Tuple[Decimal, ConfidenceBreakdown]:
        """Calculate overall OnChain score and confidence."""
        
        return self.score_calculator.calculate_overall_score_and_confidence(
            component_scores, signal_results
        )
    
    def _determine_bias(self, onchain_score: Decimal, confidence: Decimal) -> BiasType:
        """Determine overall bias classification."""
        
        thresholds = self.config.bias_thresholds
        
        if confidence > thresholds['confidence_threshold']:
            if onchain_score > thresholds['positive_score_threshold']:
                return BiasType.POSITIVE
            elif onchain_score < thresholds['negative_score_threshold']:
                return BiasType.NEGATIVE
        
        return BiasType.NEUTRAL
    
    def _count_conflicting_signals(self, signal_results: Dict[str, SignalResult]) -> int:
        """Count conflicting signals (simplified implementation)."""
        
        # Count bullish vs bearish signals
        bullish_signals = ['network_growth_signal', 'net_utxo_inflow_signal', 'smart_money_accumulation_signal']
        bearish_signals = ['network_congestion_signal', 'whale_flow_dominance_signal', 'smart_money_distribution_signal']
        
        bullish_active = sum(1 for s_id in bullish_signals if s_id in signal_results and signal_results[s_id].value)
        bearish_active = sum(1 for s_id in bearish_signals if s_id in signal_results and signal_results[s_id].value)
        
        # Conflict if both bullish and bearish signals are active
        return min(bullish_active, bearish_active)
    
    def _calculate_data_completeness(self, input_data: Dict[str, Any]) -> Decimal:
        """Calculate data completeness ratio."""
        
        total_expected_fields = 0
        total_available_fields = 0
        
        for data_category, data_dict in input_data.items():
            if isinstance(data_dict, dict):
                total_expected_fields += 10  # Assume 10 expected fields per category
                total_available_fields += len([v for v in data_dict.values() if v is not None])
        
        if total_expected_fields == 0:
            return Decimal('1.0')
        
        return Decimal(str(total_available_fields / total_expected_fields))
    
    def _calculate_input_hash(self, input_data: Dict[str, Any]) -> str:
        """Calculate hash of input data for reproducibility."""
        
        # Normalize data for consistent hashing
        normalized_data = json.dumps(input_data, sort_keys=True, default=str)
        return hashlib.sha256(normalized_data.encode()).hexdigest()
    
    def _calculate_result_hash(self, onchain_score: Decimal, 
                             signal_results: Dict[str, SignalResult]) -> str:
        """Calculate hash of calculation results."""
        
        result_data = {
            'onchain_score': float(onchain_score),
            'signals': {k: {'value': v.value, 'confidence': float(v.confidence)} 
                       for k, v in signal_results.items()}
        }
        
        normalized_data = json.dumps(result_data, sort_keys=True)
        return hashlib.sha256(normalized_data.encode()).hexdigest()
    
    def _store_results(self, result: OnChainScore):
        """Store results in database."""
        
        try:
            with self.SessionLocal() as session:
                # Store individual signal results
                for signal_result in result.signals.values():
                    session.execute(text("""
                        INSERT INTO signal_calculations (
                            asset, timeframe, timestamp, signal_id, signal_value, 
                            signal_confidence, input_data_hash, threshold_values, 
                            baseline_metrics, calculation_time_ms, data_quality_score
                        ) VALUES (
                            :asset, :timeframe, :timestamp, :signal_id, :signal_value,
                            :signal_confidence, :input_data_hash, :threshold_values,
                            :baseline_metrics, :calculation_time_ms, :data_quality_score
                        ) ON CONFLICT (asset, timeframe, timestamp, signal_id) 
                        DO UPDATE SET
                            signal_value = EXCLUDED.signal_value,
                            signal_confidence = EXCLUDED.signal_confidence,
                            input_data_hash = EXCLUDED.input_data_hash
                    """), {
                        'asset': signal_result.asset,
                        'timeframe': signal_result.timeframe,
                        'timestamp': signal_result.timestamp,
                        'signal_id': signal_result.signal_id,
                        'signal_value': signal_result.value,
                        'signal_confidence': float(signal_result.confidence),
                        'input_data_hash': signal_result.input_data_hash,
                        'threshold_values': json.dumps(signal_result.threshold_values),
                        'baseline_metrics': json.dumps(signal_result.baseline_metrics),
                        'calculation_time_ms': signal_result.calculation_time_ms,
                        'data_quality_score': float(signal_result.data_quality_score)
                    })
                
                # Store OnChain score
                session.execute(text("""
                    INSERT INTO onchain_scores (
                        asset, timeframe, timestamp, onchain_score, confidence, bias,
                        network_health_score, capital_flow_score, smart_money_score, risk_penalty,
                        network_health_confidence, capital_flow_confidence, smart_money_confidence,
                        signal_agreement_confidence, historical_stability_confidence,
                        data_quality_confidence, statistical_significance_confidence,
                        input_data_hash, calculation_hash, signal_count, active_signals,
                        conflicting_signals, calculation_time_ms, data_completeness
                    ) VALUES (
                        :asset, :timeframe, :timestamp, :onchain_score, :confidence, :bias,
                        :network_health_score, :capital_flow_score, :smart_money_score, :risk_penalty,
                        :network_health_confidence, :capital_flow_confidence, :smart_money_confidence,
                        :signal_agreement_confidence, :historical_stability_confidence,
                        :data_quality_confidence, :statistical_significance_confidence,
                        :input_data_hash, :calculation_hash, :signal_count, :active_signals,
                        :conflicting_signals, :calculation_time_ms, :data_completeness
                    ) ON CONFLICT (asset, timeframe, timestamp)
                    DO UPDATE SET
                        onchain_score = EXCLUDED.onchain_score,
                        confidence = EXCLUDED.confidence,
                        bias = EXCLUDED.bias
                """), {
                    'asset': result.asset,
                    'timeframe': result.timeframe,
                    'timestamp': result.timestamp,
                    'onchain_score': float(result.onchain_score),
                    'confidence': float(result.confidence),
                    'bias': result.bias.value,
                    'network_health_score': float(result.network_health_score.score),
                    'capital_flow_score': float(result.capital_flow_score.score),
                    'smart_money_score': float(result.smart_money_score.score),
                    'risk_penalty': float(result.risk_penalty),
                    'network_health_confidence': float(result.network_health_score.confidence),
                    'capital_flow_confidence': float(result.capital_flow_score.confidence),
                    'smart_money_confidence': float(result.smart_money_score.confidence),
                    'signal_agreement_confidence': float(result.confidence_breakdown.signal_agreement),
                    'historical_stability_confidence': float(result.confidence_breakdown.historical_stability),
                    'data_quality_confidence': float(result.confidence_breakdown.data_quality),
                    'statistical_significance_confidence': float(result.confidence_breakdown.statistical_significance),
                    'input_data_hash': result.input_data_hash,
                    'calculation_hash': result.calculation_hash,
                    'signal_count': result.signal_count,
                    'active_signals': result.active_signals,
                    'conflicting_signals': result.conflicting_signals,
                    'calculation_time_ms': result.calculation_time_ms,
                    'data_completeness': float(result.data_completeness)
                })
                
                session.commit()
                
        except Exception as e:
            self.logger.error("Failed to store results", error=str(e))
            raise
    
    def _cache_results(self, result: OnChainScore):
        """Cache results for faster retrieval."""
        
        cache_key = f"{result.asset}_{result.timeframe}_{result.timestamp}"
        self.signal_cache[cache_key] = (result, datetime.now())
        
        # Cleanup old cache entries
        if len(self.signal_cache) > 1000:
            oldest_key = min(self.signal_cache.keys(),
                           key=lambda k: self.signal_cache[k][1])
            del self.signal_cache[oldest_key]
    
    def close(self):
        """Close database connections and cleanup resources."""
        self.engine.dispose()
        self.logger.info("OnChain Signal Engine closed")