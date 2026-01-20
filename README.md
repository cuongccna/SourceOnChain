# Bitcoin Raw Data Collector

A production-ready Bitcoin blockchain data collector using only free, self-hosted data sources.

## 📁 Project Structure

```
SourceOnChain/
├── btc_collector/           # Bitcoin Core data collection
├── btc_normalization/       # Time-series normalization
├── whale_detection/         # Whale activity detection
├── smart_wallet_classifier/ # Smart wallet classification
├── onchain_signal_engine/   # Signal generation engine
├── onchain_api/             # 🔒 INTERNAL API (full features)
├── onchain_intel_product/   # 🌐 EXTERNAL API (BotTrading)
└── tests/                   # Test suite
```

> 📖 **See [ARCHITECTURE_DECISION.md](ARCHITECTURE_DECISION.md)** for API module separation rationale.

### API Modules Comparison

| Module | Purpose | Access |
|--------|---------|--------|
| `onchain_api/` | Internal monitoring, debugging, validation | VPN/Internal |
| `onchain_intel_product/` | Production BotTrading integration | External |

## Architecture

```
Bitcoin Core (RPC) → Data Collector → PostgreSQL → Feature Engineering
```

## Features

- **Raw Data Collection**: Block, transaction, UTXO, and address-level data
- **Incremental Sync**: Block-by-block synchronization with state management
- **UTXO Tracking**: Complete UTXO creation and spending tracking
- **Address Aggregation**: Real-time address statistics
- **Self-Hosted**: Uses only Bitcoin Core RPC (no external APIs)
- **Scalable**: Optimized database schema with proper indexing

## Quick Start

1. **Setup Bitcoin Core**:
   ```bash
   # bitcoin.conf
   rpcuser=your_rpc_user
   rpcpassword=your_rpc_password
   rpcport=8332
   server=1
   ```

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure Environment**:
   ```bash
   cp .env.example .env
   # Edit .env with your settings
   ```

4. **Initialize Database**:
   ```bash
   python -m btc_collector.cli init-db
   ```

5. **Start Collection**:
   ```bash
   python -m btc_collector.cli sync --start-height 0
   ```

## Configuration

See `.env.example` for all configuration options.

## Database Schema

The collector uses a normalized PostgreSQL schema optimized for UTXO-based blockchain data:

- `blocks`: Block-level metadata
- `transactions`: Transaction details with fee calculations
- `utxos`: UTXO tracking with spending status
- `transaction_inputs`: Input references for complete transaction graph
- `addresses`: Aggregated address statistics
- `sync_state`: Synchronization state management

## Performance

- **Indexing**: Optimized indexes for common query patterns
- **Batching**: Configurable batch sizes for bulk operations
- **Connection Pooling**: PostgreSQL connection pooling
- **Incremental Sync**: Resume from last synced block

## Future Extensions

This foundation supports:
- Technical indicators calculation
- On-chain analytics
- Trading signal generation
- Real-time monitoring
- Multi-chain support