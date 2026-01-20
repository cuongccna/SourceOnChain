"""Bitcoin-specific utility functions."""

import re
import hashlib
import base58
from decimal import Decimal
from typing import Optional, Dict, Any, List
import structlog

logger = structlog.get_logger(__name__)

# Bitcoin address patterns
P2PKH_PATTERN = re.compile(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$')
P2SH_PATTERN = re.compile(r'^3[a-km-zA-HJ-NP-Z1-9]{25,34}$')
BECH32_PATTERN = re.compile(r'^(bc1|tb1)[a-z0-9]{39,59}$')

# Satoshis per Bitcoin
SATOSHIS_PER_BTC = Decimal('100000000')


def satoshi_to_btc(satoshis: int) -> Decimal:
    """Convert satoshis to BTC."""
    return Decimal(satoshis) / SATOSHIS_PER_BTC


def btc_to_satoshi(btc: Decimal) -> int:
    """Convert BTC to satoshis."""
    return int(btc * SATOSHIS_PER_BTC)


def validate_bitcoin_address(address: str) -> bool:
    """Validate Bitcoin address format."""
    if not address:
        return False
    
    # Check basic patterns
    if P2PKH_PATTERN.match(address) or P2SH_PATTERN.match(address):
        return _validate_base58_address(address)
    elif BECH32_PATTERN.match(address):
        return _validate_bech32_address(address)
    
    return False


def _validate_base58_address(address: str) -> bool:
    """Validate Base58 encoded address (P2PKH/P2SH)."""
    try:
        decoded = base58.b58decode(address)
        if len(decoded) != 25:
            return False
        
        # Verify checksum
        payload = decoded[:-4]
        checksum = decoded[-4:]
        hash_result = hashlib.sha256(hashlib.sha256(payload).digest()).digest()
        
        return hash_result[:4] == checksum
    except Exception:
        return False


def _validate_bech32_address(address: str) -> bool:
    """Validate Bech32 encoded address (SegWit)."""
    # Simplified validation - in production, use proper bech32 library
    try:
        if not address.startswith(('bc1', 'tb1')):
            return False
        
        # Basic length and character validation
        if len(address) < 42 or len(address) > 62:
            return False
        
        # Check character set
        valid_chars = set('qpzry9x8gf2tvdw0s3jn54khce6mua7l')
        return all(c in valid_chars for c in address[3:])
    except Exception:
        return False


def get_script_type(script_hex: str, addresses: List[str] = None) -> str:
    """Determine script type from script hex."""
    if not script_hex:
        return "unknown"
    
    script_bytes = bytes.fromhex(script_hex)
    
    # P2PKH: OP_DUP OP_HASH160 <pubKeyHash> OP_EQUALVERIFY OP_CHECKSIG
    if (len(script_bytes) == 25 and 
        script_bytes[0] == 0x76 and  # OP_DUP
        script_bytes[1] == 0xa9 and  # OP_HASH160
        script_bytes[2] == 0x14 and  # Push 20 bytes
        script_bytes[23] == 0x88 and # OP_EQUALVERIFY
        script_bytes[24] == 0xac):   # OP_CHECKSIG
        return "P2PKH"
    
    # P2SH: OP_HASH160 <scriptHash> OP_EQUAL
    if (len(script_bytes) == 23 and
        script_bytes[0] == 0xa9 and  # OP_HASH160
        script_bytes[1] == 0x14 and  # Push 20 bytes
        script_bytes[22] == 0x87):   # OP_EQUAL
        return "P2SH"
    
    # P2WPKH: OP_0 <20-byte-pubkey-hash>
    if (len(script_bytes) == 22 and
        script_bytes[0] == 0x00 and  # OP_0
        script_bytes[1] == 0x14):    # Push 20 bytes
        return "P2WPKH"
    
    # P2WSH: OP_0 <32-byte-script-hash>
    if (len(script_bytes) == 34 and
        script_bytes[0] == 0x00 and  # OP_0
        script_bytes[1] == 0x20):    # Push 32 bytes
        return "P2WSH"
    
    # P2TR: OP_1 <32-byte-taproot-output>
    if (len(script_bytes) == 34 and
        script_bytes[0] == 0x51 and  # OP_1
        script_bytes[1] == 0x20):    # Push 32 bytes
        return "P2TR"
    
    # P2PK: <pubkey> OP_CHECKSIG
    if (len(script_bytes) in [35, 67] and
        script_bytes[-1] == 0xac):   # OP_CHECKSIG
        return "P2PK"
    
    # Multisig: OP_M <pubkey1> ... <pubkeyN> OP_N OP_CHECKMULTISIG
    if (len(script_bytes) > 3 and
        script_bytes[0] >= 0x51 and script_bytes[0] <= 0x60 and  # OP_1 to OP_16
        script_bytes[-1] == 0xae):   # OP_CHECKMULTISIG
        return "MULTISIG"
    
    # OP_RETURN (data output)
    if len(script_bytes) > 0 and script_bytes[0] == 0x6a:  # OP_RETURN
        return "OP_RETURN"
    
    return "NON_STANDARD"


def decode_address(script_hex: str, script_type: str = None) -> Optional[str]:
    """Extract Bitcoin address from output script."""
    if not script_hex:
        return None
    
    try:
        script_bytes = bytes.fromhex(script_hex)
        
        if not script_type:
            script_type = get_script_type(script_hex)
        
        if script_type == "P2PKH":
            # Extract pubkey hash (bytes 3-22)
            pubkey_hash = script_bytes[3:23]
            return _hash160_to_p2pkh_address(pubkey_hash)
        
        elif script_type == "P2SH":
            # Extract script hash (bytes 2-21)
            script_hash = script_bytes[2:22]
            return _hash160_to_p2sh_address(script_hash)
        
        elif script_type in ["P2WPKH", "P2WSH"]:
            # SegWit addresses - would need bech32 encoding
            # Simplified: return None for now
            return None
        
        elif script_type == "P2TR":
            # Taproot addresses - would need bech32m encoding
            return None
        
        return None
        
    except Exception as e:
        logger.warning("Failed to decode address", script_hex=script_hex, error=str(e))
        return None


def _hash160_to_p2pkh_address(pubkey_hash: bytes) -> str:
    """Convert pubkey hash to P2PKH address."""
    # Mainnet P2PKH version byte
    version_byte = b'\x00'
    payload = version_byte + pubkey_hash
    
    # Double SHA256 for checksum
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    
    # Base58 encode
    return base58.b58encode(payload + checksum).decode('ascii')


def _hash160_to_p2sh_address(script_hash: bytes) -> str:
    """Convert script hash to P2SH address."""
    # Mainnet P2SH version byte
    version_byte = b'\x05'
    payload = version_byte + script_hash
    
    # Double SHA256 for checksum
    checksum = hashlib.sha256(hashlib.sha256(payload).digest()).digest()[:4]
    
    # Base58 encode
    return base58.b58encode(payload + checksum).decode('ascii')


def calculate_fee(inputs_value: Decimal, outputs_value: Decimal) -> Decimal:
    """Calculate transaction fee."""
    return inputs_value - outputs_value


def parse_vout(vout_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse transaction output data."""
    value_btc = Decimal(str(vout_data.get('value', 0)))
    script_pub_key = vout_data.get('scriptPubKey', {})
    
    script_hex = script_pub_key.get('hex', '')
    script_type = script_pub_key.get('type', 'unknown')
    addresses = script_pub_key.get('addresses', [])
    
    # Get primary address
    address = addresses[0] if addresses else None
    
    # Decode address if not provided
    if not address and script_hex:
        address = decode_address(script_hex, script_type)
    
    # Normalize script type
    normalized_script_type = get_script_type(script_hex, addresses)
    
    return {
        'value_btc': value_btc,
        'address': address,
        'script_type': normalized_script_type,
        'script_hex': script_hex,
        'addresses': addresses
    }


def parse_vin(vin_data: Dict[str, Any]) -> Dict[str, Any]:
    """Parse transaction input data."""
    # Coinbase transaction
    if 'coinbase' in vin_data:
        return {
            'is_coinbase': True,
            'previous_tx_hash': None,
            'previous_vout_index': None,
            'script_sig_hex': vin_data.get('coinbase', ''),
            'witness_data': vin_data.get('txinwitness'),
            'sequence_number': vin_data.get('sequence', 0)
        }
    
    # Regular transaction input
    return {
        'is_coinbase': False,
        'previous_tx_hash': vin_data.get('txid'),
        'previous_vout_index': vin_data.get('vout'),
        'script_sig_hex': vin_data.get('scriptSig', {}).get('hex', ''),
        'witness_data': vin_data.get('txinwitness'),
        'sequence_number': vin_data.get('sequence', 0)
    }