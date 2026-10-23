"""
EAS Indexer: Cliente de consultas para Ethereum Attestation Service (EAS) en Base L2.
Permite verificar reputación on-chain, credenciales de Coinbase/Gitcoin y pruebas de trabajo
directamente desde el protocolo descentralizado EAS (https://base.easscan.org).
"""
import json
import urllib.request
import urllib.error
from typing import Dict, Any, List, Optional

EAS_BASE_GRAPHQL = "https://base.easscan.org/graphql"
EAS_BASE_CONTRACT = "0x4200000000000000000000000000000000000021"

def query_eas_graphql(query: str, variables: Optional[Dict[str, Any]] = None, timeout: float = 8.0) -> Optional[Dict[str, Any]]:
    payload = {"query": query}
    if variables:
        payload["variables"] = variables

    req = urllib.request.Request(
        EAS_BASE_GRAPHQL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AutonomousMicroEntrepreneur/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as res:
            data = json.loads(res.read().decode("utf-8"))
            return data.get("data")
    except Exception as e:
        return None

def get_address_attestations(address: str, limit: int = 10) -> List[Dict[str, Any]]:
    """Obtiene las atestaciones on-chain recibidas o emitidas por una cartera en Base L2"""
    target = address.strip()
    query = """
    query GetAttestations($target: String!, $limit: Int!) {
        received: attestations(where: { recipient: { equals: $target } }, take: $limit, orderBy: [{time: desc}]) {
            id
            attester
            recipient
            time
            schemaId
            revoked
            decodedDataJson
        }
        sent: attestations(where: { attester: { equals: $target } }, take: $limit, orderBy: [{time: desc}]) {
            id
            recipient
            time
            schemaId
            revoked
            decodedDataJson
        }
    }
    """
    res = query_eas_graphql(query, {"target": target, "limit": limit})
    if not res:
        return []

    combined = []
    for a in res.get("received", []):
        a["direction"] = "received"
        combined.append(a)
    for a in res.get("sent", []):
        a["direction"] = "sent"
        combined.append(a)

    return sorted(combined, key=lambda x: x.get("time", 0), reverse=True)

def get_address_reputation(address: str) -> Dict[str, Any]:
    """Calcula un perfil sintético de confianza on-chain analizando atestaciones de Base"""
    attestations = get_address_attestations(address, limit=25)
    received = [a for a in attestations if a.get("direction") == "received"]
    sent = [a for a in attestations if a.get("direction") == "sent"]

    coinbase_verified = False
    for a in received:
        raw_json = a.get("decodedDataJson", "")
        if "verifiedCoinbase" in raw_json or "coinbase" in raw_json.lower():
            coinbase_verified = True
            break

    attesters = list({a.get("attester") for a in received if a.get("attester")})
    trust_score = min(100, (len(received) * 15) + (25 if coinbase_verified else 0) + (len(sent) * 10))

    return {
        "address": address,
        "trust_score": trust_score,
        "coinbase_verified": coinbase_verified,
        "total_attestations_received": len(received),
        "total_attestations_sent": len(sent),
        "unique_attesters_count": len(attesters),
        "latest_attestations": attestations[:5]
    }

def get_recent_attestations(limit: int = 10) -> List[Dict[str, Any]]:
    """Consulta las atestaciones más recientes registradas globalmente en Base Mainnet"""
    query = """
    query GetRecent($limit: Int!) {
        attestations(take: $limit, orderBy: [{time: desc}]) {
            id
            attester
            recipient
            time
            schemaId
            decodedDataJson
        }
    }
    """
    res = query_eas_graphql(query, {"limit": limit})
    return res.get("attestations", []) if res else []

if __name__ == "__main__":
    recent = get_recent_attestations(limit=2)
    print(f"EAS Base Indexer OK. Recent attestations count: {len(recent)}")
    if recent:
        print(f"Latest Attestation ID: {recent[0].get('id')}")
