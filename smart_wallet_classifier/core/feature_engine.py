"""Feature engineering engine for smart wallet classification."""

from datetime import datetime, timedelta
from decimal import Decimal
from typing import List, Dict, Optional, Tuple, Any
import numpy as np
import structlog
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from smart_wallet_classifier.models.config import SmartWalletConfig
from smart_wallet_classifier.models.wallet_data import WalletBehaviorFeatures, NetworkBehaviorStats

logger = structlog.get_logger(__name__)


class FeatureEngine:
    """Extracts behavioral features from on-chain wallet data."""
    
    def __init__(self, config: SmartWalletConfig):
        self.config = config
        self.logger = logger.bind(component="feature_engine")
        
        # Database connection
        self.engine = create_engine(config.database_url)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
        # Feature cache
        self.feature_cache = {}
        
        self.logger.info("Feature engine initialized")
    
    def extract_features(self, address: str, timeframe: str, 
                        end_timestamp: Optional[datetime] = None) -> Optional[WalletBehaviorFeatures]:
        """
        Extract behavioral features for a wallet address.
        
        Args:
            address: Bitcoin address
            timeframe: Analysis timeframe ('30d', '90d', '1y')
            end_timestamp: End of analysis period (default: now)
            
        Returns:
            WalletBehaviorFeatures object or None if insufficient data
        """
        if end_timestamp is None:
            end_timestamp = datetime.now()
        
        self.logger.debug("Extracting features",
                         address=address,
                         timeframe=timeframe,
                         end_timestamp=end_timestamp)
        
        try:
            # Check cache first
            if self.config.enable_feature_caching:
                cached_features = self._get_cached_features(address, timeframe, end_timestamp)
                if cached_features:
                    return cached_features
            
            # Get timeframe boundaries
            start_timestamp = self._get_timeframe_start(end_timestamp, timeframe)
            
            # Get wallet transaction data
            wallet_data = self._get_wallet_data(address, start_timestamp, end_timestamp)
            
            if not wallet_data or len(wallet_data['transactions']) < self.config.min_transaction_count:
                self.logger.warning("Insufficient transaction data",
                                  address=address,
                                  tx_count=len(wallet_data['transactions']) if wallet_data else 0)
                return None
            
            # Calculate features
            features = self._calculate_all_features(address, timeframe, end_timestamp, wallet_data)
            
            # Cache features
            if self.config.enable_feature_caching:
                self._cache_features(features)
            
            self.logger.info("Features extracted successfully",
                           address=address,
                           timeframe=timeframe,
                           tx_count=features.transaction_count,
                           win_rate=float(features.win_rate))
            
            return features
            
        except Exception as e:
            self.logger.error("Failed to extract features",
                            address=address,
                            timeframe=timeframe,
                            error=str(e))
            return None
    
    def _get_wallet_data(self, address: str, start_time: datetime, 
                        end_time: datetime) -> Optional[Dict[str, Any]]:
        """Get comprehensive wallet data from database."""
        
        with self.SessionLocal() as session:
            # Get transactions involving this address
            tx_result = session.execute(text("""
                WITH address_transactions AS (
                    SELECT DISTINCT t.tx_hash, t.block_height, t.block_time, t.total_input_btc, 
                           t.total_output_btc, t.fee_btc, t.is_coinbase
                    FROM transactions t
                    JOIN utxos u ON t.tx_hash = u.tx_hash
                    WHERE u.address = :address
                        AND t.block_time >= :start_time
                        AND t.block_time <= :end_time
                )
                SELECT * FROM address_transactions
                ORDER BY block_time
            """), {
                "address": address,
                "start_time": start_time,
                "end_time": end_time
            }).fetchall()
            
            transactions = [dict(row._mapping) for row in tx_result]
            
            if not transactions:
                return None
            
            # Get UTXOs for this address
            utxo_result = session.execute(text("""
                SELECT u.tx_hash, u.vout_index, u.value_btc, u.is_spent, 
                       u.spent_tx_hash, u.spent_at, t.block_time as created_at
                FROM utxos u
                JOIN transactions t ON u.tx_hash = t.tx_hash
                WHERE u.address = :address
                    AND t.block_time >= :start_time
                    AND t.block_time <= :end_time
                ORDER BY t.block_time
            """), {
                "address": address,
                "start_time": start_time,
                "end_time": end_time
            }).fetchall()
            
            utxos = [dict(row._mapping) for row in utxo_result]
            
            # Get whale activity data for timing analysis
            whale_result = session.execute(text("""
                SELECT timestamp, whale_tx_count, whale_tx_volume_btc, 
                       accumulation_flag, distribution_flag, activity_spike_flag
                FROM whale_behavior_flags_ts
                WHERE asset = 'BTC'
                    AND timeframe = '1d'
                    AND timestamp >= :start_time
                    AND timestamp <= :end_time
                ORDER BY timestamp
            """), {
                "start_time": start_time,
                "end_time": end_time
            }).fetchall()
            
            whale_activity = [dict(row._mapping) for row in whale_result]
            
            return {
                'transactions': transactions,
                'utxos': utxos,
                'whale_activity': whale_activity
            }
    
    def _calculate_all_features(self, address: str, timeframe: str, 
                               end_timestamp: datetime, 
                               wallet_data: Dict[str, Any]) -> WalletBehaviorFeatures:
        """Calculate all behavioral features."""
        
        transactions = wallet_data['transactions']
        utxos = wallet_data['utxos']
        whale_activity = wallet_data['whale_activity']
        
        # Basic metrics
        transaction_count = len(transactions)
        active_days = (end_timestamp - datetime.fromisoformat(str(transactions[0]['block_time']))).days
        first_tx_date = transactions[0]['block_time']
        last_tx_date = transactions[-1]['block_time']
        
        # 1. Holding Behavior Features
        holding_features = self._calculate_holding_features(utxos)
        
        # 2. Capital Efficiency Features
        pnl_features = self._calculate_pnl_features(transactions, utxos)
        
        # 3. Timing Quality Features
        timing_features = self._calculate_timing_features(transactions, whale_activity)
        
        # 4. Activity Discipline Features
        discipline_features = self._calculate_discipline_features(transactions)
        
        # 5. Additional Behavioral Metrics
        behavioral_features = self._calculate_behavioral_metrics(transactions, utxos)
        
        # 6. Network-relative percentiles (would be calculated against network stats)
        percentile_features = self._calculate_percentile_features(
            holding_features, pnl_features, discipline_features
        )
        
        # Combine all features
        features = WalletBehaviorFeatures(
            address=address,
            timeframe=timeframe,
            calculation_timestamp=end_timestamp,
            
            # Basic metrics
            transaction_count=transaction_count,
            active_days=active_days,
            first_tx_date=first_tx_date,
            last_tx_date=last_tx_date,
            
            # Holding behavior
            avg_utxo_holding_time_days=holding_features['avg_holding_time'],
            holding_time_p25_days=holding_features['p25_holding_time'],
            holding_time_p50_days=holding_features['p50_holding_time'],
            holding_time_p75_days=holding_features['p75_holding_time'],
            holding_time_p90_days=holding_features['p90_holding_time'],
            dormancy_activation_rate=holding_features['dormancy_activation_rate'],
            
            # Capital efficiency
            realized_profit_btc=pnl_features['realized_profit'],
            realized_loss_btc=pnl_features['realized_loss'],
            net_realized_pnl_btc=pnl_features['net_pnl'],
            profit_loss_ratio=pnl_features['profit_loss_ratio'],
            win_rate=pnl_features['win_rate'],
            profitable_spends=pnl_features['profitable_spends'],
            total_spends=pnl_features['total_spends'],
            
            # Timing quality
            accumulation_before_whale_spike_rate=timing_features['accumulation_before_spike_rate'],
            distribution_after_whale_spike_rate=timing_features['distribution_after_spike_rate'],
            accumulation_periods_count=timing_features['accumulation_periods'],
            distribution_periods_count=timing_features['distribution_periods'],
            successful_accumulations=timing_features['successful_accumulations'],
            successful_distributions=timing_features['successful_distributions'],
            
            # Activity discipline
            tx_frequency_per_day=discipline_features['tx_frequency_per_day'],
            tx_frequency_std=discipline_features['tx_frequency_std'],
            burst_vs_consistency_score=discipline_features['consistency_score'],
            overtrading_penalty=discipline_features['overtrading_penalty'],
            avg_tx_interval_hours=discipline_features['avg_interval_hours'],
            
            # Percentiles
            avg_holding_time_percentile=percentile_features['holding_time_percentile'],
            win_rate_percentile=percentile_features['win_rate_percentile'],
            profit_loss_ratio_percentile=percentile_features['pnl_ratio_percentile'],
            net_pnl_percentile=percentile_features['net_pnl_percentile'],
            tx_frequency_std_percentile=percentile_features['frequency_std_percentile'],
            
            # Additional behavioral metrics
            round_number_tx_ratio=behavioral_features['round_number_ratio'],
            coinbase_tx_ratio=behavioral_features['coinbase_ratio'],
            avg_inputs_per_tx=behavioral_features['avg_inputs_per_tx'],
            avg_outputs_per_tx=behavioral_features['avg_outputs_per_tx'],
            avg_tx_value_btc=behavioral_features['avg_tx_value']
        )
        
        return features
    
    def _calculate_holding_features(self, utxos: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        """Calculate holding behavior features."""
        
        spent_utxos = [u for u in utxos if u['is_spent'] and u['spent_at']]
        
        if not spent_utxos:
            return {
                'avg_holding_time': Decimal('0'),
                'p25_holding_time': Decimal('0'),
                'p50_holding_time': Decimal('0'),
                'p75_holding_time': Decimal('0'),
                'p90_holding_time': Decimal('0'),
                'dormancy_activation_rate': Decimal('0')
            }
        
        # Calculate holding times in days
        holding_times = []
        for utxo in spent_utxos:
            created_at = utxo['created_at']
            spent_at = utxo['spent_at']
            holding_time = (spent_at - created_at).total_seconds() / 86400  # Convert to days
            holding_times.append(holding_time)
        
        # Calculate statistics
        avg_holding_time = Decimal(str(np.mean(holding_times)))
        
        percentiles = np.percentile(holding_times, [25, 50, 75, 90])
        p25_holding_time = Decimal(str(percentiles[0]))
        p50_holding_time = Decimal(str(percentiles[1]))
        p75_holding_time = Decimal(str(percentiles[2]))
        p90_holding_time = Decimal(str(percentiles[3]))
        
        # Calculate dormancy activation rate
        dormancy_threshold_days = self.config.dormancy_threshold_days
        dormant_utxos = [u for u in utxos if (
            (u['spent_at'] or datetime.now()) - u['created_at']
        ).days > dormancy_threshold_days]
        
        if dormant_utxos:
            activated_dormant = [u for u in dormant_utxos if u['is_spent']]
            dormancy_activation_rate = Decimal(str(len(activated_dormant) / len(dormant_utxos)))
        else:
            dormancy_activation_rate = Decimal('0')
        
        return {
            'avg_holding_time': avg_holding_time,
            'p25_holding_time': p25_holding_time,
            'p50_holding_time': p50_holding_time,
            'p75_holding_time': p75_holding_time,
            'p90_holding_time': p90_holding_time,
            'dormancy_activation_rate': dormancy_activation_rate
        }
    
    def _calculate_pnl_features(self, transactions: List[Dict[str, Any]], 
                               utxos: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        """Calculate capital efficiency (PnL proxy) features."""
        
        # Simplified PnL calculation using holding time as proxy
        # In practice, this would use more sophisticated cost basis accounting
        
        spent_utxos = [u for u in utxos if u['is_spent'] and u['spent_at']]
        
        if not spent_utxos:
            return {
                'realized_profit': Decimal('0'),
                'realized_loss': Decimal('0'),
                'net_pnl': Decimal('0'),
                'profit_loss_ratio': Decimal('0'),
                'win_rate': Decimal('0'),
                'profitable_spends': 0,
                'total_spends': 0
            }
        
        # Get network median holding time (simplified - would query from network stats)
        network_median_holding_days = 30  # Placeholder
        
        realized_profit = Decimal('0')
        realized_loss = Decimal('0')
        profitable_spends = 0
        
        for utxo in spent_utxos:
            holding_days = (utxo['spent_at'] - utxo['created_at']).days
            utxo_value = Decimal(str(utxo['value_btc']))
            
            # Profit/loss based on holding time relative to network median
            if holding_days > network_median_holding_days:
                realized_profit += utxo_value
                profitable_spends += 1
            else:
                realized_loss += utxo_value
        
        net_pnl = realized_profit - realized_loss
        
        # Profit-loss ratio
        if realized_loss > 0:
            profit_loss_ratio = realized_profit / realized_loss
        else:
            profit_loss_ratio = realized_profit / Decimal('0.001')  # Avoid division by zero
        
        # Win rate
        win_rate = Decimal(str(profitable_spends / len(spent_utxos))) if spent_utxos else Decimal('0')
        
        return {
            'realized_profit': realized_profit,
            'realized_loss': realized_loss,
            'net_pnl': net_pnl,
            'profit_loss_ratio': profit_loss_ratio,
            'win_rate': win_rate,
            'profitable_spends': profitable_spends,
            'total_spends': len(spent_utxos)
        }
    
    def _calculate_timing_features(self, transactions: List[Dict[str, Any]],
                                  whale_activity: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate timing quality features."""
        
        # Simplified timing analysis
        # In practice, this would identify accumulation/distribution periods
        # and correlate with whale activity
        
        return {
            'accumulation_before_spike_rate': Decimal('0.5'),  # Placeholder
            'distribution_after_spike_rate': Decimal('0.5'),   # Placeholder
            'accumulation_periods': 0,
            'distribution_periods': 0,
            'successful_accumulations': 0,
            'successful_distributions': 0
        }
    
    def _calculate_discipline_features(self, transactions: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        """Calculate activity discipline features."""
        
        if len(transactions) < 2:
            return {
                'tx_frequency_per_day': Decimal('0'),
                'tx_frequency_std': Decimal('0'),
                'consistency_score': Decimal('0.5'),
                'overtrading_penalty': Decimal('0'),
                'avg_interval_hours': Decimal('0')
            }
        
        # Calculate transaction frequency
        time_span_days = (transactions[-1]['block_time'] - transactions[0]['block_time']).days
        if time_span_days == 0:
            time_span_days = 1
        
        tx_frequency_per_day = Decimal(str(len(transactions) / time_span_days))
        
        # Calculate transaction intervals
        intervals = []
        for i in range(1, len(transactions)):
            interval_hours = (transactions[i]['block_time'] - transactions[i-1]['block_time']).total_seconds() / 3600
            intervals.append(interval_hours)
        
        if intervals:
            avg_interval_hours = Decimal(str(np.mean(intervals)))
            interval_std = np.std(intervals)
            tx_frequency_std = Decimal(str(interval_std))
            
            # Consistency score (lower std = more consistent)
            if np.mean(intervals) > 0:
                cv = interval_std / np.mean(intervals)
                consistency_score = Decimal(str(max(0, 1 - cv)))
            else:
                consistency_score = Decimal('0.5')
        else:
            avg_interval_hours = Decimal('0')
            tx_frequency_std = Decimal('0')
            consistency_score = Decimal('0.5')
        
        # Overtrading penalty (simplified)
        network_median_frequency = 0.1  # Placeholder: 0.1 tx per day
        if float(tx_frequency_per_day) > network_median_frequency:
            overtrading_penalty = Decimal(str(min(1.0, 
                (float(tx_frequency_per_day) - network_median_frequency) / network_median_frequency
            )))
        else:
            overtrading_penalty = Decimal('0')
        
        return {
            'tx_frequency_per_day': tx_frequency_per_day,
            'tx_frequency_std': tx_frequency_std,
            'consistency_score': consistency_score,
            'overtrading_penalty': overtrading_penalty,
            'avg_interval_hours': avg_interval_hours
        }
    
    def _calculate_behavioral_metrics(self, transactions: List[Dict[str, Any]], 
                                    utxos: List[Dict[str, Any]]) -> Dict[str, Decimal]:
        """Calculate additional behavioral metrics."""
        
        if not transactions:
            return {
                'round_number_ratio': Decimal('0'),
                'coinbase_ratio': Decimal('0'),
                'avg_inputs_per_tx': Decimal('0'),
                'avg_outputs_per_tx': Decimal('0'),
                'avg_tx_value': Decimal('0')
            }
        
        # Round number detection (simplified)
        round_number_count = 0
        coinbase_count = 0
        total_value = Decimal('0')
        
        for tx in transactions:
            # Check for round numbers (simplified heuristic)
            tx_value = Decimal(str(tx['total_output_btc']))
            if tx_value > 0 and float(tx_value) == float(int(tx_value)):
                round_number_count += 1
            
            if tx['is_coinbase']:
                coinbase_count += 1
            
            total_value += tx_value
        
        round_number_ratio = Decimal(str(round_number_count / len(transactions)))
        coinbase_ratio = Decimal(str(coinbase_count / len(transactions)))
        avg_tx_value = total_value / len(transactions) if transactions else Decimal('0')
        
        # Simplified input/output averages (would need actual transaction input/output data)
        avg_inputs_per_tx = Decimal('2')  # Placeholder
        avg_outputs_per_tx = Decimal('2')  # Placeholder
        
        return {
            'round_number_ratio': round_number_ratio,
            'coinbase_ratio': coinbase_ratio,
            'avg_inputs_per_tx': avg_inputs_per_tx,
            'avg_outputs_per_tx': avg_outputs_per_tx,
            'avg_tx_value': avg_tx_value
        }
    
    def _calculate_percentile_features(self, holding_features: Dict[str, Decimal],
                                     pnl_features: Dict[str, Decimal],
                                     discipline_features: Dict[str, Decimal]) -> Dict[str, Decimal]:
        """Calculate network-relative percentile features."""
        
        # In practice, these would be calculated against actual network distributions
        # For now, using placeholder values
        
        return {
            'holding_time_percentile': Decimal('0.5'),
            'win_rate_percentile': Decimal('0.5'),
            'pnl_ratio_percentile': Decimal('0.5'),
            'net_pnl_percentile': Decimal('0.5'),
            'frequency_std_percentile': Decimal('0.5')
        }
    
    def _get_timeframe_start(self, end_timestamp: datetime, timeframe: str) -> datetime:
        """Get start timestamp for timeframe."""
        
        timeframe_days = {
            '30d': 30,
            '90d': 90,
            '1y': 365
        }
        
        days = timeframe_days.get(timeframe, 30)
        return end_timestamp - timedelta(days=days)
    
    def _get_cached_features(self, address: str, timeframe: str, 
                           end_timestamp: datetime) -> Optional[WalletBehaviorFeatures]:
        """Get cached features if still valid."""
        
        cache_key = f"{address}_{timeframe}_{end_timestamp.date()}"
        
        if cache_key in self.feature_cache:
            cached_data, cached_time = self.feature_cache[cache_key]
            
            # Check if cache is still valid
            if datetime.now() - cached_time < timedelta(hours=self.config.feature_cache_ttl_hours):
                return cached_data
        
        return None
    
    def _cache_features(self, features: WalletBehaviorFeatures):
        """Cache calculated features."""
        
        cache_key = f"{features.address}_{features.timeframe}_{features.calculation_timestamp.date()}"
        self.feature_cache[cache_key] = (features, datetime.now())
        
        # Cleanup old cache entries (keep only last 1000)
        if len(self.feature_cache) > 1000:
            oldest_key = min(self.feature_cache.keys(), 
                           key=lambda k: self.feature_cache[k][1])
            del self.feature_cache[oldest_key]
    
    def close(self):
        """Close database connections."""
        self.engine.dispose()
        self.logger.info("Feature engine connections closed")