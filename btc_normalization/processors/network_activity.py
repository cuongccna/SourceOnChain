"""Network activity processor for normalization pipeline."""

from datetime import datetime
from decimal import Decimal
from typing import List, Dict, Any, Optional
import statistics
import structlog

from btc_normalization.models.normalized_data import NetworkActivityData

logger = structlog.get_logger(__name__)


class NetworkActivityProcessor:
    """Processes raw transaction data into network activity metrics."""
    
    def __init__(self):
        self.logger = logger.bind(component="network_activity_processor")
    
    def process(self, timestamp: datetime, timeframe: str,
                transactions: List[Dict[str, Any]], 
                blocks: Optional[List[Dict[str, Any]]] = None) -> NetworkActivityData:
        """
        Process raw transaction data into network activity metrics.
        
        Args:
            timestamp: Normalized timestamp (candle open)
            timeframe: Time interval ('1h', '4h', '1d')
            transactions: Raw transaction data
            blocks: Optional block data for additional metrics
            
        Returns:
            NetworkActivityData object
        """
        self.logger.debug("Processing network activity", 
                         timestamp=timestamp,
                         timeframe=timeframe,
                         tx_count=len(transactions))
        
        # Extract unique addresses from transactions
        active_addresses = self._extract_active_addresses(transactions)
        
        # Calculate transaction metrics
        tx_metrics = self._calculate_transaction_metrics(transactions)
        
        # Calculate block metrics if available
        block_metrics = self._calculate_block_metrics(blocks) if blocks else {}
        
        return NetworkActivityData(
            timestamp=timestamp,
            asset="BTC",
            timeframe=timeframe,
            active_addresses=len(active_addresses),
            tx_count=len(transactions),
            total_tx_volume_btc=tx_metrics['total_volume'],
            avg_tx_value_btc=tx_metrics['avg_value'],
            median_tx_value_btc=tx_metrics.get('median_value'),
            total_fees_btc=tx_metrics.get('total_fees'),
            avg_fee_per_tx_btc=tx_metrics.get('avg_fee'),
            avg_tx_size_bytes=tx_metrics.get('avg_size'),
            blocks_mined=block_metrics.get('blocks_mined'),
            avg_block_size_bytes=block_metrics.get('avg_block_size'),
            avg_tx_per_block=block_metrics.get('avg_tx_per_block')
        )
    
    def _extract_active_addresses(self, transactions: List[Dict[str, Any]]) -> set:
        """Extract unique addresses involved in transactions."""
        active_addresses = set()
        
        # This would need to be enhanced to extract addresses from UTXOs
        # For now, we'll use a placeholder approach
        for tx in transactions:
            tx_hash = tx.get('tx_hash')
            if tx_hash:
                # In a real implementation, we'd query UTXOs for this transaction
                # and extract addresses from both inputs and outputs
                pass
        
        # Placeholder: estimate based on transaction count
        # In practice, this would be calculated from actual UTXO address data
        estimated_addresses = len(transactions) * 2  # rough estimate
        return set(range(estimated_addresses))
    
    def _calculate_transaction_metrics(self, transactions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate transaction-level metrics."""
        if not transactions:
            return {
                'total_volume': Decimal('0'),
                'avg_value': Decimal('0'),
                'median_value': Decimal('0'),
                'total_fees': Decimal('0'),
                'avg_fee': Decimal('0'),
                'avg_size': Decimal('0')
            }
        
        # Extract values
        tx_values = []
        tx_fees = []
        tx_sizes = []
        
        for tx in transactions:
            # Transaction value (total output)
            output_value = tx.get('total_output_btc', 0)
            if output_value and not tx.get('is_coinbase', False):
                tx_values.append(Decimal(str(output_value)))
            
            # Transaction fee
            fee = tx.get('fee_btc', 0)
            if fee:
                tx_fees.append(Decimal(str(fee)))
            
            # Transaction size
            size = tx.get('tx_size_bytes', 0)
            if size:
                tx_sizes.append(size)
        
        # Calculate metrics
        total_volume = sum(tx_values) if tx_values else Decimal('0')
        avg_value = total_volume / len(tx_values) if tx_values else Decimal('0')
        median_value = Decimal(str(statistics.median([float(v) for v in tx_values]))) if tx_values else Decimal('0')
        
        total_fees = sum(tx_fees) if tx_fees else Decimal('0')
        avg_fee = total_fees / len(tx_fees) if tx_fees else Decimal('0')
        
        avg_size = Decimal(str(statistics.mean(tx_sizes))) if tx_sizes else Decimal('0')
        
        return {
            'total_volume': total_volume,
            'avg_value': avg_value,
            'median_value': median_value,
            'total_fees': total_fees,
            'avg_fee': avg_fee,
            'avg_size': avg_size
        }
    
    def _calculate_block_metrics(self, blocks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate block-level metrics."""
        if not blocks:
            return {}
        
        block_sizes = []
        tx_counts = []
        
        for block in blocks:
            size = block.get('block_size_bytes', 0)
            if size:
                block_sizes.append(size)
            
            tx_count = block.get('tx_count', 0)
            if tx_count:
                tx_counts.append(tx_count)
        
        avg_block_size = Decimal(str(statistics.mean(block_sizes))) if block_sizes else Decimal('0')
        avg_tx_per_block = Decimal(str(statistics.mean(tx_counts))) if tx_counts else Decimal('0')
        
        return {
            'blocks_mined': len(blocks),
            'avg_block_size': avg_block_size,
            'avg_tx_per_block': avg_tx_per_block
        }