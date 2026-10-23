"""
ERC-8021 Transaction Attribution Module for Base L2.
Implements the canonical ERC-8021 Data Suffix standard (Schema 0) for Base Builder Codes.
Allows the Autonomous Micro-Entrepreneur (AME) agent to attribute all on-chain activity,
claim submissions, and ETH sweeps to its builder identity for Base ecosystem rewards and indexation.
Specification: https://erc8021.com / Base Builder Codes.
"""
import os
from typing import Optional, Dict, Any

DEFAULT_BUILDER_CODE = os.getenv("BASE_BUILDER_CODE", "ame_agent")
ERC8021_MARKER = bytes.fromhex("80218021802180218021802180218021") # 16 bytes: 0x8021 repeated 8 times

def encode_erc8021_suffix(builder_code: str = DEFAULT_BUILDER_CODE) -> bytes:
    """
    Encodes an ERC-8021 Schema 0 data suffix for a builder code.
    Format: [CODES] + [CODES_LENGTH (1 byte)] + [SCHEMA_ID (0x00)] + [ERC_MARKER (16 bytes)]
    """
    code_bytes = builder_code.strip().encode("ascii")
    if len(code_bytes) > 255:
        raise ValueError("Builder code exceeds maximum length of 255 bytes")
    schema_id = b"\x00"
    codes_length = bytes([len(code_bytes)])
    return code_bytes + codes_length + schema_id + ERC8021_MARKER

def attach_erc8021_attribution(calldata_hex: str, builder_code: str = DEFAULT_BUILDER_CODE) -> str:
    """
    Appends the ERC-8021 attribution suffix to any transaction calldata hex string.
    Ensures safe execution because EVM smart contracts ignore trailing calldata bytes.
    """
    raw = calldata_hex.strip()
    prefix = "0x" if raw.startswith("0x") else ""
    clean_hex = raw[2:] if raw.startswith("0x") else raw
    
    # If calldata already has an ERC-8021 marker at the end, return as is
    if clean_hex.lower().endswith(ERC8021_MARKER.hex().lower()):
        return raw

    suffix = encode_erc8021_suffix(builder_code)
    return f"{prefix}{clean_hex}{suffix.hex()}"

def decode_erc8021_attribution(calldata_hex: str) -> Optional[Dict[str, Any]]:
    """
    Parses and decodes an ERC-8021 suffix from calldata by reading backwards from the tail.
    """
    clean_hex = calldata_hex.strip().lower()
    if clean_hex.startswith("0x"):
        clean_hex = clean_hex[2:]

    try:
        raw_bytes = bytes.fromhex(clean_hex)
    except Exception:
        return None

    if len(raw_bytes) < 18:
        return None

    if not raw_bytes.endswith(ERC8021_MARKER):
        return None

    # schemaId is 17th byte from the end
    schema_id = raw_bytes[-17]
    if schema_id == 0: # Schema 0: Canonical Registry
        codes_len = raw_bytes[-18]
        if len(raw_bytes) < 18 + codes_len:
            return None
        codes_bytes = raw_bytes[-18 - codes_len : -18]
        codes_str = codes_bytes.decode("ascii", errors="replace")
        return {
            "has_attribution": True,
            "standard": "ERC-8021",
            "schema_id": 0,
            "builder_code": codes_str,
            "marker": ERC8021_MARKER.hex(),
            "suffix_hex": raw_bytes[-18 - codes_len :].hex()
        }
    
    return {
        "has_attribution": True,
        "standard": "ERC-8021",
        "schema_id": schema_id,
        "marker": ERC8021_MARKER.hex()
    }

if __name__ == "__main__":
    suffix = encode_erc8021_suffix("ame_agent")
    print(f"ERC-8021 Module OK. Sample suffix for 'ame_agent': {suffix.hex()}")
    sample_tx = attach_erc8021_attribution("0xa9059cbb0000000000000000000000001234567890123456789012345678901234567890", "ame_agent")
    decoded = decode_erc8021_attribution(sample_tx)
    print("Decoded verification:", decoded)
