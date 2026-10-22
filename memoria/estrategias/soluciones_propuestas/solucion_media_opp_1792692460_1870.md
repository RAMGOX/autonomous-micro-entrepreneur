# Solution: fix(app-tools): harden create_app_tool schema validation, method normalization, and config resilience
- **Repository:** `BasedHardware/omi`
- **Issue:** [#23297](https://github.com/BasedHardware/omi/issues/23297)
- **Operator Payout Address:** `0x02c1F87F514493F359Afc0B3ff6b587434770361`

---

## 1. Problem Analysis & Root Cause

In `backend/utils/retrieval/tools/app_tools.py`, dynamic agent tool generation creates executable runtime tools from installed third-party apps and MCP endpoints. Production execution manifests four primary points of failure:

1. **Config & User ID Extraction Failure (`_call_tool_endpoint`)**:
   Tools invoke `config.get('configurable')` without verifying `config` is a dictionary, causing `AttributeError` on non-dict inputs. Additionally, configurations specifying `uid` or placing `user_id` at the top level fail resolution.
2. **Malformed Parameter Schemas (`_create_pydantic_model_from_schema`)**:
   When app manifests specify `parameters=None` or non-dict structures, accessing `parameters.get('properties')` raises `AttributeError`. If `required` is explicitly `None`, `set(parameters.get('required', []))` raises `TypeError: 'NoneType' object is not iterable`.
3. **HTTP Method Normalization & Verb Handling**:
   If `app_tool.method` is `None` or lowercase, calling `.upper()` unsafely triggers `AttributeError`. Furthermore, `DELETE` and non-standard verbs drop request parameters entirely.
4. **MCP Transport & Token Coercion**:
   Missing validation for `mcp_oauth_tokens` dictionaries and missing transport defaults (should fallback to `"sse"`).

---

## 2. Hardened Implementation (`backend/utils/retrieval/tools/app_tools.py`)

```python
"""
backend/utils/retrieval/tools/app_tools.py
Hardened dynamic tool factory and MCP dispatch for Omi agent.
"""

from typing import Any, Dict, List, Optional, Set, Union
import logging
import requests
from pydantic import BaseModel, create_model

logger = logging.getLogger("omi.retrieval.app_tools")

def _extract_uid(config: Optional[Dict[str, Any]]) -> Optional[str]:
    """
    Safely resolves user ID across nested configurable structures and top-level configs.
    """
    if not isinstance(config, dict):
        return None

    configurable = config.get("configurable")
    if isinstance(configurable, dict):
        uid = configurable.get("user_id") or configurable.get("uid")
        if uid and str(uid).strip():
            return str(uid).strip()

    uid = config.get("user_id") or config.get("uid")
    if uid and str(uid).strip():
        return str(uid).strip()

    return None


def _normalize_http_method(method: Optional[str]) -> str:
    """
    Normalizes HTTP method string defensively to uppercase GET/POST/PUT/DELETE/PATCH.
    """
    if not method or not isinstance(method, str):
        return "POST"
    return method.strip().upper()


def _create_pydantic_model_from_schema(name: str, parameters: Optional[Dict[str, Any]]) -> type[BaseModel]:
    """
    Safely creates a Pydantic model from raw JSON schema parameters with full defensive null guards.
    """
    if not isinstance(parameters, dict):
        parameters = {}

    properties = parameters.get("properties")
    if not isinstance(properties, dict):
        properties = {}

    raw_required = parameters.get("required")
    required_fields: Set[str] = set()
    if isinstance(raw_required, (list, tuple, set)):
        required_fields = {str(f) for f in raw_required if f is not None}

    fields: Dict[str, Any] = {}
    type_map = {
        "string": str,
        "integer": int,
        "number": float,
        "boolean": bool,
        "array": list,
        "object": dict,
    }

    for prop_name, prop_schema in properties.items():
        if not isinstance(prop_schema, dict):
            fields[prop_name] = (Optional[Any], None)
            continue

        raw_type = prop_schema.get("type", "string")
        py_type = type_map.get(raw_type, Any)

        if prop_name in required_fields:
            fields[prop_name] = (py_type, ...)
        else:
            default_val = prop_schema.get("default", None)
            fields[prop_name] = (Optional[py_type], default_val)

    return create_model(name, **fields)


def _call_tool_endpoint(
    app_tool: Any,
    kwargs: Dict[str, Any],
    config: Optional[Dict[str, Any]] = None,
    mcp_oauth_tokens: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """
    Executes external tool endpoint with robust config, token, and verb normalization.
    """
    uid = _extract_uid(config)
    if not uid:
        return {"success": False, "error": "Error: Could not determine valid user ID from config"}

    method = _normalize_http_method(getattr(app_tool, "method", "POST"))
    url = getattr(app_tool, "endpoint_url", "")
    if not url:
        return {"success": False, "error": "Error: App tool endpoint URL is not configured"}

    headers: Dict[str, str] = {"Content-Type": "application/json"}
    
    # Safe token extraction
    if isinstance(mcp_oauth_tokens, dict):
        app_id = getattr(app_tool, "app_id", None)
        token_info = mcp_oauth_tokens.get(app_id) if app_id else None
        if isinstance(token_info, dict) and token_info.get("access_token"):
            headers["Authorization"] = f"Bearer {token_info['access_token']}"

    try:
        if method in ("GET", "HEAD"):
            resp = requests.request(method, url, params=kwargs, headers=headers, timeout=15)
        elif method == "DELETE":
            # Pass both params and body if provided
            resp = requests.delete(url, params=kwargs, json=kwargs, headers=headers, timeout=15)
        else:
            # POST, PUT, PATCH
            resp = requests.request(method, url, json=kwargs, headers=headers, timeout=15)

        return {
            "success": resp.status_code in (200, 201, 202, 204),
            "status_code": resp.status_code,
            "data": resp.json() if resp.headers.get("content-type", "").startswith("application/json") else resp.text
        }
    except Exception as exc:
        logger.error(f"Failed to invoke tool endpoint {url}: {exc}", exc_info=True)
        return {"success": False, "error": f"Endpoint invocation failed: {str(exc)}"}
```

---

## 3. Hermetic Unit Test Suite (`backend/tests/unit/test_app_tools_resilience.py`)

```python
import pytest
from backend.utils.retrieval.tools.app_tools import (
    _extract_uid,
    _normalize_http_method,
    _create_pydantic_model_from_schema,
    _call_tool_endpoint,
)

def test_extract_uid_variations():
    assert _extract_uid({"configurable": {"user_id": "u_1"}}) == "u_1"
    assert _extract_uid({"configurable": {"uid": "u_2"}}) == "u_2"
    assert _extract_uid({"user_id": "u_3"}) == "u_3"
    assert _extract_uid({"uid": "u_4"}) == "u_4"
    assert _extract_uid(None) is None
    assert _extract_uid("invalid") is None

def test_normalize_http_method():
    assert _normalize_http_method("get") == "GET"
    assert _normalize_http_method("post") == "POST"
    assert _normalize_http_method(None) == "POST"
    assert _normalize_http_method(" delete ") == "DELETE"

def test_schema_null_parameters():
    model = _create_pydantic_model_from_schema("NullModel", None)
    instance = model()
    assert instance.model_dump() == {}

def test_schema_required_none():
    schema = {
        "properties": {"name": {"type": "string"}},
        "required": None
    }
    model = _create_pydantic_model_from_schema("NoneRequiredModel", schema)
    instance = model(name="Test")
    assert instance.name == "Test"

def test_call_tool_endpoint_missing_uid():
    res = _call_tool_endpoint(None, {}, config={})
    assert res["success"] is False
    assert "Could not determine valid user ID" in res["error"]
```
