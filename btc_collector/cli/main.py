"""Command-line interface for the Bitcoin collector."""

import sys
import json
from pathlib import Path
from typing import Optional
import click
import structlog

from btc_collector.models.config import CollectorConfig
from btc_collector.core.collector import BitcoinCollector

logger = structlog.get_logger(__name__)


@click.group()
@click.option('--config-file', '-c', type=click.Path(exists=True), 
              help='Path to configuration file')
@click.option('--log-level', '-l', default='INFO',
              type=click.Choice(['DEBUG', 'INFO', 'WARNING', 'ERROR']),
              help='Logging level')
@click.pass_context
def cli(ctx, config_file: Optional[str], log_level: str):
    """Bitcoin Raw Data Collector CLI."""
    ctx.ensure_object(dict)
    
    # Load configuration
    try:
        if config_file:
            # Load from specific file
            config = CollectorConfig(_env_file=config_file)
        else:
            # Load from default .env file or environment
            config = CollectorConfig()
        
        # Override log level if specified
        config.log_level = log_level
        
        ctx.obj['config'] = config
        
    except Exception as e:
        click.echo(f"Error loading configuration: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def init_db(ctx):
    """Initialize the database schema."""
    config = ctx.obj['config']
    
    click.echo("Initializing database...")
    
    try:
        collector = BitcoinCollector(config)
        
        if collector.initialize():
            click.echo("✅ Database initialized successfully")
        else:
            click.echo("❌ Failed to initialize database", err=True)
            sys.exit(1)
            
    except Exception as e:
        click.echo(f"❌ Database initialization failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.option('--start-height', '-s', type=int, default=None,
              help='Starting block height (default: resume from last synced)')
@click.option('--end-height', '-e', type=int, default=None,
              help='Ending block height (default: current tip)')
@click.option('--continuous', '-c', is_flag=True,
              help='Run continuous synchronization')
@click.option('--poll-interval', '-p', type=int, default=30,
              help='Polling interval for continuous sync (seconds)')
@click.pass_context
def sync(ctx, start_height: Optional[int], end_height: Optional[int],
         continuous: bool, poll_interval: int):
    """Synchronize blockchain data."""
    config = ctx.obj['config']
    
    try:
        collector = BitcoinCollector(config)
        
        # Initialize collector
        if not collector.initialize():
            click.echo("❌ Failed to initialize collector", err=True)
            sys.exit(1)
        
        if continuous:
            click.echo(f"🔄 Starting continuous synchronization (poll interval: {poll_interval}s)")
            click.echo("Press Ctrl+C to stop...")
            collector.continuous_sync(poll_interval)
        else:
            # Get sync status
            status = collector.get_sync_status()
            click.echo(f"📊 Current blockchain height: {status.get('current_blockchain_height', 0)}")
            click.echo(f"📊 Last synced height: {status.get('last_synced_height', 0)}")
            click.echo(f"📊 Blocks behind: {status.get('blocks_behind', 0)}")
            
            # Perform sync
            click.echo("🔄 Starting synchronization...")
            success = collector.sync_blocks(start_height, end_height)
            
            if success:
                click.echo("✅ Synchronization completed successfully")
            else:
                click.echo("❌ Synchronization failed", err=True)
                sys.exit(1)
        
        collector.close()
        
    except KeyboardInterrupt:
        click.echo("\n🛑 Synchronization interrupted by user")
    except Exception as e:
        click.echo(f"❌ Synchronization failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('height', type=int)
@click.pass_context
def sync_block(ctx, height: int):
    """Synchronize a single block."""
    config = ctx.obj['config']
    
    try:
        collector = BitcoinCollector(config)
        
        if not collector.initialize():
            click.echo("❌ Failed to initialize collector", err=True)
            sys.exit(1)
        
        click.echo(f"🔄 Syncing block {height}...")
        success = collector.sync_single_block(height)
        
        if success:
            click.echo(f"✅ Block {height} synced successfully")
        else:
            click.echo(f"❌ Failed to sync block {height}", err=True)
            sys.exit(1)
        
        collector.close()
        
    except Exception as e:
        click.echo(f"❌ Block sync failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def status(ctx):
    """Show synchronization status."""
    config = ctx.obj['config']
    
    try:
        collector = BitcoinCollector(config)
        
        if not collector.initialize():
            click.echo("❌ Failed to initialize collector", err=True)
            sys.exit(1)
        
        # Get status
        sync_status = collector.get_sync_status()
        stats = collector.get_statistics()
        
        click.echo("📊 Bitcoin Collector Status")
        click.echo("=" * 40)
        click.echo(f"Blockchain Height: {sync_status.get('current_blockchain_height', 0):,}")
        click.echo(f"Last Synced: {sync_status.get('last_synced_height', 0):,}")
        click.echo(f"Blocks Behind: {sync_status.get('blocks_behind', 0):,}")
        click.echo(f"Sync Progress: {sync_status.get('sync_progress', 0):.2f}%")
        click.echo(f"Is Syncing: {'Yes' if sync_status.get('is_syncing', False) else 'No'}")
        
        # Configuration
        click.echo("\n⚙️  Configuration")
        click.echo("=" * 40)
        click.echo(f"Batch Size: {config.sync_batch_size}")
        click.echo(f"Address Tracking: {'Enabled' if config.enable_address_tracking else 'Disabled'}")
        click.echo(f"Daily Stats: {'Enabled' if config.enable_daily_stats else 'Disabled'}")
        
        collector.close()
        
    except Exception as e:
        click.echo(f"❌ Failed to get status: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def test_connection(ctx):
    """Test connections to Bitcoin Core and database."""
    config = ctx.obj['config']
    
    try:
        collector = BitcoinCollector(config)
        
        click.echo("🔍 Testing Bitcoin Core RPC connection...")
        if collector.rpc_client.test_connection():
            click.echo("✅ Bitcoin Core RPC connection successful")
        else:
            click.echo("❌ Bitcoin Core RPC connection failed")
        
        click.echo("🔍 Testing database connection...")
        if collector.db_manager.test_connection():
            click.echo("✅ Database connection successful")
        else:
            click.echo("❌ Database connection failed")
        
        collector.close()
        
    except Exception as e:
        click.echo(f"❌ Connection test failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.argument('height', type=int)
@click.option('--output', '-o', type=click.File('w'), default='-',
              help='Output file (default: stdout)')
@click.pass_context
def export_block(ctx, height: int, output):
    """Export block data as JSON."""
    config = ctx.obj['config']
    
    try:
        collector = BitcoinCollector(config)
        
        if not collector.initialize():
            click.echo("❌ Failed to initialize collector", err=True)
            sys.exit(1)
        
        # Get block data from database
        block = collector.db_manager.get_block(height)
        
        if not block:
            click.echo(f"❌ Block {height} not found in database", err=True)
            sys.exit(1)
        
        # Convert to JSON-serializable format
        block_data = {
            'block_height': block.block_height,
            'block_hash': block.block_hash,
            'block_time': block.block_time.isoformat(),
            'tx_count': block.tx_count,
            'total_fees_btc': float(block.total_fees_btc),
            'block_size_bytes': block.block_size_bytes,
            'difficulty': float(block.difficulty) if block.difficulty else None,
            'nonce': block.nonce,
            'merkle_root': block.merkle_root,
            'previous_block_hash': block.previous_block_hash
        }
        
        json.dump(block_data, output, indent=2)
        
        if output != sys.stdout:
            click.echo(f"✅ Block {height} exported successfully")
        
        collector.close()
        
    except Exception as e:
        click.echo(f"❌ Block export failed: {e}", err=True)
        sys.exit(1)


@cli.command()
@click.pass_context
def version(ctx):
    """Show version information."""
    from btc_collector import __version__, __description__
    
    click.echo(f"Bitcoin Raw Data Collector v{__version__}")
    click.echo(__description__)


if __name__ == '__main__':
    cli()