"""Main Bitcoin data collector orchestrator."""

import time
from typing import Optional, Dict, Any
from datetime import datetime
import structlog

from btc_collector.models.config import CollectorConfig
from btc_collector.core.rpc_client import BitcoinRPCClient, BitcoinRPCError
from btc_collector.core.block_processor import BlockProcessor
from btc_collector.database.manager import DatabaseManager
from btc_collector.utils.logging import setup_logging

logger = structlog.get_logger(__name__)


class BitcoinCollector:
    """Main Bitcoin blockchain data collector."""
    
    def __init__(self, config: CollectorConfig):
        self.config = config
        self.logger = logger.bind(component="bitcoin_collector")
        
        # Setup logging
        setup_logging(config)
        
        # Initialize components
        self.rpc_client = BitcoinRPCClient(config)
        self.db_manager = DatabaseManager(config)
        self.block_processor = BlockProcessor(self.db_manager)
        
        self.logger.info("Bitcoin collector initialized")
    
    def initialize(self) -> bool:
        """Initialize the collector and verify connections."""
        self.logger.info("Initializing Bitcoin collector...")
        
        # Test Bitcoin Core RPC connection
        if not self.rpc_client.test_connection():
            self.logger.error("Failed to connect to Bitcoin Core RPC")
            return False
        
        # Test database connection
        if not self.db_manager.test_connection():
            self.logger.error("Failed to connect to database")
            return False
        
        # Create database tables if they don't exist
        try:
            self.db_manager.create_tables()
        except Exception as e:
            self.logger.error("Failed to create database tables", error=str(e))
            return False
        
        self.logger.info("Bitcoin collector initialized successfully")
        return True
    
    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        # Get blockchain info from Bitcoin Core
        try:
            blockchain_info = self.rpc_client.get_blockchain_info()
            current_height = blockchain_info.get('blocks', 0)
            
            # Get sync state from database
            sync_state = self.db_manager.get_sync_state()
            last_synced = sync_state.get('last_synced_block_height', 0) if sync_state else 0
            
            return {
                'current_blockchain_height': current_height,
                'last_synced_height': last_synced,
                'blocks_behind': current_height - last_synced,
                'is_syncing': sync_state.get('is_syncing', False) if sync_state else False,
                'sync_progress': (last_synced / current_height * 100) if current_height > 0 else 0
            }
            
        except Exception as e:
            self.logger.error("Failed to get sync status", error=str(e))
            return {}
    
    def sync_blocks(self, start_height: Optional[int] = None, 
                   end_height: Optional[int] = None) -> bool:
        """
        Synchronize blocks from Bitcoin blockchain.
        
        Args:
            start_height: Starting block height (if None, resume from last synced)
            end_height: Ending block height (if None, sync to current tip)
        """
        try:
            # Determine sync range
            if start_height is None:
                sync_state = self.db_manager.get_sync_state()
                start_height = sync_state.get('last_synced_block_height', 0) + 1 if sync_state else 0
            
            if end_height is None:
                current_height = self.rpc_client.get_block_count()
                end_height = current_height
            
            # Validate range
            if start_height > end_height:
                self.logger.warning("Start height is greater than end height",
                                  start=start_height, end=end_height)
                return True
            
            self.logger.info("Starting block synchronization",
                           start_height=start_height,
                           end_height=end_height,
                           total_blocks=end_height - start_height + 1)
            
            # Mark sync as started
            self.db_manager.set_sync_started()
            
            # Process blocks in batches
            batch_size = self.config.sync_batch_size
            current_height = start_height
            
            while current_height <= end_height:
                batch_end = min(current_height + batch_size - 1, end_height)
                
                self.logger.info("Processing block batch",
                               start=current_height,
                               end=batch_end,
                               progress=f"{((current_height - start_height) / (end_height - start_height + 1) * 100):.1f}%")
                
                # Process batch
                success = self._process_block_batch(current_height, batch_end)
                
                if not success:
                    self.logger.error("Failed to process block batch",
                                    start=current_height, end=batch_end)
                    return False
                
                # Update sync state
                self.db_manager.update_sync_state(
                    block_height=batch_end,
                    block_hash=self.rpc_client.get_block_hash(batch_end),
                    is_syncing=True
                )
                
                current_height = batch_end + 1
                
                # Small delay to prevent overwhelming the system
                time.sleep(0.1)
            
            # Mark sync as completed
            self.db_manager.update_sync_state(
                block_height=end_height,
                block_hash=self.rpc_client.get_block_hash(end_height),
                is_syncing=False
            )
            
            self.logger.info("Block synchronization completed",
                           start_height=start_height,
                           end_height=end_height,
                           total_blocks=end_height - start_height + 1)
            
            return True
            
        except Exception as e:
            self.logger.error("Block synchronization failed", error=str(e))
            # Mark sync as not running
            try:
                sync_state = self.db_manager.get_sync_state()
                if sync_state:
                    self.db_manager.update_sync_state(
                        block_height=sync_state.get('last_synced_block_height', 0),
                        block_hash=sync_state.get('last_synced_block_hash', ''),
                        is_syncing=False
                    )
            except:
                pass
            return False
    
    def _process_block_batch(self, start_height: int, end_height: int) -> bool:
        """Process a batch of blocks."""
        for height in range(start_height, end_height + 1):
            try:
                # Skip if block already exists
                if self.db_manager.block_exists(height):
                    self.logger.debug("Block already exists, skipping", height=height)
                    continue
                
                # Get block data from Bitcoin Core
                block_hash = self.rpc_client.get_block_hash(height)
                block_data = self.rpc_client.get_block(block_hash, verbosity=2)
                
                # Process the block
                success = self.block_processor.process_block(block_data)
                
                if not success:
                    self.logger.error("Failed to process block", height=height)
                    return False
                
            except BitcoinRPCError as e:
                self.logger.error("RPC error while processing block",
                                height=height, error=str(e))
                return False
            
            except Exception as e:
                self.logger.error("Unexpected error while processing block",
                                height=height, error=str(e))
                return False
        
        return True
    
    def sync_single_block(self, height: int) -> bool:
        """Synchronize a single block."""
        try:
            self.logger.info("Syncing single block", height=height)
            
            # Get block data
            block_hash = self.rpc_client.get_block_hash(height)
            block_data = self.rpc_client.get_block(block_hash, verbosity=2)
            
            # Process the block
            success = self.block_processor.process_block(block_data)
            
            if success:
                # Update sync state
                self.db_manager.update_sync_state(
                    block_height=height,
                    block_hash=block_hash,
                    is_syncing=False
                )
                
                self.logger.info("Single block sync completed", height=height)
            
            return success
            
        except Exception as e:
            self.logger.error("Failed to sync single block", height=height, error=str(e))
            return False
    
    def continuous_sync(self, poll_interval: int = 30) -> None:
        """
        Run continuous synchronization, polling for new blocks.
        
        Args:
            poll_interval: Seconds between polls for new blocks
        """
        self.logger.info("Starting continuous synchronization",
                        poll_interval=poll_interval)
        
        try:
            while True:
                # Get current status
                status = self.get_sync_status()
                blocks_behind = status.get('blocks_behind', 0)
                
                if blocks_behind > 0:
                    self.logger.info("New blocks detected, syncing...",
                                   blocks_behind=blocks_behind)
                    
                    # Sync new blocks
                    success = self.sync_blocks()
                    
                    if not success:
                        self.logger.error("Failed to sync new blocks")
                else:
                    self.logger.debug("No new blocks, waiting...")
                
                # Wait before next poll
                time.sleep(poll_interval)
                
        except KeyboardInterrupt:
            self.logger.info("Continuous sync interrupted by user")
        except Exception as e:
            self.logger.error("Continuous sync failed", error=str(e))
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get collector statistics."""
        sync_status = self.get_sync_status()
        processing_stats = self.block_processor.get_processing_stats()
        
        return {
            'sync_status': sync_status,
            'processing_stats': processing_stats,
            'config': {
                'batch_size': self.config.sync_batch_size,
                'concurrent_blocks': self.config.sync_concurrent_blocks,
                'address_tracking': self.config.enable_address_tracking
            }
        }
    
    def close(self):
        """Close all connections and cleanup."""
        self.logger.info("Shutting down Bitcoin collector...")
        
        try:
            self.rpc_client.close()
            self.db_manager.close()
            self.logger.info("Bitcoin collector shutdown complete")
        except Exception as e:
            self.logger.error("Error during shutdown", error=str(e))